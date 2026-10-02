"""Integration tests against a real Celery worker."""

import asyncio
import os
import subprocess
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid7

import pytest
from redis import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import core.celery_scheduler as scheduler
from apps.tasks.application import outbox
from apps.tasks.application.outbox import dispatch_outbox, enqueue_task
from apps.tasks.domain.entity import TaskExecutionEntity, TaskIdempotencyEntity
from core.celery_app import celery_app
from core.settings import settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_CELERY_INTEGRATION") != "1",
        reason="requires disposable Celery test infrastructure",
    ),
]


@pytest.fixture(scope="module")
def worker(tmp_path_factory):
    directory = tmp_path_factory.mktemp("celery-worker")
    queue = f"probe.{uuid7()}"
    hostname = f"{queue}@localhost"
    environment = dict(
        os.environ,
        CELERY_TASK_LEASE_GRACE_SECONDS="1",
        PYTHONPATH=os.pathsep.join([str(Path("src").resolve()), str(Path("tests").resolve())]),
    )
    with (directory / "worker.log").open("w") as log:
        process = subprocess.Popen(
            [
                "celery",
                "--app=core.celery_app:celery_app",
                "worker",
                "--pool=prefork",
                "--concurrency=1",
                "--loglevel=INFO",
                "--without-gossip",
                "--without-mingle",
                f"--queues={queue}",
                f"--hostname={hostname}",
                "--include=integration.celery_probe_tasks",
            ],
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = monotonic() + 30
            while monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail((directory / "worker.log").read_text())
                if celery_app.control.inspect(destination=[hostname], timeout=1).ping():
                    break
                sleep(0.2)
            else:
                pytest.fail(
                    "Probe worker failed to start: " + (directory / "worker.log").read_text()
                )
            yield queue
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


async def _history(task_id: str) -> TaskExecutionEntity | None:
    engine = create_async_engine(settings.DATABASE_DSN, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            return (
                await session.exec(
                    select(TaskExecutionEntity).where(
                        TaskExecutionEntity.task_id == task_id,
                    )
                )
            ).one_or_none()
    finally:
        await engine.dispose()


def _wait_history(task_id: str, status: str) -> TaskExecutionEntity:
    deadline = monotonic() + 15
    while monotonic() < deadline:
        record = asyncio.run(_history(task_id))
        if record is not None and record.status == status:
            return record
        sleep(0.1)
    pytest.fail(f"Task {task_id} did not reach durable state {status}")


def test_worker_retry_and_duplicate_execute_side_effect_once(worker) -> None:
    key = f"probe:{uuid7()}"
    first = celery_app.send_task(
        "probe.count", args=[key, True], queue=worker, headers={"idempotency_key": key}
    )
    assert first.get(timeout=20, disable_sync_subtasks=False) == 1
    history = _wait_history(first.id, "SUCCESS")
    assert history.retries == 1
    duplicate = celery_app.send_task(
        "probe.count", args=[key], queue=worker, headers={"idempotency_key": key}
    )
    assert duplicate.get(timeout=15, disable_sync_subtasks=False) == 1
    with Redis.from_url(str(settings.CACHE_DSN)) as cache:
        assert cache.get(key) == b"1"
        cache.delete(key)


def test_actual_soft_timeout_releases_claim_and_records_failure(worker) -> None:
    result = celery_app.send_task("probe.soft", queue=worker)
    error = result.get(timeout=15, propagate=False, disable_sync_subtasks=False)
    assert type(error).__name__ == "SoftTimeLimitExceeded"
    history = _wait_history(result.id, "FAILURE")
    assert isinstance(history.result, dict)
    assert history.result["exception_type"] == "SoftTimeLimitExceeded"


def test_actual_hard_kill_is_recovered_after_lease_expiration(worker, monkeypatch) -> None:
    result = celery_app.send_task("probe.hard", queue=worker)
    error = result.get(timeout=15, propagate=False, disable_sync_subtasks=False)
    assert type(error).__name__ == "TimeLimitExceeded"
    sleep(2)

    async def recover():
        engine = create_async_engine(settings.DATABASE_DSN, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr(scheduler, "SessionFactory", factory)
        try:
            await scheduler.recover_expired_tasks()
            async with factory() as session:
                assert (
                    await session.exec(
                        select(TaskIdempotencyEntity).where(
                            TaskIdempotencyEntity.task_id == result.id,
                        )
                    )
                ).one_or_none() is None
        finally:
            await engine.dispose()

    asyncio.run(recover())
    history = _wait_history(result.id, "FAILURE")
    assert isinstance(history.result, dict)
    assert history.result["exception_type"] == "TaskLeaseExpired"


def test_committed_outbox_reaches_real_worker(worker, monkeypatch) -> None:
    async def submit():
        engine = create_async_engine(settings.DATABASE_DSN, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        monkeypatch.setattr(outbox, "SessionFactory", factory)
        try:
            async with factory() as session:
                message = enqueue_task(session, "system.ping", queue=worker)
                await session.commit()
            assert await dispatch_outbox(celery_app) == 1
            return message.task_id
        finally:
            await engine.dispose()

    task_id = asyncio.run(submit())
    history = _wait_history(task_id, "SUCCESS")
    assert history.result == {"status": "ok"}
