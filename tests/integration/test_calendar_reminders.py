"""Committed schedules cancel with edits and notifications recheck current sources."""

import os
from datetime import timedelta
from uuid import uuid7

import pytest
from sqlmodel import select

from apps.calendar.application.reminders import fire_reminder
from apps.calendar.application.service import CalendarService
from apps.calendar.domain.dto import CalendarInput
from apps.calendar.domain.reminder import CalendarReminderEntity
from apps.notifications.application.inbox import InboxService
from apps.notifications.domain.entity import NotificationEntity
from apps.tasks.domain.entity import PeriodicTaskEntity
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import open_ref_id
from utils.date_utils import get_datetime_utc

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


def reminder_event(key: str, *, start=None, **changes) -> CalendarInput:
    now = start or get_datetime_utc() - timedelta(minutes=1)
    return CalendarInput.model_validate(
        {
            "command_key": key,
            "title": "Reminder test",
            "schedule": {
                "kind": "timed",
                "start_at": now,
                "end_at": get_datetime_utc() + timedelta(hours=1),
                "timezone": "UTC",
            },
            "reminder_offsets": [0, 60],
        }
        | changes
    )


@pytest.mark.anyio
async def test_event_edit_cancel_replay_and_source_transaction_rollback():
    try:
        async with SessionFactory() as session, session.begin():
            actor = UserEntity(username="reminder-" + uuid7().hex, hashed_password="hash")
            session.add(actor)
            await session.flush()
            actor_id = actor.id
            event = await CalendarService(session).create(reminder_event("initial"), actor)
            source_id = open_ref_id(event.ref_id)[0]
            reminders = (
                await session.exec(
                    select(CalendarReminderEntity).where(
                        CalendarReminderEntity.source_id == source_id
                    )
                )
            ).all()
            first_id, second_id = (row.id for row in reminders)
        assert await fire_reminder(first_id) == "sent"
        assert await fire_reminder(first_id) == "sent"
        async with SessionFactory() as session, session.begin():
            actor = await session.get(UserEntity, actor_id)
            assert actor is not None
            notices = (
                await session.exec(
                    select(NotificationEntity).where(NotificationEntity.event_id == first_id)
                )
            ).all()
            assert (
                len(notices) == 1
                and (await InboxService(session).target(notices[0], actor)).available
            )
            updated = await CalendarService(session).update(
                event.ref_id,
                reminder_event("changed", start=get_datetime_utc() + timedelta(minutes=5)),
                actor,
            )
            assert not (await InboxService(session).target(notices[0], actor)).available
            rows = (
                await session.exec(
                    select(CalendarReminderEntity).where(
                        CalendarReminderEntity.source_id == source_id
                    )
                )
            ).all()
            assert sum(row.status == "PENDING" for row in rows) == 2
            assert sum(row.status == "CANCELLED" for row in rows) == 2
            old_schedule = await session.get(PeriodicTaskEntity, reminders[1].schedule_id)
            assert old_schedule is not None and old_schedule.enabled is False
        assert await fire_reminder(second_id) == "cancelled"
        with pytest.raises(RuntimeError):
            async with SessionFactory() as session, session.begin():
                actor = await session.get(UserEntity, actor_id)
                assert actor is not None
                await CalendarService(session).delete(updated.ref_id, actor)
                raise RuntimeError("source rollback")
        async with SessionFactory() as session, session.begin():
            actor = await session.get(UserEntity, actor_id)
            assert actor is not None
            assert await CalendarService(session).get(updated.ref_id, actor)
            await CalendarService(session).delete(updated.ref_id, actor)
        async with SessionFactory() as session:
            assert not [
                row
                for row in (
                    await session.exec(
                        select(CalendarReminderEntity).where(
                            CalendarReminderEntity.source_id == source_id
                        )
                    )
                ).all()
                if row.status == "PENDING"
            ]
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_late_relevant_reminder_expires_without_notice():
    try:
        async with SessionFactory() as session, session.begin():
            actor = UserEntity(username="late-reminder-" + uuid7().hex, hashed_password="hash")
            session.add(actor)
            await session.flush()
            event = await CalendarService(session).create(
                reminder_event(
                    "late", start=get_datetime_utc() - timedelta(days=2), reminder_offsets=[0]
                ),
                actor,
            )
            row = (
                await session.exec(
                    select(CalendarReminderEntity).where(
                        CalendarReminderEntity.source_id == open_ref_id(event.ref_id)[0]
                    )
                )
            ).one()
            identity = row.id
        assert await fire_reminder(identity) == "expired"
        async with SessionFactory() as session:
            assert not (
                await session.exec(
                    select(NotificationEntity).where(NotificationEntity.event_id == identity)
                )
            ).all()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_actual_work_due_change_and_completion_cancel_old_reminders(tmp_path):
    from scripts.bootstrap_application import open_manifest

    from apps.calendar.application.reminders import configure_work_reminders
    from apps.calendar.domain.dto import ReminderInput
    from apps.requests.application.demo import install_demo
    from apps.users.application.bootstrap import install_accounts
    from apps.users.application.permission_catalog import reconcile_permissions
    from apps.work_items.application.service import WorkItemService
    from apps.work_items.domain.dto import CartableQueryDTO
    from apps.work_items.domain.entity import WorkItemEntity
    from core.ref_id import create_ref_id

    with open_manifest(
        tmp_path / "work-reminder-seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("requester", "reviewer", "designer"))
                await install_accounts(session, manifest)
                await install_demo(session, manifest)
                actor = (
                    await session.exec(
                        select(UserEntity).where(
                            UserEntity.username
                            == next(
                                account.username
                                for account in manifest.accounts
                                if account.persona == "reviewer"
                            )
                        )
                    )
                ).one()
                service = WorkItemService(session)
                available = await service.search(CartableQueryDTO(cartable="available"), actor)
                assert available.items
                item = await service.get(
                    create_ref_id(available.items[0].id, available.items[0].version),
                    actor,
                    update_row=True,
                )
                item.due_at = get_datetime_utc() + timedelta(hours=1)
                await session.flush()
                item_id, actor_id = item.id, actor.id
                configured = await configure_work_reminders(
                    session,
                    create_ref_id(item.id, item.version),
                    ReminderInput(command_key="work-first", offsets=[3600]),
                    actor,
                )
                old_id = open_ref_id(configured[0].ref_id)[0]
                # The due value is domain-owned; a fixture mutation proves stale deliveries recheck it.
                item.due_at += timedelta(hours=2)
                await session.flush()
            assert await fire_reminder(old_id) == "cancelled"
            async with SessionFactory() as session, session.begin():
                actor = await session.get(UserEntity, actor_id)
                item = await session.get(WorkItemEntity, item_id)
                assert actor is not None and item is not None
                configured = await configure_work_reminders(
                    session,
                    create_ref_id(item.id, item.version),
                    ReminderInput(command_key="work-second", offsets=[10800]),
                    actor,
                )
                new_id = open_ref_id(configured[0].ref_id)[0]
            assert await fire_reminder(new_id) == "sent"
            async with SessionFactory() as session, session.begin():
                actor = await session.get(UserEntity, actor_id)
                item = await session.get(WorkItemEntity, item_id)
                assert actor is not None and item is not None
                service = WorkItemService(session)
                item = await service.claim(
                    create_ref_id(item.id, item.version), "work-reminder-claim", actor
                )
                completed = await service.finish(
                    create_ref_id(item.id, item.version),
                    "complete",
                    "work-reminder-complete",
                    "approve",
                    {},
                    actor,
                )
                assert completed.status == "COMPLETED"
                row = await session.get(CalendarReminderEntity, new_id)
                assert row is not None and row.status == "CANCELLED"
                notice = (
                    await session.exec(
                        select(NotificationEntity).where(NotificationEntity.event_id == new_id)
                    )
                ).one()
                assert not (await InboxService(session).target(notice, actor)).available
            assert await fire_reminder(new_id) == "cancelled"
        finally:
            await engine.dispose()
