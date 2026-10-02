from sqlmodel import col, select

from apps.users.domain.auth_entity import (
    PermissionEntity,
    RoleEntity,
    RolePermissionEntity,
    UserRoleEntity,
)
from apps.users.domain.dto import UserDTO
from apps.users.domain.entity import UserEntity
from core.deps import CurrentUser, SessionDep
from utils.exceptions import NotAllowedException


async def user_permissions(user: UserEntity, session: SessionDep) -> set[str]:
    """Return all permission names granted to a user through roles."""
    if user.is_superuser:
        return {"*"}
    result = await session.exec(
        select(PermissionEntity.name)
        .join(
            RolePermissionEntity,
            col(RolePermissionEntity.permission_id) == col(PermissionEntity.id),
        )
        .join(UserRoleEntity, col(UserRoleEntity.role_id) == col(RolePermissionEntity.role_id))
        .join(RoleEntity, col(RoleEntity.id) == col(UserRoleEntity.role_id))
        .where(
            col(UserRoleEntity.user_id) == user.id,
            col(RoleEntity.deleted_at).is_(None),
            col(PermissionEntity.deleted_at).is_(None),
        )
    )
    return set(result.all())


class RequirePermission:
    """FastAPI dependency requiring one named permission or superuser status."""

    def __init__(self, permission: str) -> None:
        self.permission = permission

    async def __call__(self, user: CurrentUser, session: SessionDep) -> UserEntity:
        permissions = await user_permissions(user, session)
        if "*" not in permissions and self.permission not in permissions:
            raise NotAllowedException(f"Permission required: {self.permission}")
        return user


def require_user_management(
    actor: UserEntity, target: UserEntity | UserDTO | None = None, *, grant_superuser: bool = False
) -> None:
    """Reserve privileged account changes for superusers."""
    if not actor.is_superuser and (grant_superuser or (target is not None and target.is_superuser)):
        raise NotAllowedException("Only superusers may manage superuser accounts")
