"""Durable, idempotent orchestration of explicit external-effect reversal."""

from uuid import UUID, uuid7

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.application.events import ProcessEventService
from apps.processes.domain.entity import (
    CompensationRecordEntity,
    ProcessInstanceEntity,
    StepExecutionEntity,
)
from apps.requests.domain.entity import BusinessRequestEntity
from apps.step_types.application.registry import ServiceConfig, get_registry
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.tasks.application.outbox import enqueue_task
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowStepEntity, WorkflowVersionEntity
from core.deps import SessionFactory
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException


class CompensationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def begin(
        self, process_id: UUID, command_key: str, actor_user_id: UUID | None = None
    ) -> CompensationRecordEntity | None:
        process = await self.session.get(
            ProcessInstanceEntity, process_id, with_for_update=True, populate_existing=True
        )
        if process is None:
            raise NotFoundException("Process not found")
        if process.status == "COMPENSATED":
            return None
        duplicate = (
            await self.session.exec(
                select(CompensationRecordEntity).where(
                    CompensationRecordEntity.process_instance_id == process_id,
                    CompensationRecordEntity.dispatch_key == command_key,
                )
            )
        ).one_or_none()
        if duplicate is not None:
            return duplicate
        if process.status not in {"FAILED", "CANCELLED", "COMPENSATING", "COMPENSATION_FAILED"}:
            raise VersionConflictException("Process cannot be compensated from its current state")
        if process.status == "COMPENSATION_FAILED":
            raise VersionConflictException("Failed compensation requires an explicit record retry")
        process.status = "COMPENSATING"
        process.ended_at = None
        record = (
            await self.session.exec(
                select(CompensationRecordEntity)
                .where(
                    CompensationRecordEntity.process_instance_id == process_id,
                    CompensationRecordEntity.status == "PENDING",
                )
                .order_by(col(CompensationRecordEntity.ordinal).desc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
        ).one_or_none()
        if record is None:
            running = (
                await self.session.exec(
                    select(CompensationRecordEntity).where(
                        CompensationRecordEntity.process_instance_id == process_id,
                        col(CompensationRecordEntity.status).in_(["RUNNING", "EXECUTING"]),
                    )
                )
            ).one_or_none()
            if running is not None:
                return running
            process.status = "COMPENSATED"
            process.ended_at = get_datetime_utc()
            await ProcessEventService(self.session).append(
                process.id,
                "process.compensated",
                actor_user_id=actor_user_id,
                payload={"status": process.status},
            )
            return None
        record.status = "RUNNING"
        record.dispatch_key = command_key
        await ProcessEventService(self.session).append(
            process.id,
            "compensation.started",
            actor_user_id=actor_user_id,
            step_execution_id=record.source_execution_id,
            command_key=command_key,
            payload={"ordinal": record.ordinal},
        )
        enqueue_task(
            self.session,
            "bpms.execute_compensation",
            kwargs={"record_id": str(record.id)},
            task_id=str(uuid7()),
            idempotency_key=f"compensation:{record.id}:{command_key}",
            queue=settings.CELERY_AUTOMATION_QUEUE,
        )
        return record

    async def complete(self, record_id: UUID, command_key: str) -> CompensationRecordEntity | None:
        record = await self.session.get(
            CompensationRecordEntity, record_id, with_for_update=True, populate_existing=True
        )
        if record is None:
            raise NotFoundException("Compensation record not found")
        if record.status == "COMPLETED":
            return await self.begin(record.process_instance_id, f"{command_key}:next")
        if record.status not in {"RUNNING", "EXECUTING"}:
            raise VersionConflictException("Compensation record is not running")
        record.status = "COMPLETED"
        record.completed_at = get_datetime_utc()
        await ProcessEventService(self.session).append(
            record.process_instance_id,
            "compensation.completed",
            step_execution_id=record.source_execution_id,
            payload={"ordinal": record.ordinal},
        )
        return await self.begin(record.process_instance_id, f"{command_key}:next")

    async def fail(self, record_id: UUID, code: str) -> None:
        record = await self.session.get(
            CompensationRecordEntity, record_id, with_for_update=True, populate_existing=True
        )
        if record is None:
            raise NotFoundException("Compensation record not found")
        if record.status == "COMPLETED":
            return
        record.status = "FAILED"
        record.last_error_code = code
        process = await self.session.get(ProcessInstanceEntity, record.process_instance_id)
        if process is None:
            raise NotFoundException("Process not found")
        process.status = "COMPENSATION_FAILED"
        process.last_error_code = code
        process.ended_at = get_datetime_utc()
        await ProcessEventService(self.session).append(
            process.id,
            "compensation.failed",
            step_execution_id=record.source_execution_id,
            payload={"ordinal": record.ordinal, "error_code": code, "manual_intervention": True},
        )

    async def retry_failed(self, record_id: UUID) -> None:
        record = await self.session.get(
            CompensationRecordEntity, record_id, with_for_update=True, populate_existing=True
        )
        if record is None:
            raise NotFoundException("Compensation record not found")
        if record.status != "FAILED":
            raise VersionConflictException("Compensation record is not failed")
        record.status = "PENDING"
        record.dispatch_key = None
        record.last_error_code = None
        process = await self.session.get(ProcessInstanceEntity, record.process_instance_id)
        if process is None:
            raise NotFoundException("Process not found")
        process.status = "COMPENSATING"
        process.ended_at = None
        process.last_error_code = None

    async def recover_running(self, record_id: UUID) -> None:
        """Explicitly requeue an effect whose external outcome was reconciled as not applied."""
        record = await self.session.get(
            CompensationRecordEntity, record_id, with_for_update=True, populate_existing=True
        )
        if record is None:
            raise NotFoundException("Compensation record not found")
        if record.status not in {"RUNNING", "EXECUTING"}:
            raise VersionConflictException("Compensation record is not running")
        record.status = "PENDING"
        record.dispatch_key = None
        record.last_error_code = "compensation.recovered"
        process = await self.session.get(ProcessInstanceEntity, record.process_instance_id)
        if process is None:
            raise NotFoundException("Process not found")
        process.status = "COMPENSATING"
        process.ended_at = None
        process.last_error_code = None


async def execute_compensation(record_id: UUID) -> None:
    """Execute one claimed reversal, leaving external rollback explicit and idempotent."""
    from apps.integrations.application.service import ConnectionService
    from apps.processes.application.automation import _provider
    from apps.step_types.application.automation import resolve_operation

    async with SessionFactory() as session, session.begin():
        record = await session.get(
            CompensationRecordEntity, record_id, with_for_update=True, populate_existing=True
        )
        if record is None:
            raise NotFoundException("Compensation record not found")
        if record.status == "COMPLETED":
            return
        if record.status != "RUNNING":
            raise VersionConflictException("Compensation record is not running")
        record.status = "EXECUTING"
        await session.flush()
        process = await session.get(ProcessInstanceEntity, record.process_instance_id)
        step = await session.get(WorkflowStepEntity, record.compensation_step_id)
        source = await session.get(StepExecutionEntity, record.source_execution_id)
        if process is None or step is None or source is None:
            raise VersionConflictException("Compensation definition is unavailable")
        definition_row = (
            await session.exec(
                select(StepTypeEntity, StepTypeVersionEntity)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
                )
                .where(StepTypeVersionEntity.id == step.step_type_version_id)
            )
        ).one()
        step_type, version = definition_row
        handler = get_registry().resolve(version.handler_key, version.handler_version)
        if step_type.code == "TRANSFORM":
            config = get_registry().validate_config(
                version.handler_key, version.handler_version, step.config
            )
            get_registry().execute_transform(
                handler.handler_key,
                handler.handler_version,
                config,
                source.output_snapshot,
            )
            external = None
            actor = None
        elif step_type.code == "SERVICE_TASK":
            config = ServiceConfig.model_validate(step.config)
            resolve_operation(config.operation_key, handler.handler_key, handler.handler_version)
            workflow = await session.get(WorkflowVersionEntity, process.workflow_version_id)
            request = await session.get(BusinessRequestEntity, process.business_request_id)
            actor = (
                await session.get(UserEntity, workflow.published_by_user_id)
                if workflow is not None and workflow.published_by_user_id is not None
                else None
            )
            if actor is None or request is None:
                raise VersionConflictException("Compensation principal is unavailable")
            provider = _provider()
            external = (
                provider,
                await ConnectionService(session, provider).pin(
                    config.connection_ref,
                    actor,
                    handler_key=handler.handler_key,
                    handler_version=handler.handler_version,
                ),
            )
        else:
            raise VersionConflictException("Compensation handler type is unsupported")

    if external is not None and actor is not None:
        provider, snapshot = external
        async with SessionFactory() as session:
            stored_actor = await session.get(UserEntity, actor.id)
            if stored_actor is None:
                raise VersionConflictException("Compensation principal is unavailable")
            await ConnectionService(session, provider).execute(snapshot, stored_actor)

    async with SessionFactory() as session, session.begin():
        await CompensationService(session).complete(record_id, f"worker:{record_id}")


async def fail_compensation(record_id: UUID, code: str) -> None:
    async with SessionFactory() as session, session.begin():
        await CompensationService(session).fail(record_id, code)
