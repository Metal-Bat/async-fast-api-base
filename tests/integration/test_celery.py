"""Integration tests for task persistence, scheduling, and concurrency."""

import os
from datetime import timedelta
from unittest.mock import Mock
from uuid import UUID, uuid7

import pytest
from anyio import create_task_group
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import core.celery_scheduler as scheduler
import core.task_lifecycle as lifecycle
from apps.tasks.application import idempotency, outbox
from apps.tasks.domain.entity import (
    PeriodicTaskEntity,
    TaskExecutionEntity,
    TaskIdempotencyEntity,
    TaskOutboxEntity,
)
from core.celery_app import celery_app
from core.settings import settings
from utils.date_utils import get_datetime_utc

pytestmark = [
    pytest.mark.integration,
    pytest.mark.anyio,
    pytest.mark.skipif(
        os.getenv("RUN_CELERY_INTEGRATION") != "1",
        reason="requires disposable Celery test infrastructure",
    ),
]


@pytest.fixture
async def database(monkeypatch):
    engine = create_async_engine(settings.DATABASE_DSN, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    for module in (idempotency, outbox, scheduler, lifecycle):
        monkeypatch.setattr(module, "SessionFactory", factory)
    try:
        yield factory, engine
    finally:
        await engine.dispose()


async def test_claim_race_retry_stale_release_and_success_replay(database) -> None:
    key = uuid7()
    claims = []

    async def claim():
        claims.append(await idempotency.acquire_task(key, "same-task-id", 1260))

    async with create_task_group() as group:
        for _ in range(12):
            group.start_soon(claim)
    winners = [item for item in claims if item.acquired]
    assert len(winners) == 1
    original = winners[0]
    await idempotency.release_task(original)
    replacement = await idempotency.acquire_task(key, "same-task-id", 1260)
    assert replacement.acquired and replacement.owner_token != original.owner_token
    await idempotency.release_task(original)
    assert not (await idempotency.acquire_task(key, "duplicate", 1260)).acquired
    with pytest.raises(RuntimeError, match="ownership changed"):
        await idempotency.complete_task(original, "stale")
    await idempotency.complete_task(replacement, {"saved": True})
    await idempotency.release_task(replacement)
    duplicate = await idempotency.acquire_task(key, "new-id", 1260)
    assert duplicate.completed and duplicate.result == {"saved": True}


async def test_expired_claim_recovers_unfinished_history(database) -> None:
    factory, _ = database
    key, task_id = uuid7(), str(uuid7())
    claim = await idempotency.acquire_task(key, task_id, 1260)
    async with factory() as session:
        row = (
            await session.exec(
                select(TaskIdempotencyEntity).where(
                    TaskIdempotencyEntity.key == key,
                )
            )
        ).one()
        row.expires_at = get_datetime_utc() - timedelta(seconds=1)
        session.add(row)
        session.add(TaskExecutionEntity(task_id=task_id, task_name="test.kill", status="STARTED"))
        await session.commit()
    await scheduler.recover_expired_tasks()
    async with factory() as session:
        history = (
            await session.exec(
                select(TaskExecutionEntity).where(
                    TaskExecutionEntity.task_id == task_id,
                )
            )
        ).one()
        assert history.status == "FAILURE"
        assert (
            await session.exec(
                select(TaskIdempotencyEntity).where(
                    TaskIdempotencyEntity.key == key,
                )
            )
        ).one_or_none() is None
    replacement = await idempotency.acquire_task(key, task_id, 1260)
    assert replacement.acquired
    await idempotency.release_task(claim)
    await idempotency.release_task(replacement)


async def test_only_one_scheduler_commits_one_off_occurrence(database) -> None:
    factory, _ = database
    owners, winners = [uuid7(), uuid7()], []

    async def acquire(owner):
        if await scheduler._claim_leader(owner):
            winners.append(owner)

    async with create_task_group() as group:
        for owner in owners:
            group.start_soon(acquire, owner)
    assert len(winners) == 1
    model = PeriodicTaskEntity(
        name=str(uuid7()),
        task_name="system.ping",
        queue=settings.CELERY_DEFAULT_QUEUE,
        schedule_type="clocked",
        clocked_at=get_datetime_utc() - timedelta(seconds=1),
        one_off=True,
    )
    async with factory() as session:
        session.add(model)
        await session.commit()
    try:
        async with create_task_group() as group:
            for owner in owners:
                group.start_soon(scheduler._enqueue_due, owner, celery_app)
        async with factory() as session:
            stored = await session.get(PeriodicTaskEntity, model.id)
            assert stored is not None and stored.total_run_count == 1 and not stored.enabled
            messages = (await session.exec(select(TaskOutboxEntity))).all()
            matching = [item for item in messages if item.task_name == model.task_name]
            assert len(matching) == 1
            assert UUID(str(matching[0].headers["idempotency_key"])).version == 7
            # Keep later tests' outbox isolated from this scheduled message.
            await session.delete(matching[0])
            await session.commit()
    finally:
        await scheduler._release_leader(winners[0])


async def test_outbox_survives_publish_then_commit_failure(database, monkeypatch) -> None:
    factory, engine = database
    async with factory() as session:
        message = outbox.enqueue_task(session, "system.ping")
        await session.commit()
    published_ids = []
    publish = Mock(side_effect=lambda _app, item: published_ids.append(item.task_id))
    monkeypatch.setattr(outbox, "_publish", publish)

    def abort_commit(_connection):
        raise RuntimeError("process lost before publication commit")

    event.listen(engine.sync_engine, "commit", abort_commit)
    try:
        with pytest.raises(RuntimeError, match="process lost"):
            await outbox.dispatch_outbox(celery_app)
    finally:
        event.remove(engine.sync_engine, "commit", abort_commit)
    assert await outbox.dispatch_outbox(celery_app) == 1
    assert published_ids == [message.task_id, message.task_id]
    async with factory() as session:
        stored = (
            await session.exec(
                select(TaskOutboxEntity).where(
                    TaskOutboxEntity.task_id == message.task_id,
                )
            )
        ).one()
        assert stored.published_at is not None


async def test_rolled_back_submission_never_reaches_outbox(database) -> None:
    factory, _ = database
    async with factory() as session:
        message = outbox.enqueue_task(session, "system.ping")
        await session.flush()
        task_id = message.task_id
        await session.rollback()
    async with factory() as session:
        assert (
            await session.exec(
                select(TaskOutboxEntity).where(
                    col(TaskOutboxEntity.task_id) == task_id,
                )
            )
        ).one_or_none() is None


async def test_previous_attempt_cannot_overwrite_a_newer_attempt_history(database) -> None:
    factory, _ = database
    task_id = str(uuid7())
    await lifecycle._record(task_id, task_name="system.ping", status="STARTED", retries=1)
    await lifecycle._record(task_id, task_name="system.ping", status="RETRY", retries=0)
    async with factory() as session:
        record = (
            await session.exec(
                select(TaskExecutionEntity).where(
                    TaskExecutionEntity.task_id == task_id,
                )
            )
        ).one()
        assert record.status == "STARTED" and record.retries == 1
