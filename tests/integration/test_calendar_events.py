"""Real PostgreSQL overlap, live group policy, revisions and workflow projections."""

import os
from datetime import timedelta
from uuid import uuid7

import pytest
from scripts.bootstrap_application import open_manifest
from sqlmodel import col, select

from apps.calendar.application.service import CalendarService
from apps.calendar.domain.dto import CalendarInput, CalendarQuery
from apps.calendar.domain.entity import CalendarEventEntity
from apps.requests.application.demo import install_demo
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.work_items.domain.entity import WorkItemEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException
from utils.pagination import PageRequest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


def calendar_input(key: str, **changes) -> CalendarInput:
    return CalendarInput.model_validate(
        {
            "command_key": key,
            "title": "Private calendar",
            "schedule": {
                "kind": "all_day",
                "start_date": "2028-02-28",
                "end_date": "2028-03-02",
                "timezone": "Asia/Dubai",
            },
        }
        | changes
    )


@pytest.mark.anyio
async def test_calendar_overlap_exclusive_end_live_group_and_revision():
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            owner = UserEntity(username="calendar-owner-" + token, hashed_password=uuid7().hex)
            member = UserEntity(username="calendar-member-" + token, hashed_password=uuid7().hex)
            outsider = UserEntity(
                username="calendar-outsider-" + token,
                hashed_password=uuid7().hex,
                is_superuser=True,
            )
            session.add_all([owner, member, outsider])
            await session.flush()
            group = WorkGroupEntity(code="calendar-" + token, name="Calendar team")
            session.add(group)
            await session.flush()
            membership = WorkGroupMemberEntity(work_group_id=group.id, user_id=member.id)
            session.add_all(
                [membership, WorkGroupMemberEntity(work_group_id=group.id, user_id=owner.id)]
            )
            await session.flush()
            service = CalendarService(session)
            personal = await service.create(calendar_input("personal"), owner)
            assert (
                await service.create(calendar_input("personal"), owner)
            ).ref_id == personal.ref_id
            team = await service.create(
                calendar_input("team", work_group_ref_id=create_ref_id(group.id, group.version)),
                owner,
            )
            # End exactly at the search start does not overlap; a DST/UTC+04 timed event does.
            await service.create(
                calendar_input(
                    "boundary",
                    schedule={
                        "kind": "all_day",
                        "start_date": "2028-02-28",
                        "end_date": "2028-02-29",
                        "timezone": "UTC",
                    },
                ),
                owner,
            )
            await service.create(
                calendar_input(
                    "timed",
                    schedule={
                        "kind": "timed",
                        "start_at": "2028-02-29T00:30:00+04:00",
                        "end_at": "2028-02-29T01:30:00+04:00",
                        "timezone": "Asia/Dubai",
                    },
                ),
                owner,
            )
            query = CalendarQuery.model_validate(
                {
                    "start_date": "2028-02-29",
                    "end_date": "2028-03-01",
                    "timezone": "Asia/Dubai",
                    "size": 1,
                }
            )
            result = await service.search(query, owner)
            assert result.total == 3 and len(result.items) == 1
            assert (await service.search(query, member)).total == 1
            assert (await service.search(query, outsider)).total == 0
            with pytest.raises(NotFoundException):
                await service.update(team.ref_id, calendar_input("not-owner"), member)
            updated = await service.update(
                personal.ref_id, calendar_input("edit", title="Edited calendar"), owner
            )
            assert updated.ref_id != personal.ref_id
            assert (
                await service.update(
                    personal.ref_id, calendar_input("edit", title="Edited calendar"), owner
                )
            ).ref_id == updated.ref_id
            with pytest.raises(VersionConflictException):
                await service.update(personal.ref_id, calendar_input("stale"), owner)
            assert (await service.history(updated.ref_id, owner, PageRequest())).total == 2
            membership.is_active = False
            await session.flush()
            assert (await service.search(query, member)).total == 0
            with pytest.raises(NotFoundException):
                await service.get(team.ref_id, member)
            await service.delete(updated.ref_id, owner)
            await service.delete(updated.ref_id, owner)
            assert (await service.search(query, owner)).total == 2
            retained = await session.get(CalendarEventEntity, open_ref_id(updated.ref_id)[0])
            assert retained is not None and retained.deleted_at is not None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_work_deadline_is_actual_read_only_point_and_disappears(tmp_path):
    with open_manifest(
        tmp_path / "calendar-seed.json", database=os.environ["POSTGRES_DB"], create=True
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
                item = (
                    await session.exec(
                        select(WorkItemEntity)
                        .where(WorkItemEntity.status == "OPEN")
                        .order_by(col(WorkItemEntity.id))
                    )
                ).first()
                assert item is not None
                # Controlled fixture supplies an actual domain deadline, never inferred by the API.
                item.due_at = get_datetime_utc() + timedelta(hours=1)
                await session.flush()
                today = get_datetime_utc().date()
                query = CalendarQuery(start_date=today, end_date=today + timedelta(days=2))
                result = await CalendarService(session).search(query, actor)
                deadlines = [row for row in result.items if row.source_kind == "work_item"]
                assert len(deadlines) == 1 and deadlines[0].editable is False
                assert (
                    deadlines[0].route_key == "work_items"
                    and deadlines[0].schedule.kind == "deadline"
                )
                assert deadlines[0].schedule.due_at == item.due_at
                with pytest.raises(NotFoundException):
                    await CalendarService(session).update(
                        deadlines[0].ref_id, calendar_input("wrong-owner"), actor
                    )
                item.due_at = None
                await session.flush()
                assert not [
                    row
                    for row in (await CalendarService(session).search(query, actor)).items
                    if row.source_kind == "work_item"
                ]
        finally:
            await engine.dispose()
