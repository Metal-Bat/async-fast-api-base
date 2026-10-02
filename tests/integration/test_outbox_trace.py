"""Trace continuity through a persisted outbox and Celery worker pickup."""

from types import SimpleNamespace
from unittest.mock import Mock

from celery import signals
from celery.app.task import Context
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from structlog.contextvars import bind_contextvars, clear_contextvars

from apps.tasks.application import outbox


def test_api_outbox_and_worker_pickup_share_a_single_trace(monkeypatch) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(outbox, "tracer", provider.get_tracer("outbox"))

    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.Producer.return_value.__enter__ = Mock(return_value=Mock())
    connection.Producer.return_value.__exit__ = Mock(return_value=False)
    app = Mock()
    app.conf.broker_transport_options = {}
    app.connection_for_write.return_value = connection

    instrumentor = CeleryInstrumentor()
    try:
        with provider.get_tracer("api").start_as_current_span("api.request") as origin:
            bind_contextvars(username="ada", user_id="user-7")
            message = outbox.enqueue_task(Mock(), "system.ping")
            clear_contextvars()

        outbox._publish(app, message)
        headers = app.send_task.call_args.kwargs["headers"]
        worker_task = SimpleNamespace(
            name="system.ping",
            request=Context(
                **headers,
                id=message.task_id,
                hostname="worker-1",
                delivery_info={"routing_key": message.queue},
            ),
        )
        instrumentor.instrument(tracer_provider=provider)
        signals.task_prerun.send(
            sender=worker_task.name,
            task=worker_task,
            task_id=message.task_id,
            args=(),
            kwargs={},
        )
        try:
            with provider.get_tracer("worker").start_as_current_span("task.body"):
                pass
        finally:
            signals.task_postrun.send(
                sender=worker_task.name,
                task=worker_task,
                task_id=message.task_id,
                state="SUCCESS",
            )

        spans = {span.name: span for span in exporter.get_finished_spans()}
        producer = spans["outbox.publish system.ping"]
        pickup = spans["run/system.ping"]
        assert producer.parent is not None
        assert pickup.parent is not None
        assert spans["task.body"].parent is not None
        assert producer.context is not None
        assert pickup.context is not None
        assert producer.attributes is not None
        assert producer.parent.span_id == origin.get_span_context().span_id
        assert pickup.parent.span_id == producer.context.span_id
        assert spans["task.body"].parent.span_id == pickup.context.span_id
        assert pickup.context.trace_id == origin.get_span_context().trace_id
        assert producer.attributes["app.user.username"] == "ada"
        assert headers["trace_username"] == "ada"
    finally:
        instrumentor.uninstrument()
        clear_contextvars()
        provider.shutdown()
