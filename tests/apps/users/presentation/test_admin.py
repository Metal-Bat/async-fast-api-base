"""Tests for administrative user presentation behavior."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import httpx
import pytest
from fastapi import Request

from apps.users.application.auth_service import AuthService
from apps.users.domain.auth_dto import AdminResetPasswordDTO
from apps.users.domain.entity import UserEntity
from apps.users.presentation import admin as routes
from apps.users.presentation.admin import reset_user_password
from core.deps import get_current_user, get_db
from core.ref_id import create_ref_id
from main import app
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, VersionConflictException


def request_context() -> Request:
    return Request({"type": "http", "headers": []})


@pytest.mark.anyio
async def test_user_search_and_reset_require_authentication() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for path, body in [
            ("/api/v1/admin/users/search", {}),
            ("/api/v1/admin/users/reference/reset-password", {"new_password": "replacement"}),
        ]:
            response = await client.post(path, json=body)
            assert response.status_code == 401


@pytest.mark.anyio
async def test_regular_user_cannot_search_or_reset() -> None:
    user = UserEntity(id=uuid7(), username="regular", hashed_password="hash")
    session = Mock()
    result = Mock()
    result.all.return_value = []
    session.exec = AsyncMock(return_value=result)

    async def current():
        return user

    async def database():
        yield session

    app.dependency_overrides[get_current_user] = current
    app.dependency_overrides[get_db] = database
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path, body in [
                ("/api/v1/admin/users/search", {}),
                ("/api/v1/admin/users/reference/reset-password", {"new_password": "replacement"}),
            ]:
                assert (await client.post(path, json=body)).status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_admin_reset_revokes_credentials_and_audits_actor(monkeypatch) -> None:
    target = UserEntity(id=uuid7(), username="target", hashed_password="old")
    actor = UserEntity(id=uuid7(), username="admin", hashed_password="hash", is_superuser=True)
    session = Mock()
    session.get = AsyncMock(return_value=target)
    session.exec = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    notice = AsyncMock()
    monkeypatch.setattr("apps.notifications.application.events.stage_notice", notice)
    monkeypatch.setattr(
        "apps.users.application.auth_service.hash_password", AsyncMock(return_value="new-hash")
    )
    response = await reset_user_password(
        Request({"type": "http", "headers": []}),
        create_ref_id(target.id, target.version),
        AdminResetPasswordDTO(new_password="replacement"),
        actor,
        session,
    )
    assert response.code == 204
    assert target.hashed_password == "new-hash"
    statements = [call.args[0] for call in session.exec.await_args_list]
    assert len(statements) == 2
    for statement in statements:
        assert target.id in statement.compile().params.values()
    assert "REVOKED_AT" in str(statements[0])
    assert "USED_AT" in str(statements[1])
    audit = session.add.call_args.args[0]
    assert audit.user_id == actor.id
    assert audit.details == {"target_user_id": str(target.id)}
    session.commit.assert_awaited_once()

    assert notice.await_args is not None
    assert notice.await_args.kwargs["recipient_id"] == target.id
    assert notice.await_args.kwargs["target_id"] == target.id


@pytest.mark.anyio
async def test_reset_rejects_privileged_targets_and_stale_references() -> None:
    target = UserEntity(id=uuid7(), username="admin", hashed_password="old", is_superuser=True)
    actor = UserEntity(id=uuid7(), username="manager", hashed_password="hash")
    session = Mock()
    session.get = AsyncMock(return_value=target)
    session.commit = AsyncMock()
    with pytest.raises(NotAllowedException):
        await AuthService(session).stage_admin_password_reset(target, "replacement", actor=actor)
    actor.is_superuser = True
    with pytest.raises(VersionConflictException):
        await reset_user_password(
            Request({"type": "http", "headers": []}),
            create_ref_id(target.id, target.version + 1),
            AdminResetPasswordDTO(new_password="replacement"),
            actor,
            session,
        )
    session.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_user_manager_cannot_grant_superuser_status() -> None:
    from apps.users.domain.dto import UserCreateDTO, UserUpdateDTO
    from apps.users.presentation.admin import create_user, update_user

    actor = UserEntity(id=uuid7(), username="manager", hashed_password="hash")
    session = Mock()
    session.get = AsyncMock(return_value=actor)
    request = Request({"type": "http", "headers": []})
    with pytest.raises(NotAllowedException):
        await create_user(
            request,
            UserCreateDTO(username="elevated", password="replacement", is_superuser=True),
            actor,
            session,
        )
    ref_id = create_ref_id(actor.id, actor.version)
    with pytest.raises(NotAllowedException):
        await update_user(
            request, ref_id, UserUpdateDTO(ref_id=ref_id, is_superuser=True), actor, session
        )
    session.add.assert_not_called()


@pytest.mark.anyio
async def test_recovery_instructions_do_not_issue_tokens() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/forgot-password", json={"username_or_email": "admin"}
        )
    assert response.status_code == 202
    assert response.json()["data"] == {"detail": "Contact an administrator to reset your password."}


@pytest.mark.anyio
async def test_admin_can_restore_soft_deleted_user() -> None:
    """Administrative restore clears deletion state with optimistic locking."""
    user = UserEntity(
        id=uuid7(),
        username="restore-user",
        hashed_password="hash",
        deleted_at=get_datetime_utc(),
    )
    session = Mock()
    session.get = AsyncMock(return_value=user)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = Mock()
    actor = UserEntity(
        id=uuid7(), username="restore-admin", hashed_password="hash", is_superuser=True
    )
    restored = await routes.restore_user(
        request_context(), create_ref_id(user.id, user.version), actor, session
    )
    assert restored.data.deleted_at is None
    session.commit.assert_awaited_once()
