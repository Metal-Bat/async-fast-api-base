import hashlib
import secrets
from datetime import timedelta
from uuid import UUID, uuid7

import jwt
from sqlalchemy import or_, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.application.service import ClientService
from apps.users.domain.auth_dto import LoginDTO, TokenPairDTO
from apps.users.domain.auth_entity import (
    AuthAuditEventEntity,
    AuthSessionEntity,
    LoginFailureEntity,
    PasswordResetTokenEntity,
)
from apps.users.domain.entity import UserEntity
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import AccountLockedException, InvalidCredentialError, InvalidTokenException
from utils.security import hash_password, verify_password


def hash_secret(value: str) -> str:
    """Return a deterministic SHA-256 digest for a high-entropy opaque token."""
    return hashlib.sha256(value.encode()).hexdigest()


class AuthService:
    """Manage access tokens and persisted device sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def audit(
        self,
        event_type: str,
        *,
        user_id: UUID | None = None,
        success: bool = True,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, object] | None = None,
        notice_user_id: UUID | None = None,
    ) -> None:
        """Stage one security event in the caller's transaction."""
        event = AuthAuditEventEntity(
            user_id=user_id,
            event_type=event_type,
            success=success,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )

        self.session.add(event)
        if (
            success
            and user_id is not None
            and event_type
            in {"password.changed", "password.reset", "password.reset.admin", "logout.all"}
        ):
            await self.session.flush()
            from apps.notifications.application.events import stage_notice

            await stage_notice(
                self.session,
                map_id="MAP-14",
                event_id=event.id,
                recipient_id=notice_user_id or user_id,
                target_kind="account",
                target_id=notice_user_id or user_id,
            )

    def _access_token(self, user: UserEntity, session_id: UUID) -> str:
        now = get_datetime_utc()
        return jwt.encode(
            {
                "sub": str(user.id),
                "type": "access",
                "jti": str(uuid7()),
                "sid": str(session_id),
                "iat": now,
                "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

    def _pair(
        self, user: UserEntity, auth_session: AuthSessionEntity, refresh: str
    ) -> TokenPairDTO:
        return TokenPairDTO(
            access_token=self._access_token(user, auth_session.id),
            refresh_token=refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def login(
        self,
        data: LoginDTO,
        *,
        request_id: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPairDTO:
        """Authenticate credentials and create a persisted refresh-token family."""
        identifier = data.username.casefold()
        now = get_datetime_utc()
        failure = (
            await self.session.exec(
                select(LoginFailureEntity).where(LoginFailureEntity.identifier == identifier)
            )
        ).one_or_none()
        if failure and failure.locked_until and failure.locked_until > now:
            raise AccountLockedException("Account is temporarily locked")
        user = (
            await self.session.exec(
                select(UserEntity).where(
                    or_(
                        col(UserEntity.username) == data.username,
                        col(UserEntity.email) == data.username,
                    )
                )
            )
        ).one_or_none()
        valid = (
            user is not None
            and user.deleted_at is None
            and await verify_password(data.password, user.hashed_password)
        )
        if not valid:
            if failure is None:
                failure = LoginFailureEntity(identifier=identifier)
            failure.failure_count += 1
            if failure.failure_count >= settings.MAX_LOGIN_FAILURES:
                failure.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
                failure.failure_count = 0
            self.session.add(failure)
            await self.audit(
                "login",
                user_id=user.id if user else None,
                success=False,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await self.session.commit()
            raise InvalidCredentialError("Invalid username or password")
        if failure:
            await self.session.delete(failure)
        client = await ClientService(self.session).authenticate(
            data.client_key, data.client_secret, data.client_release
        )
        raw_refresh = secrets.token_urlsafe(48)
        auth_session = AuthSessionEntity(
            user_id=user.id,
            client_id=client.client_id,
            client_release_id=client.release_id,
            family_id=uuid7(),
            refresh_token_hash=hash_secret(raw_refresh),
            device_name=data.device_name,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.session.add(auth_session)
        await self.session.flush()
        await self.audit(
            "login",
            user_id=user.id,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"session_id": str(auth_session.id)},
        )
        await self.session.commit()
        return self._pair(user, auth_session, raw_refresh)

    async def refresh(self, raw_refresh: str) -> TokenPairDTO:
        """Rotate a refresh token; reuse revokes its entire token family."""
        now = get_datetime_utc()
        auth_session = (
            await self.session.exec(
                select(AuthSessionEntity).where(
                    AuthSessionEntity.refresh_token_hash == hash_secret(raw_refresh)
                )
            )
        ).one_or_none()
        if auth_session is None or auth_session.expires_at <= now:
            raise InvalidTokenException("Invalid or expired refresh token")
        if auth_session.revoked_at is not None:
            await self.session.exec(
                update(AuthSessionEntity)
                .where(col(AuthSessionEntity.family_id) == auth_session.family_id)
                .values(revoked_at=now)
            )
            await self.session.commit()
            raise InvalidTokenException("Refresh token reuse detected")
        await ClientService(self.session).for_session(auth_session)
        auth_session.revoked_at = now
        replacement_raw = secrets.token_urlsafe(48)
        replacement = AuthSessionEntity(
            user_id=auth_session.user_id,
            client_id=auth_session.client_id,
            client_release_id=auth_session.client_release_id,
            family_id=auth_session.family_id,
            refresh_token_hash=hash_secret(replacement_raw),
            device_name=auth_session.device_name,
            ip_address=auth_session.ip_address,
            user_agent=auth_session.user_agent,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        self.session.add(auth_session)
        self.session.add(replacement)
        user = await self.session.get(UserEntity, auth_session.user_id)
        if user is None or user.deleted_at is not None:
            raise InvalidTokenException("Session user is unavailable")
        await self.session.flush()
        await self.audit(
            "token.refresh", user_id=user.id, details={"session_id": str(replacement.id)}
        )
        await self.session.commit()
        return self._pair(user, replacement, replacement_raw)

    async def logout(self, raw_refresh: str) -> None:
        """Revoke one submitted refresh token."""
        auth_session = (
            await self.session.exec(
                select(AuthSessionEntity).where(
                    AuthSessionEntity.refresh_token_hash == hash_secret(raw_refresh)
                )
            )
        ).one_or_none()
        if auth_session and auth_session.revoked_at is None:
            auth_session.revoked_at = get_datetime_utc()
            self.session.add(auth_session)
            await self.audit("logout", user_id=auth_session.user_id)
            await self.session.commit()

    async def logout_all(self, user_id: UUID) -> None:
        """Revoke every active device session belonging to a user."""
        await self.session.exec(
            update(AuthSessionEntity)
            .where(
                col(AuthSessionEntity.user_id) == user_id,
                col(AuthSessionEntity.revoked_at).is_(None),
            )
            .values(revoked_at=get_datetime_utc())
        )
        await self.audit("logout.all", user_id=user_id)
        await self.session.commit()

    async def request_password_reset(self, identifier: str) -> str | None:
        """Create a single-use token; callers must deliver it through a trusted channel."""
        user = (
            await self.session.exec(
                select(UserEntity).where(
                    or_(col(UserEntity.username) == identifier, col(UserEntity.email) == identifier)
                )
            )
        ).one_or_none()
        if user is None or user.deleted_at is not None:
            return None
        raw = secrets.token_urlsafe(48)
        self.session.add(
            PasswordResetTokenEntity(
                user_id=user.id,
                token_hash=hash_secret(raw),
                expires_at=get_datetime_utc()
                + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
            )
        )
        await self.audit("password.reset.requested", user_id=user.id)
        await self.session.commit()
        return raw

    async def reset_password(self, token: str, new_password: str) -> None:
        """Consume a reset token, replace the password, and revoke active sessions."""
        now = get_datetime_utc()
        reset = (
            await self.session.exec(
                select(PasswordResetTokenEntity).where(
                    PasswordResetTokenEntity.token_hash == hash_secret(token)
                )
            )
        ).one_or_none()
        if reset is None or reset.used_at is not None or reset.expires_at <= now:
            raise InvalidTokenException("Invalid or expired password reset token")
        user = await self.session.get(UserEntity, reset.user_id)
        if user is None or user.deleted_at is not None:
            raise InvalidTokenException("Invalid or expired password reset token")
        user.hashed_password = await hash_password(new_password)
        reset.used_at = now
        self.session.add_all([user, reset])
        await self.session.exec(
            update(AuthSessionEntity)
            .where(
                col(AuthSessionEntity.user_id) == user.id,
                col(AuthSessionEntity.revoked_at).is_(None),
            )
            .values(revoked_at=now)
        )
        await self.audit("password.reset", user_id=user.id)
        await self.session.commit()

    async def change_password(self, user: UserEntity, current: str, new: str) -> None:
        """Verify and replace a password, revoking all device sessions."""
        if not await verify_password(current, user.hashed_password):
            raise InvalidCredentialError("Current password is invalid")
        user.hashed_password = await hash_password(new)
        self.session.add(user)
        await self.audit("password.changed", user_id=user.id)
        await self.session.exec(
            update(AuthSessionEntity)
            .where(
                col(AuthSessionEntity.user_id) == user.id,
                col(AuthSessionEntity.revoked_at).is_(None),
            )
            .values(revoked_at=get_datetime_utc())
        )
        await self.session.commit()

    async def stage_admin_password_reset(
        self,
        user: UserEntity,
        new_password: str,
        *,
        actor: UserEntity,
        request_id: str | None = None,
    ) -> None:
        """Stage a password replacement and credential revocation; caller commits."""
        from apps.users.application.authorization import require_user_management

        require_user_management(actor, user)
        now = get_datetime_utc()
        user.hashed_password = await hash_password(new_password)
        self.session.add(user)
        await self.session.exec(
            update(AuthSessionEntity)
            .where(
                col(AuthSessionEntity.user_id) == user.id,
                col(AuthSessionEntity.revoked_at).is_(None),
            )
            .values(revoked_at=now)
        )
        await self.session.exec(
            update(PasswordResetTokenEntity)
            .where(
                col(PasswordResetTokenEntity.user_id) == user.id,
                col(PasswordResetTokenEntity.used_at).is_(None),
            )
            .values(used_at=now)
        )
        await self.audit(
            "password.reset.admin",
            user_id=actor.id,
            request_id=request_id,
            details={"target_user_id": str(user.id)},
            notice_user_id=user.id,
        )
