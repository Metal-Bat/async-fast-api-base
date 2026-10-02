"""Bounded cleanup of disposable task records; business audit is retained."""

from datetime import datetime, timedelta

from sqlmodel import col, delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.domain.entity import StepExecutionAttemptEntity
from apps.tasks.domain.entity import TaskExecutionEntity, TaskIdempotencyEntity, TaskOutboxEntity
from core.settings import settings
from utils.date_utils import get_datetime_utc


async def cleanup_operational_history(
    session: AsyncSession, *, now: datetime | None = None, limit: int = 500
) -> int:
    """Preserve durable BPMS deduplication, referenced executions and all configuration history."""
    if not 1 <= limit <= 1000:
        raise ValueError("Retention batch size must be between 1 and 1000")
    now = now or get_datetime_utc()
    cutoff = now - timedelta(days=settings.CELERY_RESULT_RETENTION_DAYS)
    durable_tasks = select(TaskOutboxEntity.task_id).where(
        col(TaskOutboxEntity.task_name).startswith("bpms.")
    )
    expired = (
        select(TaskIdempotencyEntity.id)
        .where(
            col(TaskIdempotencyEntity.expires_at) < now,
            TaskIdempotencyEntity.status == "SUCCESS",
            col(TaskIdempotencyEntity.task_id).not_in(durable_tasks),
        )
        .order_by(col(TaskIdempotencyEntity.expires_at), col(TaskIdempotencyEntity.id))
        .limit(limit)
    )
    deleted = await session.exec(
        delete(TaskIdempotencyEntity).where(col(TaskIdempotencyEntity.id).in_(expired))
    )
    referenced = select(StepExecutionAttemptEntity.task_execution_id).where(
        col(StepExecutionAttemptEntity.task_execution_id).is_not(None)
    )
    executions = (
        select(TaskExecutionEntity.id)
        .where(
            col(TaskExecutionEntity.finished_at) < cutoff,
            col(TaskExecutionEntity.status).in_(["SUCCESS", "FAILURE", "REVOKED"]),
            ~col(TaskExecutionEntity.task_name).startswith("bpms."),
            col(TaskExecutionEntity.id).not_in(referenced),
        )
        .order_by(col(TaskExecutionEntity.finished_at), col(TaskExecutionEntity.id))
        .limit(limit)
    )
    await session.exec(
        delete(TaskExecutionEntity).where(col(TaskExecutionEntity.id).in_(executions))
    )
    outbox = (
        select(TaskOutboxEntity.id)
        .where(
            col(TaskOutboxEntity.published_at) < cutoff,
            ~col(TaskOutboxEntity.task_name).startswith("bpms."),
        )
        .order_by(col(TaskOutboxEntity.published_at), col(TaskOutboxEntity.id))
        .limit(limit)
    )
    await session.exec(delete(TaskOutboxEntity).where(col(TaskOutboxEntity.id).in_(outbox)))
    return deleted.rowcount or 0
