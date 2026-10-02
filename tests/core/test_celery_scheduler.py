"""Tests for scheduler leadership and transactional outbox dispatch."""

import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from sqlalchemy.exc import ProgrammingError

import core.celery_scheduler as scheduler
from apps.tasks.application import outbox
from apps.tasks.domain.entity import TaskOutboxEntity
from core.celery_app import celery_app
from utils.date_utils import get_datetime_utc


@pytest.mark.parametrize("sqlstate", ["42P01", "42703", "42601"])
def test_scheduler_warns_only_for_missing_schema(monkeypatch, sqlstate) -> None:
    class DatabaseError(Exception):
        sqlstate: str

    original = DatabaseError("database error")
    original.sqlstate = sqlstate
    error = ProgrammingError("statement", {}, original)
    monkeypatch.setattr(scheduler, "_claim_leader", AsyncMock(side_effect=error))
    monkeypatch.setattr(scheduler, "_release_leader", AsyncMock())
    log = Mock()
    monkeypatch.setattr(scheduler, "logger", log)
    with (
        asyncio.Runner() as runner,
        pytest.raises(ProgrammingError),
        scheduler.scheduler_lifecycle(runner, uuid7()),
    ):
        pytest.fail("A failed lease claim must not proceed")
    if sqlstate in {"42P01", "42703"}:
        assert log.warning.call_args.args == ("scheduler.migrations_required",)
        assert "mise run migrate" in log.warning.call_args.kwargs["message"]
        log.error.assert_not_called()
    else:
        log.warning.assert_not_called()
        assert log.error.call_args.args == ("scheduler.tick_failed",)


def test_scheduler_error_releases_leadership(monkeypatch) -> None:
    claim, release = AsyncMock(return_value=True), AsyncMock()
    monkeypatch.setattr(scheduler, "_claim_leader", claim)
    monkeypatch.setattr(scheduler, "_release_leader", release)
    owner = uuid7()
    with (
        asyncio.Runner() as runner,
        pytest.raises(ValueError, match="tick failed"),
        scheduler.scheduler_lifecycle(runner, owner) as leader,
    ):
        assert leader
        raise ValueError("tick failed")
    release.assert_awaited_once_with(owner)


def test_scheduler_close_always_closes_runner(monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "_release_leader", AsyncMock(side_effect=ConnectionError()))
    monkeypatch.setattr(scheduler, "engine", Mock(dispose=AsyncMock()))
    beat = scheduler.DatabaseScheduler(app=celery_app, lazy=True)
    beat.close()
    beat.close()
    with pytest.raises(RuntimeError, match="closed"):
        beat._async_runner.get_loop()


def test_scheduler_keeps_polling_after_database_failure(monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "_claim_leader", AsyncMock(side_effect=ConnectionError()))
    monkeypatch.setattr(scheduler, "_release_leader", AsyncMock())
    monkeypatch.setattr(scheduler, "engine", Mock(dispose=AsyncMock()))
    beat = scheduler.DatabaseScheduler(app=celery_app, lazy=True)
    try:
        assert beat.tick() == scheduler.settings.CELERY_BEAT_POLL_SECONDS
        assert not beat._is_leader
    finally:
        beat.close()


def test_scheduler_tick_is_traced_with_leadership_and_dispatch_count(monkeypatch) -> None:
    monkeypatch.setattr(scheduler, "_claim_leader", AsyncMock(return_value=True))
    monkeypatch.setattr(scheduler, "_enqueue_due", AsyncMock(return_value={"hourly": Mock()}))
    monkeypatch.setattr(scheduler, "recover_expired_tasks", AsyncMock())
    monkeypatch.setattr(scheduler, "claim_due_actions", AsyncMock(return_value=[uuid7()] * 3))
    monkeypatch.setattr(scheduler, "dispatch_outbox", AsyncMock(return_value=2))
    snapshot = AsyncMock()
    monkeypatch.setattr(scheduler, "_record_operational_snapshot", snapshot)
    monkeypatch.setattr(scheduler, "_release_leader", AsyncMock())
    monkeypatch.setattr(scheduler, "engine", Mock(dispose=AsyncMock()))
    span = Mock()
    span_context = Mock()
    span_context.__enter__ = Mock(return_value=span)
    span_context.__exit__ = Mock(return_value=False)
    start_span = Mock(return_value=span_context)
    monkeypatch.setattr(scheduler.tracer, "start_as_current_span", start_span)
    beat = scheduler.DatabaseScheduler(app=celery_app, lazy=True)
    try:
        beat.tick()
    finally:
        beat.close()

    start_span.assert_called_once_with("scheduler.tick")
    span.set_attribute.assert_any_call("scheduler.is_leader", True)
    span.set_attribute.assert_any_call("scheduler.entries.count", 1)
    span.set_attribute.assert_any_call("bpms.scheduled_actions.claimed", 3)
    span.set_attribute.assert_any_call("messaging.batch.message_count", 2)
    snapshot.assert_awaited_once_with()


@pytest.mark.anyio
async def test_operational_snapshot_failure_is_redacted_and_does_not_break_scheduler(
    monkeypatch,
) -> None:
    session = AsyncMock()
    session.__aenter__.return_value = session
    monkeypatch.setattr(scheduler, "SessionFactory", Mock(return_value=session))
    monkeypatch.setattr(
        scheduler,
        "collect_operational_snapshot",
        AsyncMock(side_effect=ConnectionError("password=secret")),
    )
    telemetry = Mock()
    monkeypatch.setattr(scheduler, "bpms_telemetry", telemetry)

    assert await scheduler._record_operational_snapshot() is False

    telemetry.log_failure.assert_called_once()
    assert telemetry.log_failure.call_args.args[:2] == ("scheduler", "snapshot_failed")


@pytest.mark.anyio
async def test_outbox_publish_failure_preserves_pending_message(monkeypatch) -> None:
    message = TaskOutboxEntity(
        task_id="stable-id",
        task_name="system.ping",
        queue="default",
        available_at=get_datetime_utc(),
    )
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.begin = Mock(return_value=AsyncMock())
    session.add = Mock()
    session.exec.side_effect = [
        Mock(one_or_none=Mock(return_value=message)),
        Mock(one_or_none=Mock(return_value=None)),
    ]
    monkeypatch.setattr(outbox, "SessionFactory", Mock(return_value=session))
    monkeypatch.setattr(outbox, "_publish", Mock(side_effect=ConnectionError("broker down")))
    before = get_datetime_utc()
    assert await outbox.dispatch_outbox(Mock()) == 0
    assert message.task_id == "stable-id"
    assert message.published_at is None
    assert message.attempts == 1 and message.available_at > before
    assert message.last_error == "ConnectionError"


@pytest.mark.anyio
async def test_outbox_marks_success_only_after_publication(monkeypatch) -> None:
    message = TaskOutboxEntity(
        task_id="stable-id",
        task_name="system.ping",
        queue="default",
        available_at=get_datetime_utc(),
    )
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.begin = Mock(return_value=AsyncMock())
    session.add = Mock()
    session.exec.side_effect = [
        Mock(one_or_none=Mock(return_value=message)),
        Mock(one_or_none=Mock(return_value=None)),
    ]
    monkeypatch.setattr(outbox, "SessionFactory", Mock(return_value=session))

    def publish(_app, item):
        assert item.published_at is None

    monkeypatch.setattr(outbox, "_publish", publish)
    assert await outbox.dispatch_outbox(Mock()) == 1
    assert message.published_at is not None
    assert message.last_error is None
