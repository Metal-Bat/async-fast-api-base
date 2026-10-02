"""Aggregate bounded operational state for periodic BPMS telemetry."""

from collections.abc import Sequence
from datetime import datetime

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.domain.entity import CompensationRecordEntity, StepExecutionEntity
from apps.tasks.domain.entity import TaskOutboxEntity
from apps.work_items.domain.entity import WorkItemEntity
from core.bpms_observability import BPMSOperationalSnapshot
from utils.date_utils import get_datetime_utc


def build_operational_snapshot(
    *,
    now: datetime,
    cartable_rows: Sequence[tuple[str, int]],
    wait_rows: Sequence[tuple[str, datetime]],
    outbox_row: tuple[int, datetime | None],
    compensation_rows: Sequence[tuple[str, int]],
) -> BPMSOperationalSnapshot:
    """Convert aggregate rows into an identifier-free telemetry snapshot."""
    outbox_count, oldest_outbox = outbox_row
    return BPMSOperationalSnapshot(
        cartable_backlog={status: count for status, count in cartable_rows},
        wait_oldest_age_seconds={
            wait_kind: max(0.0, (now - started_at).total_seconds())
            for wait_kind, started_at in wait_rows
        },
        outbox_pending=outbox_count,
        outbox_oldest_age_seconds=(
            max(0.0, (now - oldest_outbox).total_seconds()) if oldest_outbox else 0.0
        ),
        compensation_backlog={status: count for status, count in compensation_rows},
    )


async def collect_operational_snapshot(session: AsyncSession) -> BPMSOperationalSnapshot:
    """Read only aggregate operational counts and oldest timestamps from PostgreSQL."""
    now = get_datetime_utc()
    cartable_rows = (
        await session.exec(
            select(WorkItemEntity.status, func.count())
            .where(col(WorkItemEntity.status).in_(["OPEN", "CLAIMED", "IN_PROGRESS"]))
            .group_by(WorkItemEntity.status)
        )
    ).all()
    wait_rows = (
        await session.exec(
            select(StepExecutionEntity.wait_kind, func.min(StepExecutionEntity.started_at))
            .where(
                StepExecutionEntity.status == "WAITING",
                col(StepExecutionEntity.wait_kind).is_not(None),
                col(StepExecutionEntity.started_at).is_not(None),
            )
            .group_by(StepExecutionEntity.wait_kind)
        )
    ).all()
    outbox_row = (
        await session.exec(
            select(func.count(), func.min(TaskOutboxEntity.created_at)).where(
                col(TaskOutboxEntity.published_at).is_(None)
            )
        )
    ).one()
    compensation_rows = (
        await session.exec(
            select(CompensationRecordEntity.status, func.count())
            .where(
                col(CompensationRecordEntity.status).in_(
                    ["PENDING", "RUNNING", "EXECUTING", "FAILED"]
                )
            )
            .group_by(CompensationRecordEntity.status)
        )
    ).all()
    return build_operational_snapshot(
        now=now,
        cartable_rows=cartable_rows,
        wait_rows=wait_rows,
        outbox_row=outbox_row,
        compensation_rows=compensation_rows,
    )
