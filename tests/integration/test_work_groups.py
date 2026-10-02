"""PostgreSQL work-group persistence and concurrency checks."""

import os
from uuid import uuid7

import pytest
from anyio import create_task_group
from sqlmodel import func, select

from apps.users.domain.entity import UserEntity
from apps.work_groups.application.service import WorkGroupService
from apps.work_groups.domain.dto import WorkGroupCreateDTO
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from core.deps import SessionFactory, engine
from core.history import history_tables
from core.ref_id import create_ref_id

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_group_membership_lifecycle_and_history() -> None:
    actor = UserEntity(username=f"wg-actor-{uuid7()}", hashed_password="hash")
    member = UserEntity(username=f"wg-member-{uuid7()}", hashed_password="hash")
    async with SessionFactory() as session:
        session.add_all([actor, member])
        await session.flush()
        service = WorkGroupService(session)
        group = await service.create_group(
            WorkGroupCreateDTO(code=f"G{uuid7().hex}", name="Operations"), actor.id
        )
        ref = create_ref_id(group.id, group.version)
        await service.add_member(ref, member.id, actor_id=actor.id)
        await service.add_member(ref, member.id, actor_id=actor.id)
        assert await service.is_active_member(member.id, group.id)
        await service.deactivate_member(ref, member.id, actor_id=actor.id)
        assert not await service.is_active_member(member.id, group.id)
        await service.add_member(ref, member.id, actor_id=actor.id)
        assert await service.is_active_member(member.id, group.id)
        await session.commit()

    history = history_tables()["work_group"]
    async with SessionFactory() as session:
        history_count = (
            await session.exec(
                select(func.count()).select_from(history).where(history.c.ENTITY_ID == group.id)
            )
        ).one()
        assert history_count == 1
        await WorkGroupService(session).remove_member(ref, member.id, actor_id=actor.id)
        await session.commit()
        assert await session.get(WorkGroupMemberEntity, (group.id, member.id)) is None
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_duplicate_member_add_creates_one_row() -> None:
    async with SessionFactory() as session:
        user = UserEntity(username=f"wg-concurrent-{uuid7()}", hashed_password="hash")
        group = WorkGroupEntity(code=f"G{uuid7().hex}", name="Concurrent")
        session.add_all([user, group])
        await session.commit()
        group_ref = create_ref_id(group.id, group.version)
        user_id = user.id
        group_id = group.id

    async def add() -> None:
        async with SessionFactory() as session:
            await WorkGroupService(session).add_member(group_ref, user_id)
            await session.commit()

    async with create_task_group() as tasks:
        tasks.start_soon(add)
        tasks.start_soon(add)

    async with SessionFactory() as session:
        rows = (
            await session.exec(
                select(WorkGroupMemberEntity).where(
                    WorkGroupMemberEntity.work_group_id == group_id,
                    WorkGroupMemberEntity.user_id == user_id,
                )
            )
        ).all()
        assert len(rows) == 1
