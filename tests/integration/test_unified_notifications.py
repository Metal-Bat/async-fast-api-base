"""Real persisted inbox, atomic intent, compatibility and revocation evidence."""

import os
from uuid import uuid7

import pytest
from sqlmodel import col, select

from apps.notifications.application.events import stage_notice
from apps.notifications.application.inbox import InboxService
from apps.notifications.application.service import NotificationService
from apps.notifications.domain.dto import NotificationQuery
from apps.notifications.domain.entity import NotificationEntity
from apps.notifications.domain.inbox import InboxQuery
from apps.users.application.auth_service import AuthService
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotAllowedException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_security_notice_atomic_replay_locale_read_and_legacy_exclusion():
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            owner = UserEntity(username="inbox-" + token, hashed_password=token)
            outsider = UserEntity(username="inbox-other-" + token, hashed_password=token)
            session.add_all([owner, outsider])
            await session.flush()
            event = uuid7()
            row = await stage_notice(
                session,
                map_id="MAP-14",
                event_id=event,
                recipient_id=owner.id,
                target_kind="account",
                target_id=owner.id,
            )
            assert (
                row is not None
                and row.business_request_id is None
                and row.process_instance_id is None
            )
            replay = await stage_notice(
                session,
                map_id="MAP-14",
                event_id=event,
                recipient_id=owner.id,
                target_kind="account",
                target_id=owner.id,
            )
            assert replay is not None and replay.id == row.id
            inbox = InboxService(session)
            reference = create_ref_id(row.id, row.version)
            assert (await inbox.inbox_search(InboxQuery(), owner)).total == 1
            assert (
                await NotificationService(session).search(NotificationQuery(), owner)
            ).total == 0
            assert await inbox.unread_count(owner) == 1
            with pytest.raises(NotAllowedException):
                await inbox.get(reference, outsider)
            read = await inbox.mark_read(reference, owner)
            assert await inbox.unread_count(owner) == 0
            with pytest.raises(VersionConflictException):
                await inbox.mark_read(reference, owner)
            assert (await inbox.dto(read, owner)).target.kind == "account"
            await AuthService(session).audit("password.changed", user_id=owner.id)
            assert (await inbox.inbox_search(InboxQuery(), owner)).total == 2
            count_before = len((await session.exec(select(NotificationEntity))).all())
            nested = await session.begin_nested()
            await AuthService(session).audit("password.reset", user_id=owner.id)
            await nested.rollback()
            assert len((await session.exec(select(NotificationEntity))).all()) == count_before
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_claim_release_and_forward_notices_follow_committed_assignments():
    from apps.notifications.application.events import PROCESS_MAP, fanout_event
    from apps.processes.domain.entity import ProcessEventEntity
    from apps.requests.application.service import RequestService
    from apps.requests.domain.dto import BusinessRequestCreateDTO, BusinessRequestSubmitDTO
    from apps.work_items.application.service import WorkItemService
    from apps.work_items.domain.dto import WorkItemForwardDTO
    from apps.work_items.domain.entity import WorkItemEntity
    from core.ref_id import open_ref_id
    from tests.integration.test_frontend_journey import _prepare_journey

    try:
        names, _, kind = await _prepare_journey()
        async with SessionFactory() as session, session.begin():
            actors = [
                (await session.exec(select(UserEntity).where(UserEntity.username == name))).one()
                for name in names[:3]
            ]
            requester, reviewer, reassigned = actors
            reviewer_id, reassigned_id = reviewer.id, reassigned.id
            requests = RequestService(session)
            request, _ = await requests.create_draft(
                BusinessRequestCreateDTO(request_type_ref_id=kind, data={"amount": "42"}), requester
            )
            request, _ = await requests.submit(
                create_ref_id(request.id, request.version),
                BusinessRequestSubmitDTO(submit_key="assignment-notices"),
                requester,
            )
            request_id = request.id
            item = (
                await session.exec(
                    select(WorkItemEntity).where(WorkItemEntity.business_request_id == request.id)
                )
            ).one()
            work = WorkItemService(session)
            item = await work.claim(create_ref_id(item.id, item.version), "notice-claim", reviewer)
            item = await work.claimant_action(
                create_ref_id(item.id, item.version), "release", "notice-release", reviewer
            )
            item_id = item.id
        async with SessionFactory() as session:
            changes = (
                await session.exec(
                    select(ProcessEventEntity).where(
                        ProcessEventEntity.work_item_id == item_id,
                        col(ProcessEventEntity.event_type).in_(
                            ["work_item.claimed", "work_item.released"]
                        ),
                    )
                )
            ).all()
        assert len(changes) == 2
        for event in changes:
            assert await fanout_event(event.id) == 1
            assert await fanout_event(event.id) == 1
        async with SessionFactory() as session, session.begin():
            reviewer = await session.get(UserEntity, reviewer_id)
            reassigned = await session.get(UserEntity, reassigned_id)
            item = await session.get(WorkItemEntity, item_id)
            assert reviewer is not None and reassigned is not None and item is not None
            work = WorkItemService(session)
            item = await work.claim(
                create_ref_id(item.id, item.version), "notice-reclaim", reviewer
            )
            reference = create_ref_id(item.id, item.version)
            command = WorkItemForwardDTO(
                command_key="notice-forward",
                user_ref_ids=[create_ref_id(reassigned.id, reassigned.version)],
                reason="Specialist review",
            )
            forwarded = await work.forward(reference, command, reviewer)
            assert (await work.forward(reference, command, reviewer)).id == forwarded.id
            forwarded_id = forwarded.id
        async with SessionFactory() as session:
            events = (
                await session.exec(
                    select(ProcessEventEntity).where(
                        ProcessEventEntity.business_request_id == request_id
                    )
                )
            ).all()
        for event in events:
            if event.event_type in PROCESS_MAP:
                await fanout_event(event.id)
                await fanout_event(event.id)
        async with SessionFactory() as session:
            reassigned = await session.get(UserEntity, reassigned_id)
            assert reassigned is not None
            inbox = await InboxService(session).inbox_search(InboxQuery(), reassigned)
            assert inbox.total == 1
            notice = inbox.items[0]
            assert notice.template_key == "application.map_02"
            assert notice.target.available and notice.target.ref_id is not None
            assert open_ref_id(notice.target.ref_id)[0] == forwarded_id
            rows = (
                await session.exec(
                    select(NotificationEntity).where(
                        col(NotificationEntity.event_id).in_([event.id for event in changes])
                    )
                )
            ).all()
            assert len(rows) == 2
            assert all(row.recipient_user_id == reviewer_id for row in rows)
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_committed_process_fanout_dedupe_current_links_and_revocation():
    from sqlalchemy import delete

    from apps.notifications.application.events import PROCESS_MAP, fanout_event
    from apps.processes.domain.entity import ProcessEventEntity
    from apps.requests.application.service import RequestService
    from apps.requests.domain.dto import BusinessRequestCreateDTO, BusinessRequestSubmitDTO
    from apps.users.domain.auth_entity import UserRoleEntity
    from core.ref_id import open_ref_id
    from tests.integration.test_frontend_journey import _prepare_journey

    try:
        names, _, kind = await _prepare_journey()
        async with SessionFactory() as session, session.begin():
            requester = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[0]))
            ).one()
            reviewer = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[1]))
            ).one()
            requester_id, reviewer_id = requester.id, reviewer.id
            service = RequestService(session)
            request, _ = await service.create_draft(
                BusinessRequestCreateDTO(request_type_ref_id=kind, data={"amount": "42"}), requester
            )
            reference = create_ref_id(request.id, request.version)
            request, _ = await service.submit(
                reference, BusinessRequestSubmitDTO(submit_key="notices-once"), requester
            )
            request_id = request.id
        async with SessionFactory() as session:
            events = list(
                (
                    await session.exec(
                        select(ProcessEventEntity).where(
                            ProcessEventEntity.business_request_id == request_id
                        )
                    )
                ).all()
            )
        for event in events:
            if event.event_type in PROCESS_MAP:
                await fanout_event(event.id)
                await fanout_event(event.id)
        async with SessionFactory() as session, session.begin():
            reviewer = await session.get(UserEntity, reviewer_id)
            requester = await session.get(UserEntity, requester_id)
            assert reviewer is not None and requester is not None
            inbox = InboxService(session)
            request_rows = await inbox.inbox_search(InboxQuery(), requester)
            work_rows = await inbox.inbox_search(InboxQuery(), reviewer)
            assert sum(row.template_key == "application.map_01" for row in request_rows.items) == 1
            assert sum(row.template_key == "application.map_02" for row in work_rows.items) == 1
            target = next(
                row for row in work_rows.items if row.template_key == "application.map_02"
            )
            assert target.target.available and target.target.ref_id is not None
            old_identity = open_ref_id(target.target.ref_id)[0]
            await session.exec(
                delete(UserRoleEntity).where(col(UserRoleEntity.user_id) == reviewer.id)
            )
            redacted = await inbox.dto(await inbox.get(target.ref_id, reviewer), reviewer)
            assert (
                not redacted.target.available
                and redacted.target.ref_id is None
                and redacted.content is None
            )
            assert old_identity is not None
    finally:
        await engine.dispose()
