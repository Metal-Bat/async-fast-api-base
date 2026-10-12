"""Tests for transactional task outbox messages."""

import threading
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import anyio
import anyio.lowlevel
import pytest
from structlog.contextvars import bind_contextvars, clear_contextvars

from apps.tasks.application import outbox
from apps.tasks.application.outbox import enqueue_task


@pytest.mark.anyio
async def test_broker_confirmation_does_not_block_other_async_work(monkeypatch):
    """The transaction stays open while the loop can service other tasks."""
    loop_progress = threading.Event()
    transaction_open = False
    session = AsyncMock()
    message = enqueue_task(Mock(), "system.ping")
    session.exec.side_effect = [
        Mock(one_or_none=Mock(return_value=message)),
        Mock(one_or_none=Mock(return_value=None)),
    ]
    session.add = Mock()

    class Transaction:
        async def __aenter__(self):
            nonlocal transaction_open
            transaction_open = True

        async def __aexit__(self, *_args):
            nonlocal transaction_open
            transaction_open = False

    session.begin = Mock(return_value=Transaction())
    session.__aenter__.return_value = session
    monkeypatch.setattr(outbox, "SessionFactory", Mock(return_value=session))

    def confirm(_app, _message):
        assert loop_progress.wait(timeout=1), "Broker confirmation blocked the async loop"
        assert transaction_open, "The outbox row lock was released before confirmation"

    async def progress():
        await anyio.lowlevel.checkpoint()
        loop_progress.set()

    monkeypatch.setattr(outbox, "_publish", confirm)
    async with anyio.create_task_group() as group:
        group.start_soon(progress)
        assert await outbox.dispatch_outbox(Mock()) == 1
    assert not transaction_open


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
