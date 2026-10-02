from unittest.mock import Mock
from uuid import uuid7

import pytest

from apps.processes.application.automation import broker_priority
from apps.step_types.application.automation import resolve_operation
from apps.tasks.application.outbox import enqueue_task
from core.settings import settings


def test_only_registered_operation_can_be_resolved() -> None:
    operation = resolve_operation("connection.status", "service_task", "1")
    assert operation.key == "connection.status"
    with pytest.raises(ValueError, match="not registered"):
        resolve_operation("python.import", "service_task", "1")
    with pytest.raises(ValueError, match="not registered"):
        resolve_operation("connection.status", "notification", "1")


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
