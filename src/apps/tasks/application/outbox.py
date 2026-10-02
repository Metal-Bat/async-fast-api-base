from datetime import timedelta
from typing import Any
from uuid import UUID, uuid7

import structlog
from opentelemetry import context, propagate, trace
from opentelemetry.trace import SpanKind
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from structlog.contextvars import get_contextvars

from apps.tasks.domain.entity import TaskOutboxEntity
from core.bpms_observability import bpms_telemetry
from core.deps import SessionFactory
from core.settings import settings
from utils.date_utils import get_datetime_utc

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)
_RESERVED_TRACE_HEADERS = frozenset(
    {"traceparent", "tracestate", "baggage", "trace_username", "trace_user_id"}
)


def enqueue_task(
    session: AsyncSession,
    task_name: str,
    *,
    args: list[object] | None = None,
    kwargs: dict[str, object] | None = None,
    queue: str | None = None,
    headers: dict[str, object] | None = None,
    task_id: str | None = None,
    idempotency_key: UUID | str | None = None,
    priority: int = 0,
) -> TaskOutboxEntity:
    """Stage a message in the caller's transaction; the caller owns commit/rollback."""
    internal_headers = dict(headers or {})
    for name in tuple(internal_headers):
        if name.lower() in _RESERVED_TRACE_HEADERS:
            internal_headers.pop(name)
    internal_headers["idempotency_key"] = str(idempotency_key or uuid7())
    propagate.inject(internal_headers)
    internal_headers.pop("baggage", None)
    log_context = get_contextvars()
    if username := log_context.get("username"):
        internal_headers["trace_username"] = str(username)
    if user_id := log_context.get("user_id"):
        internal_headers["trace_user_id"] = str(user_id)
    message = TaskOutboxEntity(
        task_id=task_id or str(uuid7()),
        task_name=task_name,
        args=args or [],
        kwargs=kwargs or {},
        queue=queue or settings.CELERY_DEFAULT_QUEUE,
        headers=internal_headers,
        priority=priority,
        available_at=get_datetime_utc(),
    )
    session.add(message)
    return message


def _publish(app: Any, message: TaskOutboxEntity) -> None:
    """Wait for a RabbitMQ publisher confirmation with bounded socket waits."""
    token = None
    if "traceparent" in message.headers:
        token = context.attach(propagate.extract(message.headers))
    try:
        with tracer.start_as_current_span(
            f"outbox.publish {message.task_name}", kind=SpanKind.PRODUCER
        ) as span:
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.message.id", message.task_id)
            span.set_attribute("messaging.destination.name", message.queue)
            span.set_attribute("celery.task.name", message.task_name)
            for header, attribute in (
                ("trace_username", "app.user.username"),
                ("trace_user_id", "app.user.id"),
                ("trace_user_id", "enduser.id"),
            ):
                if value := message.headers.get(header):
                    span.set_attribute(attribute, str(value))
            delivery_headers = dict(message.headers)
            propagate.inject(delivery_headers)
            delivery_headers.pop("baggage", None)
            with app.connection_for_write(
                connect_timeout=5,
                transport_options={
                    **app.conf.broker_transport_options,
                    "read_timeout": 5,
                    "write_timeout": 5,
                },
            ) as connection:
                connection.ensure_connection(max_retries=0)
                with connection.Producer() as producer:
                    app.send_task(
                        message.task_name,
                        args=message.args,
                        kwargs=message.kwargs,
                        queue=message.queue,
                        headers=delivery_headers,
                        priority=message.priority,
                        task_id=message.task_id,
                        producer=producer,
                        retry=False,
                        timeout=5,
                        confirm_timeout=5,
                    )
    finally:
        if token is not None:
            context.detach(token)


async def dispatch_outbox(app: Any) -> int:
    """Publish locked rows; a crash releases the transaction and permits replay of the same ID."""
    published = 0
    for _ in range(settings.CELERY_OUTBOX_BATCH_SIZE):
        async with SessionFactory() as session, session.begin():
            message = (
                await session.exec(
                    select(TaskOutboxEntity)
                    .where(
                        col(TaskOutboxEntity.published_at).is_(None),
                        col(TaskOutboxEntity.available_at) <= get_datetime_utc(),
                    )
                    .order_by(col(TaskOutboxEntity.available_at), col(TaskOutboxEntity.id))
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            ).one_or_none()
            if message is None:
                break
            message.attempts += 1
            try:
                _publish(app, message)
            except Exception as exc:  # noqa: BLE001 - boundary logs failure and retains recoverable state
                delay = min(300, 2 ** min(message.attempts, 8))
                message.available_at = get_datetime_utc() + timedelta(seconds=delay)
                message.last_error = type(exc).__name__
                logger.warning(
                    "outbox.publish_failed",
                    task_id=message.task_id,
                    attempt=message.attempts,
                    retry_seconds=delay,
                    error_type=type(exc).__name__,
                )
                bpms_telemetry.record_outbox_retry()
                bpms_telemetry.log_failure("outbox", "publish_failed", exc)
            else:
                message.published_at = get_datetime_utc()
                message.last_error = None
                published += 1
                logger.info("outbox.published", task_id=message.task_id, attempt=message.attempts)
            session.add(message)
    return published
