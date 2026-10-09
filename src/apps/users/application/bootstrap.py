"""Install explicit ordinary accounts once; existing identities remain operator-owned."""

from uuid import uuid5

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.users.application.service import get_user_service
from apps.users.domain.auth_entity import RoleEntity, UserRoleEntity
from apps.users.domain.bootstrap import BootstrapManifest, BootstrapSummary
from apps.users.domain.entity import UserEntity
from utils.exceptions import VersionConflictException
from utils.security import hash_password


async def install_accounts(
    session: AsyncSession, manifest: BootstrapManifest, *, check_only: bool = False
) -> BootstrapSummary:
    """The caller owns commit; repairs never reset passwords or restore revoked grants."""
    if len({account.persona for account in manifest.accounts}) != len(manifest.accounts):
        raise ValueError("Installation personas must be distinct")
    summary = BootstrapSummary()
    if not check_only:
        await session.exec(select(func.pg_advisory_xact_lock(0x4150504245303034)))
    for account in manifest.accounts:
        identifier = uuid5(manifest.installation_id, f"user:{account.persona}")
        existing = await session.get(UserEntity, identifier)
        if existing is not None:
            if existing.deleted_at is not None or existing.is_superuser:
                raise VersionConflictException("Installed ordinary account was removed or elevated")
            summary.preserved_users.append(existing.username)
            continue
        collision = (
            await session.exec(select(UserEntity).where(UserEntity.username == account.username))
        ).one_or_none()
        if collision is not None:
            raise VersionConflictException("Installation username is owned by another identity")
        if check_only:
            summary.missing_users.append(account.username)
            continue
        role = (
            await session.exec(
                select(RoleEntity).where(RoleEntity.name == f"app.{account.persona}.v1")
            )
        ).one_or_none()
        if role is None or role.deleted_at is not None:
            raise VersionConflictException("Installation role is unavailable")
        user = await get_user_service(session).create(
            UserEntity(
                id=identifier,
                username=account.username,
                hashed_password=await hash_password(account.password.get_secret_value()),
            )
        )
        session.add(UserRoleEntity(user_id=user.id, role_id=role.id))
        await session.flush()
        summary.created_users.append(user.username)
    return summary
