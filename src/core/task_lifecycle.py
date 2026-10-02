import json
import traceback as traceback_module
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic
from typing import Any
from uuid import UUID

import structlog
from celery.exceptions import Ignore, Reject, Retry, SoftTimeLimitExceeded
from opentelemetry import trace
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col
from structlog.contextvars import bound_contextvars

from apps.tasks.application.idempotency import acquire_task, complete_task, release_task
from apps.tasks.domain.entity import TaskExecutionEntity
from core.celery_runtime import run_async
from core.deps import SessionFactory
from core.settings import settings
from utils.date_utils import get_datetime_utc

logger = structlog.get_logger(__name__)


class TaskAlreadyRunning(Exception):
    """A delivery must wait for the current owner's lease."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("Task idempotency key is already running")
        self.retry_after = retry_after


@dataclass(slots=True)
class TaskLifecycle:
    """Carry the cached result or the current body's result through finalization."""

    duplicate: bool = False
    result: Any = None


def json_value(value: Any) -> Any:
    """Return a JSON-compatible value for durable result storage."""
    try:
        json.dumps(value)
    except TypeError, ValueError:
        return repr(value)
    return value


def _idempotency_uuid(task_name: str, value: object) -> UUID:
    """Keep new UUID keys sortable while deterministically adapting legacy deliveries."""
    try:
        return UUID(str(value))
    except ValueError:
        digest = sha256(f"{task_name}:{value}".encode()).hexdigest()
        return UUID(digest[:32])


async def _record(task_id: str, **values: Any) -> None:
    statement = insert(TaskExecutionEntity).values(task_id=task_id, **values)
    # Column names are uppercase in the database; map attributes explicitly for upserts.
    statement = statement.on_conflict_do_update(
        index_elements=[TaskExecutionEntity.task_id],
        set_={getattr(TaskExecutionEntity, key): value for key, value in values.items()},
        where=col(TaskExecutionEntity.retries) <= values.get("retries", 0),
    )
    async with SessionFactory() as session:
        await session.exec(statement)
        await session.commit()


def record_execution(task_id: str, **values: Any) -> None:
    """Keep history failures observable without hiding task outcomes or cleanup."""
    try:
        run_async(_record(task_id, **values))
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:  # noqa: BLE001 - boundary logs failure and retains recoverable state
        logger.error("task.history_failed", task_id=task_id, error_type=type(exc).__name__)


@contextmanager
def task_lifecycle(
    task: Any, args: tuple[Any, ...], kwargs: dict[str, Any]
) -> Iterator[TaskLifecycle]:
    """Release failed/retried work in finally; retain successful results for deduplication."""
    request = task.request
    task_id = request.id
    headers = request.headers or {}
    key = headers.get("idempotency_key") or task_id
    scoped_key = _idempotency_uuid(task.name, key)
    hard_limit = (getattr(request, "timelimit", None) or (None, None))[0]
    hard_limit = hard_limit or task.time_limit or settings.CELERY_TASK_TIME_LIMIT
    lease_seconds = int(hard_limit) + settings.CELERY_TASK_LEASE_GRACE_SECONDS
    span = trace.get_current_span()
    span.add_event("task.picked_up")
    span.set_attribute("messaging.message.id", task_id)
    span.set_attribute(
        "messaging.destination.name", (request.delivery_info or {}).get("routing_key", "")
    )
    span.set_attribute("celery.task.name", task.name)
    span.set_attribute("celery.task.retries", request.retries)
    if username := headers.get("trace_username"):
        span.set_attribute("app.user.username", str(username))
    if user_id := headers.get("trace_user_id"):
        user_id_text = str(user_id)
        span.set_attribute("enduser.id", user_id_text)
        span.set_attribute("app.user.id", user_id_text)
    with bound_contextvars(task_id=task_id, task_name=task.name):
        claim = run_async(acquire_task(scoped_key, task_id, lease_seconds))
        if not claim.acquired:
            if not claim.completed:
                logger.info("task.lease_busy", retry_after=claim.retry_after)
                raise TaskAlreadyRunning(claim.retry_after)
            logger.info("task.duplicate_completed")
            yield TaskLifecycle(duplicate=True, result=claim.result)
            return

        started_at, clock = get_datetime_utc(), monotonic()
        state = TaskLifecycle()
        status = "FAILURE"
        result: Any = None
        traceback_text: str | None = None
        try:
            logger.info("task.started", retries=request.retries, lease_seconds=lease_seconds)
            record_execution(
                task_id,
                task_name=task.name,
                status="STARTED",
                result=None,
                traceback=None,
                args=json_value(list(args)),
                kwargs=json_value(kwargs),
                queue=(request.delivery_info or {}).get("routing_key"),
                worker=request.hostname,
                retries=request.retries,
                started_at=started_at,
                finished_at=None,
                duration_seconds=None,
            )
            yield state
            result = json_value(state.result)
            run_async(complete_task(claim, result))
            status = "SUCCESS"
            logger.info("task.succeeded", duration_seconds=monotonic() - clock)
        except BaseException as exc:
            if isinstance(exc, Retry):
                status = "RETRY"
            elif isinstance(exc, (Ignore, Reject)):
                status = "IGNORED" if isinstance(exc, Ignore) else "REJECTED"
            result = {"exception_type": type(exc).__name__, "message": str(exc)}
            traceback_text = traceback_module.format_exc()
            logger.warning("task.interrupted", status=status, error_type=type(exc).__name__)
            raise
        finally:
            try:
                run_async(release_task(claim))
                logger.info("task.state_released", status=status)
            except BaseException as exc:  # noqa: BLE001 - cleanup must not mask the task error
                # A dead database or process cannot promise immediate release; the lease expires.
                logger.error(
                    "task.release_failed",
                    error_type=type(exc).__name__,
                    lease_seconds=lease_seconds,
                )
            record_execution(
                task_id,
                task_name=task.name,
                status=status,
                result=result,
                traceback=traceback_text,
                retries=request.retries,
                started_at=started_at,
                finished_at=get_datetime_utc(),
                duration_seconds=monotonic() - clock,
            )
