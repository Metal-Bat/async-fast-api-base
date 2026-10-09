"""Database scheduler/outbox recovery reaches the actual isolated Celery worker."""

import asyncio
import os
import socket
from uuid import uuid7

import pytest
from celery import Celery
from sqlmodel import col, select

from apps.calendar.application.service import CalendarService
from apps.calendar.domain.reminder import CalendarReminderEntity
from apps.notifications.domain.entity import NotificationEntity
from apps.tasks.application import outbox
from apps.tasks.domain.entity import TaskOutboxEntity
from apps.users.domain.entity import UserEntity
from core.celery_app import celery_app
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


@pytest.mark.anyio
async def test_scheduler_reload_broker_recovery_and_real_worker_deduplicate():
    owner = uuid7()
    try:
        async with SessionFactory() as session, session.begin():
            actor = UserEntity(
                username="worker-calendar-" + uuid7().hex, hashed_password=uuid7().hex
            )
            session.add(actor)
            await session.flush()
            event = await CalendarService(session).create(
                reminder_event("worker", reminder_offsets=[0]), actor
            )
            reminder = (
                await session.exec(
                    select(CalendarReminderEntity).where(
                        CalendarReminderEntity.source_id == open_ref_id(event.ref_id)[0]
                    )
                )
            ).one()
            identity = reminder.id
        assert await _claim_leader(owner)
        await _enqueue_due(owner, celery_app)
        await _release_leader(owner)
        # A new scheduler process loads the disabled one-off row, never another occurrence.
        replacement = uuid7()
        assert await _claim_leader(replacement)
        await _enqueue_due(replacement, celery_app)
        await _release_leader(replacement)
        async with SessionFactory() as session:
            messages = (
                await session.exec(
                    select(TaskOutboxEntity).where(
                        TaskOutboxEntity.task_name == "bpms.fire_calendar_reminder",
                        col(TaskOutboxEntity.kwargs)["reminder_id"].as_string() == str(identity),
                    )
                )
            ).all()
            assert len(messages) == 1
            message_id, task_id = messages[0].id, messages[0].task_id
        # Exercise a real refused broker connection, retaining the owned live broker for recovery.
        with socket.socket() as endpoint:
            endpoint.bind(("127.0.0.1", 0))
            port = endpoint.getsockname()[1]
            with Celery(
                "owned_unavailable_broker",
                broker=f"redis://127.0.0.1:{port}/1",
                set_as_current=False,
            ) as unavailable:
                unavailable.conf.broker_write_url = f"redis://127.0.0.1:{port}/1"
                assert unavailable.conf.broker_write_url == f"redis://127.0.0.1:{port}/1"
                unavailable.conf.broker_transport_options = {
                    "socket_connect_timeout": 1,
                    "socket_timeout": 1,
                }
                assert await outbox.dispatch_outbox(unavailable) == 0
        async with SessionFactory() as session, session.begin():
            message = await session.get(TaskOutboxEntity, message_id)
            assert (
                message is not None and message.published_at is None and message.task_id == task_id
            )
            assert message.attempts == 1 and message.last_error == "OperationalError"
            message.available_at = get_datetime_utc()
        assert await outbox.dispatch_outbox(celery_app) >= 1
        for _ in range(100):
            async with SessionFactory() as session:
                row = await session.get(CalendarReminderEntity, identity)
                assert row is not None
                if row.status == "SENT":
                    break
            await asyncio.sleep(0.2)
        assert row.status == "SENT"
        # Re-publish the exact retained broker message through the real worker.
        async with SessionFactory() as session:
            message = await session.get(TaskOutboxEntity, message_id)
            assert message is not None
            outbox._publish(celery_app, message)
        async with SessionFactory() as session:
            notices = (
                await session.exec(
                    select(NotificationEntity).where(NotificationEntity.event_id == identity)
                )
            ).all()
            assert len(notices) == 1 and notices[0].target_kind == "calendar"
    finally:
        await _release_leader(owner)
        await engine.dispose()


@pytest.mark.anyio
async def test_cancel_after_enqueue_is_safe_at_the_actual_worker():
    owner = uuid7()
    try:
        async with SessionFactory() as session, session.begin():
            actor = UserEntity(
                username="cancel-worker-calendar-" + uuid7().hex,
                hashed_password=uuid7().hex,
            )
            session.add(actor)
            await session.flush()
            actor_id = actor.id
            event = await CalendarService(session).create(
                reminder_event("worker-cancel", reminder_offsets=[0]), actor
            )
            reminder = (
                await session.exec(
                    select(CalendarReminderEntity).where(
                        CalendarReminderEntity.source_id == open_ref_id(event.ref_id)[0]
                    )
                )
            ).one()
            identity = reminder.id
        assert await _claim_leader(owner)
        await _enqueue_due(owner, celery_app)
        await _release_leader(owner)
        async with SessionFactory() as session, session.begin():
            actor = await session.get(UserEntity, actor_id)
            assert actor is not None
            await CalendarService(session).delete(event.ref_id, actor)
        await outbox.dispatch_outbox(celery_app)
        from apps.tasks.domain.entity import TaskExecutionEntity

        for _ in range(100):
            async with SessionFactory() as session:
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
                execution = (
                    await session.exec(
                        select(TaskExecutionEntity).where(
                            TaskExecutionEntity.task_id == messages[0].task_id
                        )
                    )
                ).first()
                if execution is not None and execution.status == "SUCCESS":
                    break
            await asyncio.sleep(0.2)
        assert execution is not None and execution.result == {"status": "cancelled"}
        async with SessionFactory() as session:
            assert not (
                await session.exec(
                    select(NotificationEntity).where(NotificationEntity.event_id == identity)
                )
            ).all()
    finally:
        await _release_leader(owner)
        await engine.dispose()
