"""Approval-fenced sandbox dispatch using the existing attempt and process owner."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID, uuid5

from anyio import CancelScope, get_cancelled_exc_class
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.integrations.application.orders import OrderOutcomeUnknown, OrderPreDispatchFailure
from apps.integrations.application.providers import OrderProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.orders import (
    PROTECTED_ORDER_OPERATION,
    SandboxOrderPayload,
    SandboxOrderReceipt,
    payload_hash,
)
from apps.processes.application.approval import ProtectedEffectApproval
from apps.processes.application.events import ProcessEventService
from apps.processes.domain.automation import (
    AutomationResult,
    AutomationSnapshot,
    OrderDispatchEvidence,
    OrderDispatchState,
)
from apps.processes.domain.entity import (
    ExecutionTokenEntity,
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.users.application import authorization
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowStepEntity
from utils.date_utils import get_datetime_utc
from utils.exceptions import ServiceUnavailableException, VersionConflictException

SessionSource = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class ProtectedOrderDispatch:
    def __init__(self, sessions: SessionSource, provider: OrderProvider) -> None:
        self.sessions = sessions
        self.provider = provider

    async def _locked(self, session: AsyncSession, attempt_id: UUID):
        # Match process commands: process first, then token/execution/attempt.
        attempt = await session.get(StepExecutionAttemptEntity, attempt_id)
        execution = (
            await session.get(StepExecutionEntity, attempt.step_execution_id) if attempt else None
        )
        if attempt is None or execution is None:
            raise VersionConflictException("Background attempt is unavailable")
        process = await session.get(
            ProcessInstanceEntity,
            execution.process_instance_id,
            with_for_update=True,
            populate_existing=True,
        )
        token = await session.get(
            ExecutionTokenEntity,
            execution.execution_token_id,
            with_for_update=True,
            populate_existing=True,
        )
        execution = await session.get(
            StepExecutionEntity, execution.id, with_for_update=True, populate_existing=True
        )
        attempt = await session.get(
            StepExecutionAttemptEntity, attempt_id, with_for_update=True, populate_existing=True
        )
        if process is None or token is None or execution is None or attempt is None:
            raise VersionConflictException("Background attempt is unavailable")
        return process, token, execution, attempt

    async def execute(self, attempt_id: UUID) -> AutomationResult:
        def result(disposition: str) -> AutomationResult:
            return AutomationResult(attempt_id=attempt_id, disposition=disposition)

        async with self.sessions() as session, session.begin():
            process, token, execution, attempt = await self._locked(session, attempt_id)
            if attempt.status == "SUCCEEDED":
                return result("duplicate")
            if (
                process.status != "WAITING"
                or token.status != "WAITING"
                or execution.status != "WAITING"
                or attempt.status not in {"WAITING", "RUNNING"}
            ):
                if attempt.status in {"WAITING", "RUNNING"}:
                    attempt.status = "CANCELLED"
                    attempt.ended_at = get_datetime_utc()
                return result("late_ignored")
            snapshot = AutomationSnapshot.model_validate(attempt.automation_snapshot)
            if snapshot.protected_approval is None or snapshot.connection is None:
                raise VersionConflictException(
                    "Protected operation requires matching human approval"
                )
            actor = await session.get(UserEntity, snapshot.actor_id, populate_existing=True)
            if actor is None or actor.deleted_at is not None or actor.is_superuser:
                raise VersionConflictException(
                    "Protected execution requires an active ordinary publisher"
                )
            if "workflows.manage" not in await authorization.user_permissions(actor, session):
                raise VersionConflictException("Protected publisher authority was revoked")
            step = await session.get(WorkflowStepEntity, execution.workflow_step_id)
            if (
                step is None
                or step.config.get("operation_key") != PROTECTED_ORDER_OPERATION
                or step.config.get("connection_ref") != snapshot.connection.connection_ref
            ):
                raise VersionConflictException("Protected operation contract changed")
            evidence = await ProtectedEffectApproval(session).capture(execution, step)
            if evidence != snapshot.protected_approval:
                raise VersionConflictException("Protected human approval changed")
            await ConnectionService(session, self.provider).recheck_service(
                snapshot.connection, actor
            )
            if (
                snapshot.connection.provider != "https_sandbox_orders"
                or snapshot.connection.kind != "SERVICE"
            ):
                raise VersionConflictException("Protected sandbox connection is unavailable")
            payload = SandboxOrderPayload.model_validate(
                (execution.input_snapshot or {}).get("payload")
            )
            identity = uuid5(execution.id, PROTECTED_ORDER_OPERATION)
            digest = payload_hash(payload.model_dump(mode="json"))
            dispatch = snapshot.order_dispatch or OrderDispatchEvidence(
                operation_id=identity, payload_hash=digest
            )
            if dispatch.operation_id != identity or dispatch.payload_hash != digest:
                raise VersionConflictException("Protected operation payload changed")
            if dispatch.state in {"DISPATCHING", "UNKNOWN"}:
                return result("operation_unknown")
            if dispatch.state == "CONFIRMED":
                if dispatch.receipt is None:
                    raise VersionConflictException("Protected receipt is unavailable")
                return result(await self._complete(session, attempt_id, dispatch.receipt))
            dispatch.state = "DISPATCHING"
            dispatch.dispatched_at = get_datetime_utc()
            snapshot.order_dispatch = dispatch
            attempt.automation_snapshot = snapshot.model_dump(mode="json")
            attempt.status = "RUNNING"
            await ProcessEventService(session).append(
                process.id,
                "operation.dispatch_started",
                step_execution_id=execution.id,
                payload={"operation_id": str(identity), "operation": PROTECTED_ORDER_OPERATION},
            )

        # No database session or transaction survives the network call.
        try:
            receipt = await self.provider.create_order(snapshot.connection, identity, payload)
            if (
                receipt.operation_id != identity
                or receipt.payload_hash != digest
                or receipt.state != "CREATED"
            ):
                raise OrderOutcomeUnknown("Sandbox receipt requires reconciliation")
        except OrderPreDispatchFailure:
            await self._record(attempt_id, "PREPARED")
            raise ServiceUnavailableException(
                "Sandbox operation is unavailable before dispatch"
            ) from None
        except get_cancelled_exc_class():
            with CancelScope(shield=True):
                await self._record(attempt_id, "UNKNOWN")
            raise
        except Exception:  # noqa: BLE001 -- Unknown external outcomes cannot be blindly retried.
            await self._record(attempt_id, "UNKNOWN")
            return result("operation_unknown")
        return result(await self._record(attempt_id, "CONFIRMED", receipt))

    async def _record(
        self,
        attempt_id: UUID,
        state: OrderDispatchState,
        receipt: SandboxOrderReceipt | None = None,
    ) -> str:
        async with self.sessions() as session, session.begin():
            return await self.record_outcome(session, attempt_id, state, receipt)

    async def record_outcome(
        self,
        session: AsyncSession,
        attempt_id: UUID,
        state: OrderDispatchState,
        receipt: SandboxOrderReceipt | None = None,
    ) -> str:
        process, _, execution, attempt = await self._locked(session, attempt_id)
        snapshot = AutomationSnapshot.model_validate(attempt.automation_snapshot)
        dispatch = snapshot.order_dispatch
        if dispatch is None:
            raise VersionConflictException("Protected operation evidence is unavailable")
        # An operator or duplicate delivery cannot erase a confirmed receipt.
        if dispatch.state == "CONFIRMED":
            return "duplicate"
        dispatch.state = state
        dispatch.receipt = receipt
        attempt.automation_snapshot = snapshot.model_dump(mode="json")
        if state == "PREPARED":
            return "pre_dispatch_failure"
        event = "operation.confirmed" if receipt else "operation.outcome_unknown"
        await ProcessEventService(session).append(
            process.id,
            event,
            step_execution_id=execution.id,
            payload={
                "operation_id": str(dispatch.operation_id),
                "receipt_id": str(receipt.receipt_id) if receipt else None,
                "state": state,
            },
        )
        if state == "UNKNOWN":
            if execution.status == "WAITING":
                execution.last_error_code = "operation.outcome.unknown"
            return "operation_unknown"
        if receipt is None:
            raise VersionConflictException("Protected receipt is unavailable")
        if receipt.state == "CANCELLED":
            from apps.processes.application.service import ProcessService

            return await ProcessService(session).fail_background(
                attempt_id, "operation.externally.cancelled"
            )
        return await self._complete(session, attempt_id, receipt)

    @staticmethod
    async def _complete(
        session: AsyncSession, attempt_id: UUID, receipt: SandboxOrderReceipt
    ) -> str:
        from apps.processes.application.service import ProcessService

        return await ProcessService(session).complete_background(
            attempt_id, {"result": receipt.model_dump(mode="json")}
        )
