"""Registered sandbox reversal behind the existing compensation record/state machine."""

from uuid import UUID, uuid5

from sqlmodel import col, select

from apps.integrations.application.orders import OrderOutcomeUnknown
from apps.integrations.application.providers import CancellationProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.orders import ORDER_CANCELLATION_OPERATION, SandboxOrderReceipt
from apps.processes.application.events import ProcessEventService
from apps.processes.application.orders import SessionSource
from apps.processes.domain.automation import AutomationSnapshot
from apps.processes.domain.entity import (
    CompensationRecordEntity,
    ProcessEventEntity,
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.step_types.application.automation import resolve_operation
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeVersionEntity
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowStepEntity
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException


async def compensate_order(
    record_id: UUID, sessions: SessionSource, provider: CancellationProvider
) -> str:
    from apps.processes.application.compensation import CompensationService

    async with sessions() as session, session.begin():
        record = await session.get(CompensationRecordEntity, record_id)
        if record is None:
            raise NotFoundException("Compensation record not found")
        process = await session.get(
            ProcessInstanceEntity,
            record.process_instance_id,
            with_for_update=True,
            populate_existing=True,
        )
        record = await session.get(
            CompensationRecordEntity, record_id, with_for_update=True, populate_existing=True
        )
        if record is None:
            raise NotFoundException("Compensation record not found")
        if record.status == "COMPLETED":
            return "duplicate"
        if (
            process is None
            or process.status not in {"COMPENSATING", "COMPENSATION_FAILED"}
            or record.status not in {"RUNNING", "EXECUTING"}
        ):
            raise VersionConflictException("Sandbox compensation is not running")
        step = await session.get(WorkflowStepEntity, record.compensation_step_id)
        source = await session.get(StepExecutionEntity, record.source_execution_id)
        version = (
            await session.get(StepTypeVersionEntity, step.step_type_version_id) if step else None
        )
        if (
            step is None
            or source is None
            or version is None
            or step.workflow_version_id != process.workflow_version_id
            or step.config.get("operation_key") != ORDER_CANCELLATION_OPERATION
            or not bool((step.flow or {}).get("compensation_only"))
        ):
            raise VersionConflictException("Sandbox compensation contract is unavailable")
        handler = await StepTypeService(session, get_registry()).registered_handler(version)
        resolve_operation(
            ORDER_CANCELLATION_OPERATION,
            handler.handler_key,
            handler.handler_version,
            execution_scope="COMPENSATION",
        )
        prior = (
            await session.exec(
                select(StepExecutionAttemptEntity)
                .where(StepExecutionAttemptEntity.step_execution_id == source.id)
                .order_by(col(StepExecutionAttemptEntity.number).desc())
                .limit(1)
            )
        ).one_or_none()
        if prior is None:
            raise VersionConflictException("Sandbox original effect is unavailable")
        snapshot = AutomationSnapshot.model_validate(prior.automation_snapshot)
        dispatch = snapshot.order_dispatch
        if (
            snapshot.operation_key != "sandbox.order.create/1"
            or dispatch is None
            or dispatch.state != "CONFIRMED"
            or dispatch.receipt is None
            or dispatch.receipt.state != "CREATED"
            or snapshot.connection is None
            or snapshot.protected_approval is None
        ):
            raise VersionConflictException("Sandbox original receipt requires reconciliation")
        original = SandboxOrderReceipt.model_validate(dispatch.receipt)
        pin = snapshot.connection
        if step.config.get("connection_ref") != pin.connection_ref:
            raise VersionConflictException("Sandbox reversal cannot substitute a connection")
        actor = await session.get(UserEntity, snapshot.actor_id, populate_existing=True)
        if (
            actor is None
            or actor.deleted_at is not None
            or actor.is_superuser
            or "workflows.manage" not in await user_permissions(actor, session)
        ):
            raise VersionConflictException("Protected publisher authority was revoked")
        await ConnectionService(session, provider).recheck_service(pin, actor)
        operation_id = uuid5(record.id, ORDER_CANCELLATION_OPERATION)
        key = "sandbox-reversal:" + str(record.id)
        existing = (
            await session.exec(
                select(ProcessEventEntity).where(
                    ProcessEventEntity.process_instance_id == process.id,
                    ProcessEventEntity.event_type == "compensation.dispatch_started",
                    ProcessEventEntity.command_key == key,
                )
            )
        ).one_or_none()
        lookup_only = existing is not None
        if (
            existing is not None
            and record.status == "EXECUTING"
            and (get_datetime_utc() - existing.occurred_at).total_seconds() < 20
        ):
            return "duplicate_in_flight"
        record.status = "EXECUTING"
        if not lookup_only:
            await ProcessEventService(session).append(
                process.id,
                "compensation.dispatch_started",
                step_execution_id=source.id,
                command_key=key,
                payload={
                    "operation_id": str(operation_id),
                    "order_operation_id": str(original.operation_id),
                },
            )
        process_id = process.id
        source_id = source.id

    # A repeated/crashed dispatch may only look up the original reversal receipt.
    receipt = (
        await provider.lookup_cancellation(pin, operation_id, original)
        if lookup_only
        else await provider.cancel_order(pin, operation_id, original)
    )
    if (
        receipt is None
        or receipt.operation_id != operation_id
        or receipt.order_operation_id != original.operation_id
        or receipt.payload_hash != original.payload_hash
    ):
        raise OrderOutcomeUnknown("Sandbox cancellation requires reconciliation")
    async with sessions() as session, session.begin():
        await session.get(
            ProcessInstanceEntity, process_id, with_for_update=True, populate_existing=True
        )
        record = await session.get(
            CompensationRecordEntity, record_id, with_for_update=True, populate_existing=True
        )
        if record is None:
            raise NotFoundException("Compensation record not found")
        if record.status == "COMPLETED":
            return "duplicate"
        if record.status != "EXECUTING":
            raise VersionConflictException("Sandbox compensation changed during dispatch")
        await ProcessEventService(session).append(
            process_id,
            "compensation.receipt_confirmed",
            step_execution_id=source_id,
            command_key=key + ":receipt",
            payload={
                "operation_id": str(receipt.operation_id),
                "order_operation_id": str(receipt.order_operation_id),
                "receipt_id": str(receipt.receipt_id),
                "state": receipt.state,
            },
        )
        await CompensationService(session).complete(record_id, f"worker:{record_id}")
    return "completed"
