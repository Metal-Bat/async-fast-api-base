"""Pause only independently owned worker/broker resources, then recover a scheduled notice."""

import json
import os
import signal
import subprocess
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid7

import anyio
import pytest
from celery import Celery
from sqlmodel import col, select

from apps.calendar.application.service import CalendarService
from apps.calendar.domain.reminder import CalendarReminderEntity
from apps.notifications.domain.entity import NotificationEntity
from apps.tasks.application import outbox
from apps.tasks.domain.entity import PeriodicTaskEntity, TaskOutboxEntity
from apps.users.domain.entity import UserEntity
from core.celery_scheduler import _claim_leader, _enqueue_due, _release_leader
from core.deps import SessionFactory, engine
from core.ref_id import open_ref_id
from tests.integration.test_calendar_reminders import reminder_event
from utils.date_utils import get_datetime_utc

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_NOTIFICATION_WORKER") != "1",
        reason="requires owned worker and HTTPS email gateway",
    ),
]


def checked_container_action(identity: str, owner: str, action: str) -> None:
    """Refuse changed ownership before a bounded pause/unpause of the exact container."""
    assert action in {"pause", "unpause"}
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            '{"id":{{json .Id}},"owner":{{json (index .Config.Labels "app-be-owner")}}}',
            identity,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert json.loads(result.stdout) == {"id": identity, "owner": owner}
    subprocess.run(["docker", action, identity], check=True, capture_output=True, timeout=10)


def checked_worker_signal(resources, value: signal.Signals) -> None:
    """Verify the observed process start identity, parent and worker arguments before signaling."""
    pid = resources["worker_pid"]
    path = Path(f"/proc/{pid}")
    fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
    assert fields[19] == resources["worker_start_identity"]
    assert int(fields[1]) == resources["supervisor_pid"]
    parent = Path(f"/proc/{resources['supervisor_pid']}/stat").read_text().rsplit(")", 1)[1].split()
    assert parent[19] == resources["supervisor_start_identity"]
    args = (path / "cmdline").read_bytes().split(b"\0")
    assert b"celery" in args and b"core.celery_app:celery_app" in args
    os.kill(pid, value)


@pytest.mark.anyio
async def test_actual_broker_worker_interruption_and_scheduler_replacement_recover_once():
    assert os.environ["POSTGRES_DB"] == os.environ["FLOW_TEST_OWNED_DATABASE"]
    resources = json.loads(os.environ["FLOW_TEST_RESOURCES"])
    assert resources["database"] == os.environ["FLOW_TEST_OWNED_DATABASE"]
    first, replacement = uuid7(), uuid7()
    try:
        with nullcontext(dict(os.environ)) as configured:
            cache = next(item for item in resources["containers"] if "-cache-" in item["name"])
            worker_paused = broker_paused = False
            with Celery(
                "owned_recovery", broker=configured["CELERY_BROKER_URL"], set_as_current=False
            ) as app:
                app.conf.broker_write_url = configured["CELERY_BROKER_URL"]
                app.conf.broker_read_url = configured["CELERY_BROKER_URL"]
                assert app.conf.broker_write_url == configured["CELERY_BROKER_URL"]
                app.conf.broker_transport_options = {
                    "socket_connect_timeout": 1,
                    "socket_timeout": 1,
                }
                try:
                    checked_worker_signal(resources, signal.SIGSTOP)
                    worker_paused = True
                    async with SessionFactory() as session, session.begin():
                        actor = UserEntity(
                            username="recover-worker-" + uuid7().hex, hashed_password=uuid7().hex
                        )
                        session.add(actor)
                        await session.flush()
                        event = await CalendarService(session).create(
                            reminder_event("real-interruption", reminder_offsets=[0]), actor
                        )
                        reminder = (
                            await session.exec(
                                select(CalendarReminderEntity).where(
                                    CalendarReminderEntity.source_id == open_ref_id(event.ref_id)[0]
                                )
                            )
                        ).one()
                        identity = reminder.id
                        schedule = await session.get(PeriodicTaskEntity, reminder.schedule_id)
                        assert schedule is not None
                        schedule.queue = configured["CELERY_AUTOMATION_QUEUE"]
                    assert await _claim_leader(first)
                    await _enqueue_due(first, app)
                    await _release_leader(first)
                    assert await _claim_leader(replacement)
                    await _enqueue_due(replacement, app)
                    await _release_leader(replacement)
                    checked_container_action(cache["id"], resources["owner_label"], "pause")
                    broker_paused = True
                    assert await outbox.dispatch_outbox(app) == 0
                    async with SessionFactory() as session, session.begin():
                        messages = (
                            await session.exec(
                                select(TaskOutboxEntity).where(
                                    TaskOutboxEntity.task_name == "bpms.fire_calendar_reminder",
                                    col(TaskOutboxEntity.kwargs)["reminder_id"].as_string()
                                    == str(identity),
                                )
                            )
                        ).all()
                        assert len(messages) == 1
                        message = messages[0]
                        message_id, task_id = message.id, message.task_id
                        assert message.published_at is None and message.attempts == 1
                        message.available_at = get_datetime_utc()
                    checked_container_action(cache["id"], resources["owner_label"], "unpause")
                    broker_paused = False
                    assert await outbox.dispatch_outbox(app) >= 1
                    async with SessionFactory() as session:
                        row = await session.get(CalendarReminderEntity, identity)
                        assert row is not None and row.status == "PENDING"
                    checked_worker_signal(resources, signal.SIGCONT)
                    worker_paused = False
                    for _ in range(150):
                        async with SessionFactory() as session:
                            row = await session.get(CalendarReminderEntity, identity)
                            assert row is not None
                            if row.status == "SENT":
                                break
                        await anyio.sleep(0.2)
                    assert row.status == "SENT"
                    async with SessionFactory() as session:
                        message = await session.get(TaskOutboxEntity, message_id)
                        assert message is not None and message.task_id == task_id
                        await anyio.to_thread.run_sync(outbox._publish, app, message)
                    await anyio.sleep(0.5)
                    async with SessionFactory() as session:
                        notices = (
                            await session.exec(
                                select(NotificationEntity).where(
                                    NotificationEntity.event_id == identity
                                )
                            )
                        ).all()
                        assert len(notices) == 1
                finally:
                    if broker_paused:
                        checked_container_action(cache["id"], resources["owner_label"], "unpause")
                    if worker_paused:
                        checked_worker_signal(resources, signal.SIGCONT)
    finally:
        await _release_leader(first)
        await _release_leader(replacement)
        await engine.dispose()
