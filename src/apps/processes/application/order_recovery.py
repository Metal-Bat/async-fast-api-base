"""Authorized receipt lookup through existing process events and attempt evidence."""

import hashlib
from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.integrations.application.orders import OrderOutcomeUnknown, OrderPreDispatchFailure
from apps.integrations.application.providers import OrderProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.orders import payload_hash
from apps.processes.application.events import ProcessEventService
from apps.processes.application.orders import ProtectedOrderDispatch, SessionSource
from apps.processes.application.recovery import ProcessRecoveryService
from apps.processes.domain.automation import AutomationSnapshot
from apps.processes.domain.dtos.orders import (
    OrderReconciliationDTO,
    SandboxCancellationRecoveryDTO,
    SandboxOperationDTO,
)
from apps.processes.domain.entity import (
    CompensationRecordEntity,
    ProcessEventEntity,
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    NotAllowedException,
    NotFoundException,
    ServiceUnavailableException,
    VersionConflictException,
)
from utils.pagination import Page, PageRequest


class OrderRecoveryService:
    def __init__(
        self, sessions: SessionSource = SessionFactory, provider: OrderProvider | None = None
    ) -> None:
        from apps.processes.application.automation import _provider

        self.sessions = sessions
        self.provider = provider or _provider()

    async def _operator(self, session: AsyncSession, actor_id: UUID) -> UserEntity:
        actor = await session.get(UserEntity, actor_id, populate_existing=True)
        if actor is None:
            raise NotAllowedException("Only superusers may recover processes")
        ProcessRecoveryService._authorize(actor)
        return actor

    async def _attempt(self, session: AsyncSession, process_id: UUID, execution_id: UUID):
        execution = await session.get(
            StepExecutionEntity, execution_id, with_for_update=True, populate_existing=True
        )
        if execution is None or execution.process_instance_id != process_id:
            raise NotFoundException("Step execution not found")
        attempt = (
            await session.exec(
                select(StepExecutionAttemptEntity)
                .where(StepExecutionAttemptEntity.step_execution_id == execution.id)
                .order_by(col(StepExecutionAttemptEntity.number).desc())
                .limit(1)
                .with_for_update()
            )
        ).one_or_none()
        if attempt is None:
            raise NotFoundException("Sandbox operation not found")
        snapshot = AutomationSnapshot.model_validate(attempt.automation_snapshot)
        if snapshot.operation_key != "sandbox.order.create/1" or snapshot.order_dispatch is None:
            raise NotFoundException("Sandbox operation not found")
        return execution, attempt, snapshot

    async def _publisher(self, session: AsyncSession, snapshot: AutomationSnapshot) -> None:
        actor = await session.get(UserEntity, snapshot.actor_id, populate_existing=True)
        if (
            actor is None
            or actor.deleted_at is not None
            or actor.is_superuser
            or "workflows.manage" not in await user_permissions(actor, session)
        ):
            raise VersionConflictException("Protected publisher authority was revoked")
        if snapshot.connection is None:
            raise VersionConflictException("Protected connection pin is unavailable")
        await ConnectionService(session, self.provider).recheck_service(snapshot.connection, actor)

    @staticmethod
    def _projection(
        execution: StepExecutionEntity, snapshot: AutomationSnapshot
    ) -> SandboxOperationDTO:
        dispatch = snapshot.order_dispatch
        if dispatch is None:
            raise NotFoundException("Sandbox operation not found")
        return SandboxOperationDTO(
            step_execution_ref_id=create_ref_id(execution.id, execution.version),
            operation_id=dispatch.operation_id,
            state=dispatch.state,
            receipt=dispatch.receipt,
        )

    async def search(
        self, session: AsyncSession, process_id: UUID, query: PageRequest
    ) -> Page[SandboxOperationDTO]:
        """One current attempt per logical operation; caller owns participant authorization."""
        latest = (
            select(func.max(StepExecutionAttemptEntity.number))
            .where(StepExecutionAttemptEntity.step_execution_id == col(StepExecutionEntity.id))
            .correlate(StepExecutionEntity)
            .scalar_subquery()
        )
        statement = (
            select(StepExecutionAttemptEntity, StepExecutionEntity)
            .join(
                StepExecutionEntity,
                col(StepExecutionEntity.id) == col(StepExecutionAttemptEntity.step_execution_id),
            )
            .where(
                StepExecutionEntity.process_instance_id == process_id,
                col(StepExecutionAttemptEntity.automation_snapshot).op("->>")("operation_key")
                == "sandbox.order.create/1",
                StepExecutionAttemptEntity.number == latest,
            )
        )
        total = (await session.exec(select(func.count()).select_from(statement.subquery()))).one()
        rows = (
            await session.exec(
                statement.order_by(col(StepExecutionEntity.created_at), col(StepExecutionEntity.id))
                .offset((query.page - 1) * query.size)
                .limit(query.size)
            )
        ).all()
        return Page[SandboxOperationDTO](
            page=query.page,
            size=query.size,
            total=total,
            items=[
                self._projection(
                    execution, AutomationSnapshot.model_validate(attempt.automation_snapshot)
                )
                for attempt, execution in rows
            ],
        )

    async def reconcile(
        self, process_ref: str, data: OrderReconciliationDTO, actor_id: UUID
    ) -> SandboxOperationDTO:
        process_id, expected_process = open_ref_id(process_ref)
        execution_id, expected_execution = open_ref_id(data.step_execution_ref_id)
        command_key = "order-lookup:" + hashlib.sha256(data.command_key.encode()).hexdigest()
        intent_hash = payload_hash(
            {**data.model_dump(), "process": str(process_id), "actor": str(actor_id)}
        )
        async with self.sessions() as session, session.begin():
            actor = await self._operator(session, actor_id)
            process = await session.get(
                ProcessInstanceEntity, process_id, with_for_update=True, populate_existing=True
            )
            if process is None:
                raise NotFoundException("Process not found")
            existing = (
                await session.exec(
                    select(ProcessEventEntity).where(
                        ProcessEventEntity.process_instance_id == process.id,
                        ProcessEventEntity.command_key == command_key,
                        ProcessEventEntity.event_type == "operation.reconciliation_started",
                    )
                )
            ).one_or_none()
            if existing is not None:
                if existing.public_payload.get("intent_hash") != intent_hash:
                    raise VersionConflictException(
                        "Recovery command key was reused with different intent"
                    )
                execution, _, snapshot = await self._attempt(session, process_id, execution_id)
                return self._projection(execution, snapshot)
            execution, attempt, snapshot = await self._attempt(session, process_id, execution_id)
            if process.version != expected_process or execution.version != expected_execution:
                raise VersionConflictException("Process or step execution is stale")
            dispatch = snapshot.order_dispatch
            if dispatch is None:
                raise NotFoundException("Sandbox operation not found")
            if dispatch.state == "DISPATCHING":
                if (
                    dispatch.dispatched_at is None
                    or (get_datetime_utc() - dispatch.dispatched_at).total_seconds() < 20
                ):
                    raise VersionConflictException("Sandbox dispatch is still within its deadline")
            elif dispatch.state != "UNKNOWN":
                raise VersionConflictException("Sandbox operation does not require reconciliation")
            await self._publisher(session, snapshot)
            if (
                snapshot.protected_approval is None
                or snapshot.protected_approval.payload_hash
                != payload_hash((execution.input_snapshot or {}).get("payload"))
            ):
                raise VersionConflictException("Protected human approval changed")
            await ProcessEventService(session).append(
                process_id,
                "operation.reconciliation_started",
                actor_user_id=actor.id,
                step_execution_id=execution.id,
                command_key=command_key,
                payload={
                    "operation_id": str(dispatch.operation_id),
                    "reason": data.reason,
                    "intent_hash": intent_hash,
                },
            )
            attempt_id = attempt.id
            pin = snapshot.connection
            if pin is None:
                raise VersionConflictException("Protected connection pin is unavailable")
            operation_id = dispatch.operation_id
            digest = dispatch.payload_hash

        # Lookup has no business side effect and holds no DB session or transaction.
        try:
            receipt = await self.provider.lookup_order(pin, operation_id)
        except OrderOutcomeUnknown, OrderPreDispatchFailure:
            raise ServiceUnavailableException("Sandbox receipt lookup is unavailable") from None
        if receipt is not None and (
            receipt.operation_id != operation_id or receipt.payload_hash != digest
        ):
            raise VersionConflictException("Sandbox receipt differs from the approved operation")
        async with self.sessions() as session, session.begin():
            actor = await self._operator(session, actor_id)
            process = await session.get(
                ProcessInstanceEntity, process_id, with_for_update=True, populate_existing=True
            )
            if process is None:
                raise NotFoundException("Process not found")
            execution, _, current = await self._attempt(session, process_id, execution_id)
            if (
                current.connection != pin
                or current.order_dispatch is None
                or current.order_dispatch.operation_id != operation_id
                or current.order_dispatch.payload_hash != digest
            ):
                raise VersionConflictException("Sandbox operation pin changed during lookup")
            await self._publisher(session, current)
            if (
                current.protected_approval is None
                or current.protected_approval.payload_hash
                != payload_hash((execution.input_snapshot or {}).get("payload"))
            ):
                raise VersionConflictException("Protected human approval changed")
            await ProtectedOrderDispatch(self.sessions, self.provider).record_outcome(
                session, attempt_id, "CONFIRMED" if receipt is not None else "UNKNOWN", receipt
            )
            await ProcessEventService(session).append(
                process_id,
                "operation.reconciled",
                actor_user_id=actor.id,
                step_execution_id=execution.id,
                command_key=command_key + ":result",
                payload={
                    "operation_id": str(operation_id),
                    "receipt_id": str(receipt.receipt_id) if receipt else None,
                    "state": "CONFIRMED" if receipt else "UNKNOWN",
                    "reason": data.reason,
                    "intent_hash": intent_hash,
                },
            )
        async with self.sessions() as session:
            execution, _, current = await self._attempt(session, process_id, execution_id)
            return self._projection(execution, current)

    async def reconcile_cancellation(
        self, process_ref: str, data: OrderReconciliationDTO, actor_id: UUID
    ) -> SandboxCancellationRecoveryDTO:
        """Deliberately requeue receipt lookup through the existing compensation outbox."""
        from apps.processes.application.compensation import CompensationService

        process_id, expected_process = open_ref_id(process_ref)
        execution_id, expected_execution = open_ref_id(data.step_execution_ref_id)
        key = "cancel-lookup:" + hashlib.sha256(data.command_key.encode()).hexdigest()
        intent = payload_hash(
            {**data.model_dump(), "process": str(process_id), "actor": str(actor_id)}
        )
        async with self.sessions() as session, session.begin():
            actor = await self._operator(session, actor_id)
            process = await session.get(
                ProcessInstanceEntity, process_id, with_for_update=True, populate_existing=True
            )
            if process is None:
                raise NotFoundException("Process not found")
            execution, _, snapshot = await self._attempt(session, process_id, execution_id)
            record = (
                await session.exec(
                    select(CompensationRecordEntity)
                    .where(
                        CompensationRecordEntity.process_instance_id == process_id,
                        CompensationRecordEntity.source_execution_id == execution_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if record is None:
                raise NotFoundException("Compensation record not found")
            existing = (
                await session.exec(
                    select(ProcessEventEntity).where(
                        ProcessEventEntity.process_instance_id == process_id,
                        ProcessEventEntity.event_type == "compensation.reconciliation_requested",
                        ProcessEventEntity.command_key == key,
                    )
                )
            ).one_or_none()
            if existing is not None:
                if existing.public_payload.get("intent_hash") != intent:
                    raise VersionConflictException(
                        "Recovery command key was reused with different intent"
                    )
            else:
                if process.version != expected_process or execution.version != expected_execution:
                    raise VersionConflictException("Process or step execution is stale")
                await self._publisher(session, snapshot)
                started = (
                    await session.exec(
                        select(ProcessEventEntity).where(
                            ProcessEventEntity.process_instance_id == process_id,
                            ProcessEventEntity.event_type == "compensation.dispatch_started",
                            ProcessEventEntity.command_key == "sandbox-reversal:" + str(record.id),
                        )
                    )
                ).one_or_none()
                if started is None:
                    raise VersionConflictException("Sandbox cancellation has no uncertain dispatch")
                if (
                    record.status == "EXECUTING"
                    and (get_datetime_utc() - started.occurred_at).total_seconds() < 20
                ):
                    raise VersionConflictException("Sandbox dispatch is still within its deadline")
                service = CompensationService(session)
                if record.status == "FAILED":
                    await service.retry_failed(record.id)
                elif record.status in {"RUNNING", "EXECUTING"}:
                    await service.recover_running(record.id)
                else:
                    raise VersionConflictException(
                        "Sandbox cancellation does not require reconciliation"
                    )
                await ProcessEventService(session).append(
                    process_id,
                    "compensation.reconciliation_requested",
                    actor_user_id=actor.id,
                    step_execution_id=execution_id,
                    command_key=key,
                    payload={"reason": data.reason, "intent_hash": intent},
                )
                await service.begin(process_id, key + ":dispatch", actor.id)
            return SandboxCancellationRecoveryDTO(
                step_execution_ref_id=create_ref_id(execution.id, execution.version),
                status=record.status,
            )
