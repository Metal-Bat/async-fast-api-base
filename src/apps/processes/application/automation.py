"""Crash-safe dispatch and execution of registered BPMS background operations."""

from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.agent_service import AIAgentService
from apps.ai.application.budget_service import AIBudgetService
from apps.ai.application.decision import pinned_decision
from apps.ai.domain.entity import AITaskBudgetEntity
from apps.integrations.application.providers import ConnectionProvider, StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.data.secrets import EncryptedFileSecrets
from apps.processes.application.extension_services import ProcessStepServices
from apps.processes.domain.automation import AutomationResult, AutomationSnapshot
from apps.processes.domain.entity import (
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.requests.domain.entity import BusinessRequestEntity
from apps.step_types.application.automation import resolve_operation
from apps.step_types.application.invocation import StepInvocationContext
from apps.step_types.application.registry import HandlerDefinition, ServiceConfig, get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeVersionEntity
from apps.tasks.application.outbox import enqueue_task
from apps.tasks.domain.entity import TaskExecutionEntity
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowStepEntity, WorkflowVersionEntity
from core.deps import SessionFactory
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import VersionConflictException

BACKGROUND_TASK = "bpms.execute_background"


def broker_priority(business_priority: int) -> int:
    """Map the stable 0..9 business scale onto the configured broker scale."""
    if not 0 <= business_priority <= 9:
        raise ValueError("Business priority must be between 0 and 9")
    return round(business_priority * settings.CELERY_MAX_PRIORITY / 9)


def _provider() -> StatusProvider:
    secrets = EncryptedFileSecrets(
        settings.INTEGRATION_SECRETS_DIR,
        [key.get_secret_value().encode() for key in settings.INTEGRATION_SECRET_KEYS],
    )
    return StatusProvider(secrets, settings.INTEGRATION_HTTP_ENDPOINTS)


class AutomationDispatcher:
    def __init__(self, session: AsyncSession, provider: ConnectionProvider | None = None) -> None:
        self.session = session
        self.provider = provider or _provider()

    async def stage(
        self,
        *,
        attempt: StepExecutionAttemptEntity,
        step: WorkflowStepEntity,
        handler: HandlerDefinition,
        request: BusinessRequestEntity,
    ) -> None:
        """Pin authorization and stage one opaque message in the caller's transaction."""
        config = ServiceConfig.model_validate(step.config)
        operation = resolve_operation(
            config.operation_key, handler.handler_key, handler.handler_version
        )
        version = await self.session.get(WorkflowVersionEntity, request.workflow_version_id)
        actor = (
            await self.session.get(UserEntity, version.published_by_user_id)
            if version is not None and version.published_by_user_id is not None
            else None
        )
        if actor is None:
            raise VersionConflictException("Published workflow has no execution principal")
        pin = await ConnectionService(self.session, self.provider).pin(
            config.connection_ref,
            actor,
            handler_key=handler.handler_key,
            handler_version=handler.handler_version,
        )
        snapshot = AutomationSnapshot(
            handler_key=handler.handler_key,
            handler_version=handler.handler_version,
            operation_key=operation.key,
            actor_id=actor.id,
            connection=pin,
        )
        attempt.automation_snapshot = snapshot.model_dump(mode="json")
        enqueue_task(
            self.session,
            BACKGROUND_TASK,
            kwargs={"attempt_id": str(attempt.id)},
            task_id=str(attempt.id),
            idempotency_key=attempt.id,
            queue=settings.CELERY_AUTOMATION_QUEUE,
            priority=broker_priority(request.priority),
        )
        execution = await self.session.get(StepExecutionEntity, attempt.step_execution_id)
        if execution is None:
            raise VersionConflictException("Step execution is unavailable")
        from apps.processes.application.events import ProcessEventService

        await ProcessEventService(self.session).append(
            execution.process_instance_id,
            "automation.dispatched",
            actor_user_id=actor.id,
            step_execution_id=execution.id,
            payload={"operation": operation.key, "attempt": attempt.number},
        )

    async def stage_extension(
        self,
        *,
        attempt: StepExecutionAttemptEntity,
        step: WorkflowStepEntity,
        handler: HandlerDefinition,
        request: BusinessRequestEntity,
    ) -> None:
        """Pin capabilities and enqueue one registered background class attempt."""
        if handler.implementation is None or handler.execution_mode != "BACKGROUND":
            raise ValueError("Background class is unavailable")
        config = handler.config_model.model_validate(step.config)
        version = await self.session.get(WorkflowVersionEntity, request.workflow_version_id)
        actor = (
            await self.session.get(UserEntity, version.published_by_user_id)
            if version is not None and version.published_by_user_id is not None
            else None
        )
        if actor is None or actor.deleted_at is not None:
            raise VersionConflictException("Published workflow has no execution principal")
        pin = None
        ai_agent_ref = None
        ai_agent_checksum = None
        ai_decision = None
        if handler.handler_key == "ai_decision":
            ai_agent_ref = getattr(config, "agent_ref", None)
            if not isinstance(ai_agent_ref, str):
                raise ValueError("AI agent reference is required")
            agent, spec = await AIAgentService(self.session).published(ai_agent_ref, actor)
            execution = await self.session.get(StepExecutionEntity, attempt.step_execution_id)
            if execution is None:
                raise VersionConflictException("Step execution is unavailable")
            bound = (execution.input_snapshot or {}).get("data")
            if not isinstance(bound, dict):
                raise ValueError("AI decision requires a data input object")
            ai_decision, _ = pinned_decision(spec, bound)
            previous = (
                await self.session.exec(
                    select(StepExecutionAttemptEntity).where(
                        StepExecutionAttemptEntity.step_execution_id == execution.id,
                        StepExecutionAttemptEntity.id != attempt.id,
                    )
                )
            ).all()
            for prior in previous:
                if prior.automation_snapshot and prior.automation_snapshot.get("ai_decision"):
                    old = AutomationSnapshot.model_validate(prior.automation_snapshot)
                    if old.ai_agent_checksum != agent.checksum or old.ai_decision != ai_decision:
                        raise VersionConflictException(
                            "AI decision contract changed across retries"
                        )
                    ai_decision = old.ai_decision
                    break
            pin, _ = await ConnectionService(self.session, self.provider).pin_ai(
                spec.connection_ref, actor, spec.model_id
            )
            existing = (
                await self.session.exec(
                    select(AITaskBudgetEntity).where(
                        AITaskBudgetEntity.step_execution_id == execution.id
                    )
                )
            ).one_or_none()
            if existing is None:
                await AIBudgetService(self.session).create(
                    execution.id, spec.effective_limits, price_version=spec.price.version
                )
            elif (
                existing.effective_limits != spec.effective_limits.model_dump(mode="json")
                or existing.price_version != spec.price.version
            ):
                raise VersionConflictException("AI task budget pin changed across retries")
            ai_agent_checksum = agent.checksum
        elif "integration.connection.use" in handler.required_capabilities:
            connection_ref = getattr(config, "connection_ref", None)
            if not isinstance(connection_ref, str):
                raise ValueError("Background connection reference is required")
            pin = await ConnectionService(self.session, self.provider).pin_service(
                connection_ref, actor
            )
        snapshot = AutomationSnapshot(
            handler_key=handler.handler_key,
            handler_version=handler.handler_version,
            operation_key="registered",
            actor_id=actor.id,
            connection=pin,
            handler_fingerprint=handler.fingerprint,
            ai_agent_ref=ai_agent_ref,
            ai_agent_checksum=ai_agent_checksum,
            ai_decision=ai_decision,
        )
        attempt.automation_snapshot = snapshot.model_dump(mode="json")
        enqueue_task(
            self.session,
            BACKGROUND_TASK,
            kwargs={"attempt_id": str(attempt.id)},
            task_id=str(attempt.id),
            idempotency_key=attempt.id,
            queue=settings.CELERY_AUTOMATION_QUEUE,
            priority=broker_priority(request.priority),
        )
        execution = await self.session.get(StepExecutionEntity, attempt.step_execution_id)
        if execution is None:
            raise VersionConflictException("Step execution is unavailable")
        from apps.processes.application.events import ProcessEventService

        await ProcessEventService(self.session).append(
            execution.process_instance_id,
            "automation.dispatched",
            actor_user_id=actor.id,
            step_execution_id=execution.id,
            payload={"operation": handler.handler_key, "attempt": attempt.number},
        )


async def execute_background(
    attempt_id: UUID, provider: ConnectionProvider | None = None
) -> AutomationResult:
    """Execute a pinned adapter, then apply its result through an idempotent callback."""
    async with SessionFactory() as session, session.begin():
        attempt = await session.get(
            StepExecutionAttemptEntity,
            attempt_id,
            with_for_update=True,
            populate_existing=True,
        )
        if attempt is None or attempt.automation_snapshot is None:
            raise VersionConflictException("Background attempt is unavailable")
        if attempt.status == "SUCCEEDED":
            return AutomationResult(attempt_id=attempt_id, disposition="duplicate")
        execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
        if execution is None:
            raise VersionConflictException("Step execution is unavailable")
        if attempt.status not in {"WAITING", "RUNNING"} or execution.status != "WAITING":
            if attempt.status in {"WAITING", "RUNNING"}:
                attempt.status = "CANCELLED"
                attempt.ended_at = get_datetime_utc()
            return AutomationResult(attempt_id=attempt_id, disposition="late_ignored")
        task_execution = (
            await session.exec(
                select(TaskExecutionEntity).where(TaskExecutionEntity.task_id == str(attempt_id))
            )
        ).one_or_none()
        if task_execution is not None:
            attempt.task_execution_id = task_execution.id
        attempt.status = "RUNNING"
        snapshot = AutomationSnapshot.model_validate(attempt.automation_snapshot)

    async with SessionFactory() as session:
        actor = await session.get(UserEntity, snapshot.actor_id)
        if actor is None or actor.deleted_at is not None:
            raise VersionConflictException("Background execution principal is unavailable")
        if snapshot.handler_fingerprint is None:
            if snapshot.connection is None:
                raise VersionConflictException("Background connection pin is unavailable")
            result = await ConnectionService(session, provider or _provider()).execute(
                snapshot.connection, actor
            )
            outputs = {"result": result.model_dump(mode="json")}
            outcome = None
        else:
            registry = get_registry()
            handler = registry.resolve(snapshot.handler_key, snapshot.handler_version)
            if handler.fingerprint != snapshot.handler_fingerprint:
                raise VersionConflictException("Background handler contract differs from dispatch")
            step = await session.get(WorkflowStepEntity, execution.workflow_step_id)
            version = (
                await session.get(StepTypeVersionEntity, step.step_type_version_id)
                if step is not None
                else None
            )
            process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
            if step is None or version is None or process is None:
                raise VersionConflictException("Background step contract is unavailable")
            await StepTypeService(session, registry).registered_handler(version)
            context = StepInvocationContext(
                actor_id=actor.id,
                process_id=process.id,
                request_id=process.business_request_id,
                execution_id=execution.id,
                attempt_id=attempt_id,
                idempotency_key=str(attempt_id),
                inputs=execution.input_snapshot or {},
                services=ProcessStepServices(
                    session,
                    actor_id=actor.id,
                    process_id=process.id,
                    request_id=process.business_request_id,
                    connection_pin=snapshot.connection,
                    provider=provider or _provider(),
                    ai_snapshot=snapshot,
                ),
                cancelled=lambda: execution.status != "WAITING",
            )
            from apps.ai.application.approval_service import AIExecutionDeferred

            try:
                step_result = await registry.invoke(
                    snapshot.handler_key, snapshot.handler_version, step.config, context
                )
            except AIExecutionDeferred as deferred:
                return AutomationResult(attempt_id=attempt_id, disposition=deferred.disposition)
            outputs = step_result.outputs
            outcome = step_result.outcome
    from apps.processes.application.service import ProcessService

    async with SessionFactory() as session, session.begin():
        disposition = await ProcessService(session).complete_background(
            attempt_id, outputs, outcome=outcome
        )
    return AutomationResult(attempt_id=attempt_id, disposition=disposition)


async def fail_background(attempt_id: UUID, code: str) -> AutomationResult:
    """Apply a redacted terminal failure after the registered retry budget is exhausted."""
    from apps.processes.application.service import ProcessService

    async with SessionFactory() as session, session.begin():
        disposition = await ProcessService(session).fail_background(attempt_id, code)
    return AutomationResult(attempt_id=attempt_id, disposition=disposition)
