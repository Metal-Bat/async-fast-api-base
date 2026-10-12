from unittest.mock import Mock
from uuid import uuid7

import pytest

from apps.processes.application.automation import broker_priority
from apps.step_types.application.automation import resolve_operation
from apps.tasks.application.outbox import enqueue_task
from core.settings import settings

CONNECTION_CODE = "test"


def test_only_registered_operation_can_be_resolved() -> None:
    operation = resolve_operation("connection.status", "service_task", "1")
    assert operation.key == "connection.status"
    with pytest.raises(ValueError, match="not registered"):
        resolve_operation("python.import", "service_task", "1")
    with pytest.raises(ValueError, match="not registered"):
        resolve_operation("connection.status", "notification", "1")


def test_sandbox_operation_is_versioned_and_only_compatible_with_service_task() -> None:
    operation = resolve_operation("sandbox.order.create/1", "service_task", "1")
    assert operation.allowed_providers == ("https_sandbox_orders",)
    assert operation.approval_policy == "purchase-human-approval/1"
    with pytest.raises(ValueError, match="not registered"):
        resolve_operation("sandbox.order.create/1", "notification", "1")


def test_cancellation_is_registered_only_for_explicit_compensation() -> None:
    with pytest.raises(ValueError, match="not registered"):
        resolve_operation("sandbox.order.cancel/1", "service_task", "1")
    operation = resolve_operation(
        "sandbox.order.cancel/1", "service_task", "1", execution_scope="COMPENSATION"
    )
    assert operation.key == "sandbox.order.cancel/1"


def test_business_priority_maps_to_supported_broker_range() -> None:
    assert broker_priority(0) == 0
    assert broker_priority(9) == settings.CELERY_MAX_PRIORITY
    assert broker_priority(5) == round(5 * settings.CELERY_MAX_PRIORITY / 9)
    with pytest.raises(ValueError, match="between 0 and 9"):
        broker_priority(10)


def test_opaque_outbox_message_uses_attempt_as_delivery_identity() -> None:
    session = Mock()
    attempt_id = uuid7()
    message = enqueue_task(
        session,
        "bpms.execute_background",
        kwargs={"attempt_id": str(attempt_id)},
        task_id=str(attempt_id),
        idempotency_key=attempt_id,
        priority=broker_priority(7),
    )
    assert message.task_id == str(attempt_id)
    assert message.kwargs == {"attempt_id": str(attempt_id)}
    assert message.headers["idempotency_key"] == str(attempt_id)
    assert "connection" not in str(message.kwargs)
    session.add.assert_called_once_with(message)


@pytest.mark.anyio
async def test_protected_operation_cannot_stage_without_human_action(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from apps.integrations.domain.contracts import ConnectionPin
    from apps.processes.application import automation
    from apps.processes.domain.entity import StepExecutionEntity
    from apps.users.domain.entity import UserEntity
    from apps.workflows.domain.entity import WorkflowVersionEntity
    from utils.exceptions import VersionConflictException

    actor = UserEntity(id=uuid7(), username="ordinary-publisher", hashed_password="hash")
    version = SimpleNamespace(id=uuid7(), published_by_user_id=actor.id)
    execution = SimpleNamespace(id=uuid7(), process_instance_id=uuid7())
    session = Mock()

    async def get(kind, identifier, **kwargs):
        return {
            WorkflowVersionEntity: version,
            UserEntity: actor,
            StepExecutionEntity: execution,
        }.get(kind)

    session.get = AsyncMock(side_effect=get)
    pin = ConnectionPin(
        connection_ref="pin",
        provider="https_sandbox_orders",
        kind="SERVICE",
        endpoint_key="sandbox",
        secret_ref=CONNECTION_CODE,
        secret_version="1",
    )
    monkeypatch.setattr(automation.ConnectionService, "pin", AsyncMock(return_value=pin))
    monkeypatch.setattr(
        automation, "resolve_operation", lambda *args: SimpleNamespace(key="sandbox.order.create/1")
    )
    from apps.processes.application.events import ProcessEventService

    monkeypatch.setattr(ProcessEventService, "append", AsyncMock())
    attempt = Mock(id=uuid7(), step_execution_id=execution.id, number=1)
    step = Mock(config={"operation_key": "sandbox.order.create/1", "connection_ref": "pin"})
    request = Mock(workflow_version_id=version.id, priority=1)
    handler = Mock(handler_key="service_task", handler_version="1")
    with pytest.raises(VersionConflictException, match="human approval"):
        await automation.AutomationDispatcher(session, Mock()).stage(
            attempt=attempt, step=step, handler=handler, request=request
        )
    session.add.assert_not_called()
