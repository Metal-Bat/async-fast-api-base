import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any, override
from uuid import UUID, uuid7

import structlog
from celery.beat import ScheduleEntry, Scheduler
from celery.schedules import crontab, schedule
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import ProgrammingError
from sqlmodel import col, delete, select, update

from apps.processes.application.operations import collect_operational_snapshot
from apps.processes.application.waits import claim_due_actions
from apps.processes.domain.entity import StepExecutionAttemptEntity
from apps.reporting.domain.entity import ReportEntity, ReportStatus
from apps.tasks.application.outbox import dispatch_outbox, enqueue_task
from apps.tasks.domain.entity import (
    PeriodicTaskEntity,
    SchedulerLeaseEntity,
    TaskExecutionEntity,
    TaskIdempotencyEntity,
)
from core.bpms_observability import bpms_telemetry
from core.deps import SessionFactory, engine
from core.settings import settings
from utils.date_utils import get_datetime_utc

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)
_LEASE_NAME = "celery.scheduler"


async def _claim_leader(owner_id: UUID) -> bool:
    """Atomically renew our lease or take an expired lease; concurrent contenders cannot win."""
    now = get_datetime_utc()
    expires_at = now + timedelta(seconds=max(settings.CELERY_BEAT_POLL_SECONDS * 3, 30))
    statement = (
        insert(SchedulerLeaseEntity)
        .values(
            name=_LEASE_NAME,
            owner_id=owner_id,
            expires_at=expires_at,
        )
        .on_conflict_do_update(
            index_elements=[SchedulerLeaseEntity.name],
            set_={"OWNER_ID": owner_id, "EXPIRES_AT": expires_at},
            where=(col(SchedulerLeaseEntity.owner_id) == owner_id)
            | (col(SchedulerLeaseEntity.expires_at) <= now),
        )
        .returning(col(SchedulerLeaseEntity.owner_id))
    )
    async with SessionFactory() as session:
        acquired = (await session.exec(statement)).first() is not None
        await session.commit()
        return acquired


async def _release_leader(owner_id: UUID) -> None:
    """Release only this scheduler's lease, leaving a replacement leader untouched."""
    async with SessionFactory() as session:
        await session.exec(
            delete(SchedulerLeaseEntity).where(
                col(SchedulerLeaseEntity.name) == _LEASE_NAME,
                col(SchedulerLeaseEntity.owner_id) == owner_id,
            )
        )
        await session.commit()


@contextmanager
def scheduler_lifecycle(runner: asyncio.Runner, owner_id: UUID) -> Iterator[bool]:
    """Release leadership on any tick error; successful ticks retain the renewable lease."""
    try:
        acquired = runner.run(_claim_leader(owner_id))
        yield acquired
    except BaseException as exc:
        if isinstance(exc, ProgrammingError) and getattr(exc.orig, "sqlstate", None) in {
            "42P01",  # undefined table
            "42703",  # undefined column
        }:
            logger.warning(
                "scheduler.migrations_required",
                message="Database schema is missing or outdated. Run `mise run migrate` manually.",
                owner_id=str(owner_id),
            )
        else:
            logger.error(
                "scheduler.tick_failed",
                owner_id=str(owner_id),
                error_type=type(exc).__name__,
                exc_info=exc,
            )
        # Also attempt cleanup after an ambiguous acquisition commit.
        try:
            runner.run(_release_leader(owner_id))
        except Exception as cleanup_error:
            logger.error(
                "scheduler.release_failed",
                error_type=type(cleanup_error).__name__,
                exc_info=cleanup_error,
            )
        raise


def _entry(model: PeriodicTaskEntity, app: Any) -> ScheduleEntry:
    now = get_datetime_utc()
    if model.schedule_type == "crontab":
        task_schedule = crontab(
            minute=model.cron_minute or "*",
            hour=model.cron_hour or "*",
            day_of_week=model.cron_day_of_week or "*",
            day_of_month=model.cron_day_of_month or "*",
            month_of_year=model.cron_month_of_year or "*",
        )
    elif model.schedule_type == "clocked":
        task_schedule = schedule(timedelta(0))
    else:
        task_schedule = schedule(model.interval_seconds or 60.0)
    return ScheduleEntry(
        name=model.name,
        task=model.task_name,
        schedule=task_schedule,
        args=tuple(model.args),
        kwargs=model.kwargs,
        options={"queue": model.queue, "headers": model.headers},
        last_run_at=model.last_run_at or model.start_at or model.created_at or now,
        total_run_count=model.total_run_count,
        app=app,
    )


async def _enqueue_due(owner_id: UUID, app: Any) -> dict[str, ScheduleEntry]:
    """Commit each schedule occurrence and its message together, fenced by the leader row."""
    entries: dict[str, ScheduleEntry] = {}
    async with SessionFactory() as session, session.begin():
        leader = (
            await session.exec(
                select(SchedulerLeaseEntity)
                .where(
                    col(SchedulerLeaseEntity.name) == _LEASE_NAME,
                    col(SchedulerLeaseEntity.owner_id) == owner_id,
                    col(SchedulerLeaseEntity.expires_at) > get_datetime_utc(),
                )
                .with_for_update()
            )
        ).one_or_none()
        if leader is None:
            return entries
        models = (
            await session.exec(
                select(PeriodicTaskEntity)
                .where(
                    col(PeriodicTaskEntity.enabled).is_(True),
                    col(PeriodicTaskEntity.deleted_at).is_(None),
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        now = get_datetime_utc()
        for model in models:
            if model.start_at and model.start_at > now:
                continue
            if model.expires_at and model.expires_at <= now:
                continue
            entry = _entry(model, app)
            entries[model.name] = entry
            if model.schedule_type == "clocked":
                due = model.clocked_at is not None and model.clocked_at <= now
            else:
                due = entry.is_due().is_due
            if not due:
                continue
            occurrence = model.total_run_count + 1
            message = enqueue_task(
                session,
                model.task_name,
                args=model.args,
                kwargs=model.kwargs,
                queue=model.queue,
            )
            model.last_run_at = now
            model.total_run_count = occurrence
            if model.one_off:
                model.enabled = False
            session.add(model)
            logger.info("scheduler.enqueued", schedule_id=str(model.id), task_id=message.task_id)
    return entries


async def recover_expired_tasks() -> None:
    """Clear leases left by hard-killed workers and mark their unfinished history as failed."""
    now = get_datetime_utc()
    async with SessionFactory() as session, session.begin():
        expired = (
            await session.exec(
                select(TaskIdempotencyEntity)
                .where(
                    col(TaskIdempotencyEntity.expires_at) <= now,
                )
                .with_for_update(skip_locked=True)
                .limit(100)
            )
        ).all()
        for claim in expired:
            if claim.status == "RUNNING":
                await session.exec(
                    update(TaskExecutionEntity)
                    .where(
                        col(TaskExecutionEntity.task_id) == claim.task_id,
                        col(TaskExecutionEntity.status) == "STARTED",
                    )
                    .values(
                        status="FAILURE",
                        finished_at=now,
                        result={
                            "exception_type": "TaskLeaseExpired",
                            "message": "Worker stopped before task finalization",
                        },
                    )
                )
                report = (
                    await session.exec(
                        select(ReportEntity)
                        .where(
                            col(ReportEntity.task_id) == claim.task_id,
                            col(ReportEntity.status) == ReportStatus.PROCESSING,
                        )
                        .with_for_update()
                    )
                ).one_or_none()
                if report is not None:
                    report.status = ReportStatus.FAILED
                    report.completed_at = now
                    report.error_code = "TaskLeaseExpired"
                    report.error_message = "Worker stopped before report finalization"
                    session.add(report)
                try:
                    attempt_id = UUID(claim.task_id)
                except ValueError:
                    attempt_id = None
                if attempt_id is not None:
                    attempt = await session.get(
                        StepExecutionAttemptEntity,
                        attempt_id,
                        with_for_update=True,
                        populate_existing=True,
                    )
                    if attempt is not None and attempt.status == "RUNNING":
                        attempt.status = "WAITING"
                        session.add(attempt)
                logger.warning("task.expired_lease_recovered", task_id=claim.task_id)
            await session.delete(claim)


async def _record_operational_snapshot() -> bool:
    """Publish aggregate BPMS state without disrupting scheduling when monitoring fails."""
    try:
        async with SessionFactory() as session:
            snapshot = await collect_operational_snapshot(session)
        with bpms_telemetry.start_span("scheduler.snapshot", component="scheduler"):
            bpms_telemetry.record_snapshot(snapshot)
        return True
    except Exception as exc:  # noqa: BLE001 - telemetry must not stop durable scheduling
        bpms_telemetry.log_failure("scheduler", "snapshot_failed", exc)
        return False


class DatabaseScheduler(Scheduler):
    """Poll schedules and drain committed messages even while the broker is recovering."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._async_runner = asyncio.Runner()
        self._leader_id = uuid7()
        self._closed = False
        self._is_leader = False
        try:
            super().__init__(*args, **kwargs)
        except BaseException:
            self.close()
            raise

    @override
    def setup_schedule(self) -> None:
        self.schedule = {}

    @override
    def tick(self, *args: Any, **kwargs: Any) -> float:
        with tracer.start_as_current_span("scheduler.tick") as span:
            span.set_attribute("scheduler.owner.id", str(self._leader_id))
            try:
                with scheduler_lifecycle(self._async_runner, self._leader_id) as leader:
                    if leader != self._is_leader:
                        logger.info(
                            "scheduler.leadership_changed",
                            leader=leader,
                            owner_id=str(self._leader_id),
                        )
                    self._is_leader = leader
                    span.set_attribute("scheduler.is_leader", leader)
                    if leader:
                        self.schedule = self._async_runner.run(
                            _enqueue_due(self._leader_id, self.app)
                        )
                        self._async_runner.run(recover_expired_tasks())
                        claimed = self._async_runner.run(claim_due_actions(self._leader_id))
                        span.set_attribute("bpms.scheduled_actions.claimed", len(claimed))
                        self._async_runner.run(_record_operational_snapshot())
                    span.set_attribute("scheduler.entries.count", len(self.schedule))
                    # Row locks make publication safe across leader changes and concurrent dispatchers.
                    published = self._async_runner.run(dispatch_outbox(self.app))
                    span.set_attribute("messaging.batch.message_count", published)
            except Exception as exc:  # noqa: BLE001 - lifecycle logs and beat keeps polling
                self._is_leader = False
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
        return settings.CELERY_BEAT_POLL_SECONDS

    @override
    def close(self) -> None:
        """Release leadership and close the runner even if database cleanup fails."""
        if self._closed:
            return
        self._closed = True
        try:
            self._async_runner.run(_release_leader(self._leader_id))
            logger.info("scheduler.state_released", owner_id=str(self._leader_id))
        except Exception as exc:
            logger.error("scheduler.release_failed", error_type=type(exc).__name__, exc_info=exc)
        finally:
            try:
                self._async_runner.run(engine.dispose())
            finally:
                self._async_runner.close()
                logger.info("scheduler.resources_closed", owner_id=str(self._leader_id))
                super().close()
