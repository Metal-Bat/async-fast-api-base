"""Real PostgreSQL seed convergence, revocation preservation and ordinary-role isolation."""

import os
from uuid import uuid7

import anyio
import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import col, select

from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeVersionEntity
from apps.users.application.permission_catalog import PERMISSIONS, reconcile_permissions
from apps.users.domain.auth_entity import (
    PermissionEntity,
    RoleEntity,
    RolePermissionEntity,
    UserRoleEntity,
)
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from main import app
from utils.date_utils import get_datetime_utc
from utils.security import hash_password

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_seed_check_repeat_and_operator_edits_are_preserved():
    try:
        async with SessionFactory() as session:
            before = await reconcile_permissions(session, check_only=True)
            assert before.created_permissions == []
            first = await reconcile_permissions(session, roles=("requester", "operator"))
            assert first.created_permissions or not before.missing_permissions
            role = (
                await session.exec(select(RoleEntity).where(RoleEntity.name == "app.requester.v1"))
            ).one()
            role.description = "Operator-owned description"
            await session.flush()
            repeated = await reconcile_permissions(session, roles=("requester", "operator"))
            assert not repeated.created_permissions and not repeated.created_roles
            assert role.description == "Operator-owned description"
            target = (
                await session.exec(
                    select(PermissionEntity).where(PermissionEntity.name == "requests.start")
                )
            ).one()
            target.deleted_at = get_datetime_utc()
            await session.flush()
            revoked = await reconcile_permissions(session, roles=("reviewer",))
            assert revoked.deleted_permissions == ["requests.start"]
            assert revoked.blocked_roles == ["app.reviewer.v1"]
            assert target.deleted_at is not None
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_seed_converges_and_does_not_rewrite_published_catalogs():
    summaries = []
    try:
        async with SessionFactory() as session:
            before = list((await session.exec(select(StepTypeVersionEntity))).all())
            published = {row.id: row.model_dump() for row in before if row.status == "PUBLISHED"}

        async def seed():
            async with SessionFactory() as session, session.begin():
                summaries.append(await reconcile_permissions(session))
                await StepTypeService(session, get_registry()).reconcile()

        async with anyio.create_task_group() as group:
            group.start_soon(seed)
            group.start_soon(seed)
        async with SessionFactory() as session:
            names = list(
                (
                    await session.exec(
                        select(PermissionEntity.name).where(
                            col(PermissionEntity.name).in_(PERMISSIONS)
                        )
                    )
                ).all()
            )
            assert set(names) == set(PERMISSIONS) and len(names) == len(PERMISSIONS)
            for identifier, original in published.items():
                row = await session.get(StepTypeVersionEntity, identifier)
                assert row is not None and row.model_dump() == original
        assert len(summaries) == 2
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_seeded_requester_can_read_self_but_cannot_manage_users_or_restore():
    username, password = f"seed-role-{uuid7()}", f"Synthetic-{uuid7()}"
    try:
        async with SessionFactory() as session, session.begin():
            await reconcile_permissions(session, roles=("requester",))
            role = (
                await session.exec(select(RoleEntity).where(RoleEntity.name == "app.requester.v1"))
            ).one()
            user = UserEntity(username=username, hashed_password=await hash_password(password))
            session.add(user)
            await session.flush()
            session.add(UserRoleEntity(user_id=user.id, role_id=role.id))
            assignments = (
                await session.exec(
                    select(RolePermissionEntity).where(RolePermissionEntity.role_id == role.id)
                )
            ).all()
            assert len(assignments) == 1 and not user.is_superuser
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            assert login.status_code == 200
            headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
            assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
            assert (
                await client.post("/api/v1/admin/users/search", json={}, headers=headers)
            ).status_code == 403
            assert (
                await client.post(
                    "/api/v1/admin/work-groups/select",
                    json={"include_deleted": True},
                    headers=headers,
                )
            ).status_code == 403
            assert (
                await client.post(
                    f"/api/v1/admin/users/{create_ref_id(user.id, user.version)}/restore",
                    headers=headers,
                )
            ).status_code == 403
    finally:
        await engine.dispose()
