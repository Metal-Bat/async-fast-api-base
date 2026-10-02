from apps.tasks.domain.entities.execution import (
    TaskExecutionEntity,
    TaskIdempotencyEntity,
    TaskOutboxEntity,
)
from apps.tasks.domain.entities.lease import SchedulerLeaseEntity
from apps.tasks.domain.entities.schedule import PeriodicTaskEntity
from core.history import create_history_table

PeriodicTaskHistoryTable = create_history_table(
    getattr(PeriodicTaskEntity, "__table__")  # noqa: B009
)


__all__ = [
    "PeriodicTaskEntity",
    "SchedulerLeaseEntity",
    "TaskExecutionEntity",
    "TaskIdempotencyEntity",
    "TaskOutboxEntity",
]
