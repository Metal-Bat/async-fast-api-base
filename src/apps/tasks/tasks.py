from typing import Any
from uuid import UUID

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.exc import OperationalError

from core.celery_runtime import run_async
from core.deps import SessionFactory
from core.settings import settings
from core.task_registry import TaskPolicy, register_task
from utils.exceptions import ServiceUnavailableException

_BACKGROUND_POLICY = TaskPolicy(queue=settings.CELERY_AUTOMATION_QUEUE, retry_for=(), max_retries=5)
_SUBPROCESS_POLICY = TaskPolicy(
    queue=settings.CELERY_AUTOMATION_QUEUE, retry_for=(OperationalError,), max_retries=5
)


class BackgroundExecutionFailed(Exception):
    """Redacted terminal automation failure recorded in the process domain."""


class CompensationExecutionFailed(Exception):
    """Redacted terminal compensation failure recorded in the process domain."""


class NotificationDeliveryFailed(Exception):
    """Redacted terminal notification delivery failure."""


@register_task("bpms.execute_background", bind=True, policy=_BACKGROUND_POLICY)
def execute_bpms_background(task: Task, attempt_id: str) -> dict[str, Any]:
    """Execute one opaque BPMS attempt with bounded, redacted retries."""
    from apps.ai.application.errors import AIBudgetExhausted
    from apps.processes.application.automation import execute_background, fail_background

    try:
        return run_async(execute_background(UUID(attempt_id))).model_dump(mode="json")
    except AIBudgetExhausted:
        run_async(fail_background(UUID(attempt_id), "ai.budget.exhausted"))
        raise BackgroundExecutionFailed("AI task budget exhausted") from None
    except ServiceUnavailableException as exc:
        if task.request.retries < _BACKGROUND_POLICY.max_retries:
            countdown = min(300, 2 ** (task.request.retries + 1))
            raise task.retry(exc=exc, countdown=countdown)
        run_async(fail_background(UUID(attempt_id), "background.provider.unavailable"))
        raise BackgroundExecutionFailed("Background provider unavailable") from None
    except SoftTimeLimitExceeded as exc:
        if task.request.retries < _BACKGROUND_POLICY.max_retries:
            raise task.retry(exc=exc, countdown=2 ** (task.request.retries + 1))
        run_async(fail_background(UUID(attempt_id), "background.task.timeout"))
        raise BackgroundExecutionFailed("Background task timed out") from None
    except Exception:  # noqa: BLE001 -- terminal boundary records only a redacted domain failure
        run_async(fail_background(UUID(attempt_id), "background.execution.failed"))
        raise BackgroundExecutionFailed("Background execution failed") from None


@register_task("bpms.settle_subprocess", policy=_SUBPROCESS_POLICY)
def settle_bpms_subprocess(child_id: str) -> dict[str, str]:
    """Apply a committed child result once; replay is fenced by the parent step."""
    from apps.processes.application.service import ProcessService
    from apps.processes.application.subprocess import SubprocessService
    from apps.work_items.domain import entity as work_item_entities  # noqa: F401

    async def settle() -> str:
        async with SessionFactory() as session, session.begin():
            return await SubprocessService(session, ProcessService(session)).settle(UUID(child_id))

    return {"status": run_async(settle())}


@register_task("bpms.expire_ai_approval", policy=_BACKGROUND_POLICY)
def expire_ai_approval(attempt_id: str) -> dict[str, bool]:
    """Expire and redact one due AI approval; duplicate deliveries are no-ops."""
    from apps.ai.application.approval_service import AIToolApprovalService

    async def expire() -> bool:
        async with SessionFactory() as session, session.begin():
            return await AIToolApprovalService(session).expire(UUID(attempt_id))

    return {"expired": run_async(expire())}


@register_task("bpms.execute_compensation", bind=True, policy=_BACKGROUND_POLICY)
def execute_bpms_compensation(_task: Task, record_id: str) -> dict[str, str]:
    """Execute one fenced reversal; ambiguous failure requires explicit reconciliation."""
    from apps.processes.application.compensation import (
        execute_compensation,
        fail_compensation,
    )

    identifier = UUID(record_id)
    try:
        run_async(execute_compensation(identifier))
        return {"status": "completed"}
    except ServiceUnavailableException:
        run_async(fail_compensation(identifier, "compensation.provider.unavailable"))
    except SoftTimeLimitExceeded:
        run_async(fail_compensation(identifier, "compensation.task.timeout"))
    except Exception:  # noqa: BLE001 -- boundary records a stable redacted failure
        run_async(fail_compensation(identifier, "compensation.execution.failed"))
    raise CompensationExecutionFailed("Compensation execution failed") from None


@register_task("bpms.deliver_notification", bind=True, policy=_BACKGROUND_POLICY)
def deliver_bpms_notification(task: Task, delivery_id: str) -> dict[str, str]:
    """Deliver one opaque notification row with bounded provider retries."""
    from apps.notifications.application.delivery import deliver_notification, fail_delivery

    identifier = UUID(delivery_id)
    try:
        return {"status": run_async(deliver_notification(identifier))}
    except (ServiceUnavailableException, SoftTimeLimitExceeded) as exc:
        if task.request.retries < _BACKGROUND_POLICY.max_retries:
            countdown = min(300, 2 ** (task.request.retries + 1))
            raise task.retry(exc=exc, countdown=countdown)
        run_async(fail_delivery(identifier, "notification.retry.exhausted"))
    except Exception:  # noqa: BLE001 -- boundary records only a stable redacted failure
        run_async(fail_delivery(identifier, "notification.delivery.failed"))
    raise NotificationDeliveryFailed("Notification delivery failed") from None


@register_task("bpms.fanout_application_notice", policy=_BACKGROUND_POLICY)
def fanout_application_notice(event_id: str, after_user_id: str | None = None) -> dict[str, int]:
    """Fan out one committed event in a bounded recipient batch."""
    from apps.notifications.application.events import fanout_event

    return {
        "recipients": run_async(
            fanout_event(UUID(event_id), UUID(after_user_id) if after_user_id is not None else None)
        )
    }


@register_task("bpms.fire_scheduled_action", policy=_BACKGROUND_POLICY)
def fire_bpms_scheduled_action(action_id: str, owner_id: str) -> dict[str, bool]:
    """Apply one leased timer/deadline delivery; stale messages are safe no-ops."""
    from apps.processes.application.waits import fire_claimed_action

    return {"fired": run_async(fire_claimed_action(UUID(action_id), UUID(owner_id)))}


@register_task("bpms.fail_scheduled_action", policy=_BACKGROUND_POLICY)
def fail_bpms_scheduled_action(action_id: str) -> dict[str, bool]:
    """Fail a wait after its durable scheduled delivery exhausts retries."""
    from apps.processes.application.waits import fail_scheduled_action

    return {"failed": run_async(fail_scheduled_action(UUID(action_id)))}


@register_task("system.ping")
def ping() -> dict[str, str]:
    """Return a lightweight worker health result."""
    return {"status": "ok"}


@register_task("bpms.fanout_support_incident", policy=_BACKGROUND_POLICY)
def fanout_support_incident(incident_id: str, after_user_id: str | None = None) -> dict[str, int]:
    """Deliver one bounded committed support episode through the existing inbox."""
    from apps.support.application.alerts import fanout_incident

    return {
        "recipients": run_async(
            fanout_incident(
                UUID(incident_id), UUID(after_user_id) if after_user_id is not None else None
            )
        )
    }


@register_task("system.cleanup_task_history")
def cleanup_task_history() -> dict[str, int]:
    """Delete expired idempotency claims and old execution history."""

    async def cleanup() -> int:
        from apps.notifications.application.service import NotificationService
        from apps.support.application.service import prune_incidents
        from apps.tasks.application.retention import cleanup_operational_history

        async with SessionFactory() as session:
            expired = await cleanup_operational_history(session)
            await NotificationService(session).redact_expired()
            await prune_incidents(session)
            await session.commit()
            return expired

    return {"deleted": run_async(cleanup())}


@register_task("media.cleanup_abandoned_uploads")
def cleanup_abandoned_media() -> dict[str, int]:
    """Remove bounded batches of expired uploads after reference rechecks."""
    from apps.forms.application.attachments import cleanup_abandoned_uploads

    async def cleanup() -> int:
        async with SessionFactory() as session, session.begin():
            return await cleanup_abandoned_uploads(session)

    return {"deleted": run_async(cleanup())}


@register_task("bpms.fire_calendar_reminder", policy=_BACKGROUND_POLICY)
def fire_calendar_reminder(reminder_id: str) -> dict[str, str]:
    """Fire one committed schedule after checking current source and recipient."""
    from apps.calendar.application.reminders import fire_reminder

    return {"status": run_async(fire_reminder(UUID(reminder_id)))}
