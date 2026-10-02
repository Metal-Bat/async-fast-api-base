"""Tests for the user authentication application service."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import jwt
import pytest

from apps.users.application.auth_service import AuthService, hash_secret
from apps.users.domain.auth_dto import LoginDTO
from apps.users.domain.auth_entity import AuthSessionEntity, PasswordResetTokenEntity
from apps.users.domain.entity import UserEntity
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import InvalidCredentialError, InvalidTokenException
from utils.security import hash_password, verify_password


def result(value: object) -> Mock:
    """Build a SQLAlchemy-result-shaped test double."""
    response = Mock()
    response.one_or_none.return_value = value
    return response


def session_with(*results: object) -> Mock:
    """Build an async-session-shaped test double with ordered query results."""
    session = Mock()
    session.exec = AsyncMock(side_effect=[result(value) for value in results])
    session.get = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.add = Mock()
    session.add_all = Mock()
    return session


def test_access_token_is_short_lived_and_typed() -> None:
    """Access JWTs include their session, type, unique ID, and expiry."""
    user = UserEntity(username="token-user", hashed_password="hash")
    auth_session = AuthSessionEntity(
        user_id=user.id,
        family_id=user.id,
        refresh_token_hash=hash_secret("refresh"),
        expires_at=get_datetime_utc(),
    )
    token = AuthService(Mock())._access_token(user, auth_session.id)
    assert isinstance(token, str)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["type"] == "access"
    assert payload["sub"] == str(user.id)
    assert payload["sid"] == str(auth_session.id)
    assert payload["exp"] - payload["iat"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@pytest.mark.anyio
async def test_login_success_and_failure_are_audited() -> None:
    """Successful credentials create a token pair; bad credentials are rejected."""
    user = UserEntity(username="login", hashed_password=await hash_password("password"))
    success_session = session_with(None, user)
    pair = await AuthService(success_session).login(
        LoginDTO(username="login", password="password"),
        request_id="request",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert pair.access_token and pair.refresh_token
    success_session.commit.assert_awaited_once()

    failure_session = session_with(None, user)
    with pytest.raises(InvalidCredentialError):
        await AuthService(failure_session).login(
            LoginDTO(username="login", password="wrong"),
            request_id=None,
            ip_address=None,
            user_agent=None,
        )
    failure_session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_refresh_rotation_logout_and_reuse_detection() -> None:
    """Refresh tokens rotate once and revoked-token reuse is rejected."""
    user = UserEntity(username="rotate", hashed_password="hash")
    active = AuthSessionEntity(
        user_id=user.id,
        family_id=user.id,
        refresh_token_hash=hash_secret("refresh"),
        expires_at=get_datetime_utc() + timedelta(days=1),
    )
    session = session_with(active)
    session.get.return_value = user
    rotated = await AuthService(session).refresh("refresh")
    assert rotated.refresh_token != "refresh"
    assert active.revoked_at is not None

    revoked = AuthSessionEntity(
        user_id=user.id,
        family_id=user.id,
        refresh_token_hash=hash_secret("reused"),
        expires_at=get_datetime_utc() + timedelta(days=1),
        revoked_at=get_datetime_utc(),
    )
    reused_session = session_with(revoked, None)
    with pytest.raises(InvalidTokenException, match="reuse"):
        await AuthService(reused_session).refresh("reused")

    logout_session = session_with(active)
    active.revoked_at = None
    await AuthService(logout_session).logout("refresh")
    assert active.revoked_at is not None


@pytest.mark.anyio
async def test_password_reset_and_change_revoke_sessions() -> None:
    """Reset and authenticated password changes replace hashes and revoke sessions."""
    user = UserEntity(username="password", hashed_password=await hash_password("old-password"))
    request_session = session_with(user)
    raw = await AuthService(request_session).request_password_reset("password")
    assert raw is not None

    reset = PasswordResetTokenEntity(
        user_id=user.id,
        token_hash=hash_secret(raw),
        expires_at=get_datetime_utc() + timedelta(minutes=5),
    )
    reset_session = session_with(reset, None)
    reset_session.get.return_value = user
    await AuthService(reset_session).reset_password(raw, "new-password")
    assert await verify_password("new-password", user.hashed_password)
    assert reset.used_at is not None

    change_session = session_with(None)
    await AuthService(change_session).change_password(user, "new-password", "newest-password")
    assert await verify_password("newest-password", user.hashed_password)


@pytest.mark.anyio
async def test_invalid_reset_and_unknown_account_are_safe() -> None:
    """Unknown accounts are silent and invalid reset tokens fail safely."""
    unknown = session_with(None)
    assert await AuthService(unknown).request_password_reset("missing") is None
    invalid = session_with(None)
    with pytest.raises(InvalidTokenException):
        await AuthService(invalid).reset_password("bad", "new-password")


@pytest.mark.anyio
async def test_deleted_accounts_cannot_request_or_consume_password_resets() -> None:
    deleted = UserEntity(
        username="deleted",
        hashed_password="hash",
        deleted_at=get_datetime_utc(),
    )
    request_session = session_with(deleted)
    assert await AuthService(request_session).request_password_reset("deleted") is None
    request_session.commit.assert_not_awaited()

    reset = PasswordResetTokenEntity(
        user_id=deleted.id,
        token_hash=hash_secret("token"),
        expires_at=get_datetime_utc() + timedelta(minutes=5),
    )
    consume_session = session_with(reset)
    consume_session.get.return_value = deleted
    with pytest.raises(InvalidTokenException):
        await AuthService(consume_session).reset_password("token", "new-password")
