"""Read existing protected evidence and authority; never dispatch or reconcile an effect."""

from dataclasses import dataclass
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.integrations.domain.orders import (
    PROTECTED_ORDER_OPERATION,
    SandboxOrderPayload,
    payload_hash,
)
from apps.processes.domain.automation import AutomationSnapshot
from apps.processes.domain.entity import (
    ProcessEventEntity,
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.requests.application.service import RequestService
from apps.requests.domain.entity import BusinessRequestEntity
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from core.ref_id import create_ref_id


@dataclass(frozen=True)
class OperationNotice:
    map_id: str
    occurrence_id: UUID
    execution_id: UUID


async def evidence(session: AsyncSession, execution_id: UUID):
    execution = await session.get(StepExecutionEntity, execution_id, populate_existing=True)
    if execution is None:
        return None
    attempt = (
        await session.exec(
            select(StepExecutionAttemptEntity)
            .where(
                StepExecutionAttemptEntity.step_execution_id == execution.id,
            )
            .order_by(col(StepExecutionAttemptEntity.number).desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
    ).first()
    if attempt is None:
        return None
    try:
        snapshot = AutomationSnapshot.model_validate(attempt.automation_snapshot)
    except ValidationError:
        return None
    dispatch = snapshot.order_dispatch
    if snapshot.operation_key != PROTECTED_ORDER_OPERATION or dispatch is None:
        return None
    try:
        payload = SandboxOrderPayload.model_validate(
            (execution.input_snapshot or {}).get("payload")
        )
    except ValidationError:
        return None
    if dispatch.payload_hash != payload_hash(payload.model_dump(mode="json")):
        return None
    return execution, attempt, dispatch


def notice_kind(attempt: StepExecutionAttemptEntity, dispatch) -> str | None:
    if dispatch.state == "UNKNOWN" and dispatch.receipt is None:
        return "MAP-07"
    if dispatch.state == "PREPARED" and attempt.status in {"FAILED", "TIMED_OUT"}:
        return "MAP-07"
    receipt = dispatch.receipt
    if (
        dispatch.state == "CONFIRMED"
        and receipt is not None
        and receipt.state == "CREATED"
        and receipt.operation_id == dispatch.operation_id
        and receipt.payload_hash == dispatch.payload_hash
    ):
        return "MAP-08"
    return None


async def event_notice(session: AsyncSession, event: ProcessEventEntity) -> OperationNotice | None:
    if event.step_execution_id is None:
        return None
    current = await evidence(session, event.step_execution_id)
    if current is None:
        return None
    execution, attempt, dispatch = current
    if execution.process_instance_id != event.process_instance_id:
        return None
    kind = notice_kind(attempt, dispatch)
    payload = event.public_payload or {}
    if event.event_type == "automation.failed":
        if (
            kind != "MAP-07"
            or dispatch.state != "PREPARED"
            or payload.get("attempt") != attempt.number
        ):
            return None
        occurrence = uuid5(attempt.id, "operation-failed-before-dispatch")
    else:
        if payload.get("operation_id") != str(dispatch.operation_id):
            return None
        if event.event_type == "operation.outcome_unknown":
            if kind != "MAP-07" or dispatch.state != "UNKNOWN" or payload.get("state") != "UNKNOWN":
                return None
            occurrence = uuid5(dispatch.operation_id, "operation-outcome-unknown")
        elif event.event_type in {"operation.confirmed", "operation.reconciled"}:
            receipt = dispatch.receipt
            if (
                kind != "MAP-08"
                or receipt is None
                or payload.get("receipt_id") != str(receipt.receipt_id)
                or payload.get("state") != "CONFIRMED"
            ):
                return None
            occurrence = uuid5(
                dispatch.operation_id, "operation-confirmed:" + str(receipt.receipt_id)
            )
        else:
            return None
    return OperationNotice(kind, occurrence, execution.id)


async def destination(
    session: AsyncSession, execution_id: UUID, template: str, actor: UserEntity
) -> str | None:
    if actor.deleted_at is not None:
        return None
    permissions = await user_permissions(actor, session)
    if "*" not in permissions and "requests.start" not in permissions:
        return None
    current = await evidence(session, execution_id)
    if current is None:
        return None
    execution, attempt, dispatch = current
    kind = notice_kind(attempt, dispatch)
    if kind is None:
        return None
    if template != {"MAP-07": "application.map_07", "MAP-08": "application.map_08"}.get(kind):
        return None
    if kind == "MAP-07" and (
        not actor.is_superuser
        or ("*" not in permissions and "processes.recover" not in permissions)
    ):
        return None
    process = await session.get(
        ProcessInstanceEntity, execution.process_instance_id, populate_existing=True
    )
    if process is None:
        return None
    request = await session.get(
        BusinessRequestEntity, process.business_request_id, populate_existing=True
    )
    if (
        request is None
        or request.deleted_at is not None
        or not await RequestService(session).can_view(request, actor)
    ):
        return None
    if kind == "MAP-08" and request.requester_user_id != actor.id:
        return None
    return create_ref_id(process.id, process.version)
