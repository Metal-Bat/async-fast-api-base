"""Real worker warm drain and durable delivery after restart on the supported schema."""

import asyncio
import os
import subprocess
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid7

import pytest
from redis import Redis

from apps.tasks.application.outbox import dispatch_outbox, enqueue_task
from core.celery_app import celery_app
from core.deps import SessionFactory, engine
from core.settings import settings
from tests.integration.test_celery_worker import _wait_history

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_CELERY_INTEGRATION") != "1",
        reason="requires disposable worker infrastructure",
    ),
]


def test_worker_drains_then_consumes_committed_work_after_restart(tmp_path) -> None:
    queue = f"drain.{uuid7()}"
    hostname = f"{queue}@localhost"
    key = f"probe:{uuid7()}"
    environment = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(Path("src").resolve()), str(Path("tests").resolve())]),
    )
    command = [
        "celery",
        "--app=core.celery_app:celery_app",
        "worker",
        "--pool=prefork",
        "--concurrency=1",
        "--loglevel=WARNING",
        "--without-gossip",
        "--without-mingle",
        f"--queues={queue}",
        f"--hostname={hostname}",
        "--include=integration.celery_probe_tasks",
    ]
    process = None
    with (
        (tmp_path / "worker.log").open("w") as log,
        Redis.from_url(str(settings.CACHE_DSN)) as cache,
    ):

        def start():
            worker = subprocess.Popen(
                command, env=environment, stdout=log, stderr=subprocess.STDOUT
            )
            deadline = monotonic() + 20
            while monotonic() < deadline:
                if worker.poll() is not None:
                    pytest.fail("Worker exited before becoming ready")
                if celery_app.control.inspect(destination=[hostname], timeout=1).ping():
                    return worker
                sleep(0.1)
            worker.terminate()
            worker.wait(timeout=10)
            pytest.fail("Worker did not become ready")

        try:
            process = start()
            result = celery_app.send_task(
                "probe.drain", args=[key], queue=queue, headers={"idempotency_key": key}
            )
            deadline = monotonic() + 10
            while not cache.exists(f"{key}:started") and monotonic() < deadline:
                sleep(0.05)
            assert cache.exists(f"{key}:started")
            process.terminate()
            assert process.wait(timeout=15) == 0
            assert result.get(timeout=10, disable_sync_subtasks=False) == 1
            assert _wait_history(result.id, "SUCCESS")

            async def stage_and_publish():
                async with SessionFactory() as session:
                    message = enqueue_task(session, "system.ping", queue=queue)
                    await session.commit()
                await dispatch_outbox(celery_app)
                await engine.dispose()
                return message.task_id

            task_id = asyncio.run(stage_and_publish())
            process = start()
            assert _wait_history(task_id, "SUCCESS").result == {"status": "ok"}
            duplicate = celery_app.send_task(
                "probe.drain", args=[key], queue=queue, headers={"idempotency_key": key}
            )
            assert duplicate.get(timeout=10, disable_sync_subtasks=False) == 1
            assert cache.get(key) == b"1"
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            cache.delete(key, f"{key}:started")
