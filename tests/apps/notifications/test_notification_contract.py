from unittest.mock import Mock
from uuid import uuid7

import pytest

from apps.notifications.application.service import NotificationService
from apps.notifications.application.templates import NotificationTemplateRegistry
from apps.tasks.application.outbox import enqueue_task


def test_template_rendering_is_typed_localized_and_html_safe() -> None:
    templates = NotificationTemplateRegistry()

    rendered = templates.render(
        "workflow.notice", "1", "fa", {"message": "<script>alert(1)</script>"}
    )

    assert rendered.subject == "اعلان گردش کار"
    assert rendered.content == "&lt;script&gt;alert(1)&lt;/script&gt;"
    with pytest.raises(ValueError, match="variables"):
        templates.render("workflow.notice", "1", "en", {})
    with pytest.raises(ValueError, match="incompatible"):
        templates.render("workflow.notice", "1", "en", {"message": 1})
    with pytest.raises(ValueError, match="not registered"):
        templates.render("unknown", "1", "en", {"message": "hello"})


def test_destination_fingerprint_and_outbox_payload_do_not_expose_address() -> None:
    first = NotificationService._fingerprint("User@Example.test")
    second = NotificationService._fingerprint(" user@example.test ")
    assert first == second and len(first) == 64
    assert "example" not in first

    session = Mock()
    delivery_id = uuid7()
    message = enqueue_task(
        session,
        "bpms.deliver_notification",
        kwargs={"delivery_id": str(delivery_id)},
        task_id=f"notification:{delivery_id}",
        idempotency_key=delivery_id,
    )
    assert message.kwargs == {"delivery_id": str(delivery_id)}
    assert "@" not in str(message.kwargs) + str(message.headers)
