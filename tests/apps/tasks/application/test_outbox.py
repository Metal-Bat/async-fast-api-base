"""Tests for transactional task outbox messages."""

from unittest.mock import Mock
from uuid import UUID

from structlog.contextvars import bind_contextvars, clear_contextvars

from apps.tasks.application import outbox
from apps.tasks.application.outbox import enqueue_task


def test_outbox_autogenerates_uuid7_idempotency_key() -> None:
    message = enqueue_task(Mock(), "system.ping")

    generated = UUID(str(message.headers["idempotency_key"]))
    assert generated.version == 7


def test_outbox_persists_trace_context_and_authenticated_identity(monkeypatch) -> None:
    def inject(carrier):
        carrier["traceparent"] = "00-trace-span-01"

    monkeypatch.setattr(outbox.propagate, "inject", inject, raising=False)
    bind_contextvars(username="ada", user_id="0199-user")
    try:
        message = enqueue_task(Mock(), "system.ping")
    finally:
        clear_contextvars()

    assert message.headers["traceparent"] == "00-trace-span-01"
    assert message.headers["trace_username"] == "ada"
    assert message.headers["trace_user_id"] == "0199-user"


def test_outbox_does_not_accept_caller_supplied_trace_identity(monkeypatch) -> None:
    monkeypatch.setattr(outbox.propagate, "inject", Mock())

    message = enqueue_task(
        Mock(),
        "system.ping",
        headers={
            "trace_username": "forged-user",
            "trace_user_id": "forged-id",
            "traceparent": "forged-parent",
            "tracestate": "forged-state",
        },
    )

    assert "trace_username" not in message.headers
    assert "trace_user_id" not in message.headers
    assert "traceparent" not in message.headers
    assert "tracestate" not in message.headers


def test_publish_restores_originating_trace_before_celery_publish(monkeypatch) -> None:
    parent_context = object()
    token = object()
    extract = Mock(return_value=parent_context)
    attach = Mock(return_value=token)
    detach = Mock()
    monkeypatch.setattr(outbox.propagate, "extract", extract)
    monkeypatch.setattr(outbox.context, "attach", attach)
    monkeypatch.setattr(outbox.context, "detach", detach)
    span = Mock()
    span_context = Mock()
    span_context.__enter__ = Mock(return_value=span)
    span_context.__exit__ = Mock(return_value=False)
    start_span = Mock(return_value=span_context)
    monkeypatch.setattr(outbox.tracer, "start_as_current_span", start_span, raising=False)
    inject = Mock(side_effect=lambda headers: headers.update(traceparent="producer-parent"))
    monkeypatch.setattr(outbox.propagate, "inject", inject)
    producer = Mock()
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.Producer.return_value.__enter__ = Mock(return_value=producer)
    connection.Producer.return_value.__exit__ = Mock(return_value=False)
    app = Mock()
    app.conf.broker_transport_options = {}
    app.connection_for_write.return_value = connection
    message = Mock(
        task_name="system.ping",
        args=[],
        kwargs={},
        queue="default",
        headers={"traceparent": "00-trace-span-01", "trace_username": "ada"},
        priority=0,
        task_id="task-id",
    )

    outbox._publish(app, message)

    extract.assert_called_once_with(message.headers)
    attach.assert_called_once_with(parent_context)
    detach.assert_called_once_with(token)
    start_span.assert_called_once_with("outbox.publish system.ping", kind=outbox.SpanKind.PRODUCER)
    span.set_attribute.assert_any_call("app.user.username", "ada")
    span.set_attribute.assert_any_call("messaging.message.id", "task-id")
    span.set_attribute.assert_any_call("messaging.destination.name", "default")
    assert app.send_task.call_args.kwargs["headers"]["traceparent"] == "producer-parent"
    assert message.headers["traceparent"] == "00-trace-span-01"
