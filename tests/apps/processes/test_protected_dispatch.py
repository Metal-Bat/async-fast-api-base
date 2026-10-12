"""Public worker seam must fence protected effects and never replay uncertainty."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock
from uuid import uuid5, uuid7

import pytest

from apps.integrations.domain.contracts import AdapterResult, ConnectionPin
from apps.integrations.domain.orders import (
    ProtectedApprovalEvidence,
    SandboxOrderReceipt,
    payload_hash,
)
from apps.processes.application import automation
from apps.processes.application.approval import ProtectedEffectApproval
from apps.processes.application.service import ProcessService
from apps.processes.domain.automation import AutomationSnapshot
from apps.processes.domain.entity import (
    ExecutionTokenEntity,
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowStepEntity
from utils.exceptions import VersionConflictException

CONNECTION_CODE = "test"


@pytest.fixture
def dispatch(monkeypatch):
    payload = {"item_code": "DEMO", "quantity": 1}
    actor = UserEntity(id=uuid7(), username="publisher", hashed_password="hash")
    evidence = ProtectedApprovalEvidence(
        workflow_version_id=uuid7(),
        graph_checksum="a" * 64,
        approval_step_id=uuid7(),
        approval_execution_id=uuid7(),
        work_item_id=uuid7(),
        action_id=uuid7(),
        actor_id=uuid7(),
        payload_hash=payload_hash(payload),
    )
    pin = ConnectionPin(
        connection_ref="pin",
        provider="https_sandbox_orders",
        kind="SERVICE",
        endpoint_key="sandbox",
        secret_ref=CONNECTION_CODE,
        secret_version="1",
    )
    snapshot = AutomationSnapshot(
        handler_key="service_task",
        handler_version="1",
        operation_key="sandbox.order.create/1",
        actor_id=actor.id,
        connection=pin,
        protected_approval=evidence,
    )
    process = ProcessInstanceEntity(
        id=uuid7(),
        business_request_id=uuid7(),
        workflow_version_id=evidence.workflow_version_id,
        status="WAITING",
    )
    token = ExecutionTokenEntity(id=uuid7(), process_instance_id=process.id, status="WAITING")
    step = WorkflowStepEntity(
        id=uuid7(),
        workflow_version_id=process.workflow_version_id,
        step_type_version_id=uuid7(),
        step_key="order",
        name="Order",
        config={"operation_key": "sandbox.order.create/1", "connection_ref": "pin"},
    )
    execution = StepExecutionEntity(
        id=uuid7(),
        process_instance_id=process.id,
        execution_token_id=token.id,
        workflow_step_id=step.id,
        visit_number=1,
        status="WAITING",
        wait_kind="BACKGROUND",
        input_snapshot={"payload": payload},
    )
    attempt = StepExecutionAttemptEntity(
        id=uuid7(),
        step_execution_id=execution.id,
        number=1,
        status="WAITING",
        dispatch_key="test",
        automation_snapshot=snapshot.model_dump(mode="json"),
    )
    rows = {
        UserEntity: actor,
        ProcessInstanceEntity: process,
        ExecutionTokenEntity: token,
        WorkflowStepEntity: step,
        StepExecutionEntity: execution,
        StepExecutionAttemptEntity: attempt,
    }
    active_sessions = []

    @asynccontextmanager
    async def context():
        yield

    session = Mock(
        get=AsyncMock(side_effect=lambda kind, identifier, **kwargs: rows.get(kind)),
        exec=AsyncMock(return_value=Mock(one_or_none=Mock(return_value=None))),
        begin=context,
    )

    @asynccontextmanager
    async def factory():
        active_sessions.append(session)
        try:
            yield session
        finally:
            active_sessions.remove(session)

    monkeypatch.setattr(automation, "SessionFactory", factory)
    monkeypatch.setattr(ProtectedEffectApproval, "capture", AsyncMock(return_value=evidence))
    monkeypatch.setattr(automation.ConnectionService, "recheck_service", AsyncMock())
    complete = AsyncMock(return_value="completed")
    monkeypatch.setattr(ProcessService, "complete_background", complete)
    from apps.processes.application.events import ProcessEventService

    monkeypatch.setattr(ProcessEventService, "append", AsyncMock())
    from apps.users.application import authorization

    monkeypatch.setattr(
        authorization, "user_permissions", AsyncMock(return_value={"workflows.manage"})
    )
    provider = Mock(
        validate=Mock(),
        invoke=AsyncMock(return_value=AdapterResult(status_code=200)),
        create_order=AsyncMock(),
        lookup_order=AsyncMock(),
    )
    return Mock(
        attempt=attempt,
        execution=execution,
        process=process,
        token=token,
        actor=actor,
        evidence=evidence,
        provider=provider,
        active_sessions=active_sessions,
        factory=factory,
        complete=complete,
    )


@pytest.mark.anyio
async def test_worker_cannot_ignore_missing_human_approval(dispatch):
    dispatch.attempt.automation_snapshot["protected_approval"] = None
    with pytest.raises(VersionConflictException, match="approval"):
        await automation.execute_background(dispatch.attempt.id, dispatch.provider)
    dispatch.provider.invoke.assert_not_called()
    dispatch.provider.create_order.assert_not_called()


@pytest.mark.anyio
async def test_protected_dispatch_records_receipt_and_closes_db_before_http(dispatch):
    identity = uuid5(dispatch.execution.id, "sandbox.order.create/1")
    receipt = SandboxOrderReceipt(
        operation_id=identity,
        receipt_id=uuid7(),
        state="CREATED",
        payload_hash=payload_hash({"item_code": "DEMO", "quantity": 1, "note": None}),
    )

    async def create(pin, operation_id, payload):
        assert not dispatch.active_sessions
        assert operation_id == identity
        assert dispatch.attempt.automation_snapshot["order_dispatch"]["state"] == "DISPATCHING"
        return receipt

    dispatch.provider.create_order.side_effect = create
    result = await automation.execute_background(dispatch.attempt.id, dispatch.provider)
    assert result.disposition == "completed"
    dispatch.provider.create_order.assert_awaited_once()
    dispatch.provider.invoke.assert_not_called()
    assert dispatch.attempt.automation_snapshot["order_dispatch"]["receipt"] == receipt.model_dump(
        mode="json"
    )


@pytest.mark.anyio
async def test_unknown_dispatch_is_not_retried_by_duplicate_delivery(dispatch):
    from apps.integrations.application.orders import OrderOutcomeUnknown

    dispatch.provider.create_order.side_effect = OrderOutcomeUnknown("requires lookup")
    result = await automation.execute_background(dispatch.attempt.id, dispatch.provider)
    assert result.disposition == "operation_unknown"
    assert dispatch.execution.status == "WAITING"
    assert dispatch.attempt.automation_snapshot["order_dispatch"]["state"] == "UNKNOWN"
    replay = await automation.execute_background(dispatch.attempt.id, dispatch.provider)
    assert replay.disposition == "operation_unknown"
    dispatch.provider.create_order.assert_awaited_once()
    dispatch.complete.assert_not_called()


@pytest.mark.anyio
async def test_worker_cannot_ignore_changed_human_action(dispatch):
    dispatch.attempt.automation_snapshot["protected_approval"]["action_id"] = str(uuid7())
    with pytest.raises(VersionConflictException, match="approval"):
        await automation.execute_background(dispatch.attempt.id, dispatch.provider)
    dispatch.provider.invoke.assert_not_called()
    dispatch.provider.create_order.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("change", ["superuser", "offboarded", "cancelled"])
async def test_protected_worker_does_not_dispatch_for_invalid_principal_or_process(
    dispatch, change
):
    from utils.date_utils import get_datetime_utc

    if change == "superuser":
        dispatch.actor.is_superuser = True
    elif change == "offboarded":
        dispatch.actor.deleted_at = get_datetime_utc()
    else:
        dispatch.process.status = "CANCELLED"
    try:
        await automation.execute_background(dispatch.attempt.id, dispatch.provider)
    except VersionConflictException:
        pass
    dispatch.provider.invoke.assert_not_called()
    dispatch.provider.create_order.assert_not_called()
