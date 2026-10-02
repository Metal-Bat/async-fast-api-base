from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import TypeAdapter
from sqlmodel import col, delete, select

from apps.reporting.application.service import ReportService
from apps.reporting.domain.dto import ReportDetailDTO
from apps.users.application.auth_service import AuthService
from apps.users.application.authorization import RequirePermission, require_user_management
from apps.users.application.reporting import USER_REPORT
from apps.users.application.service import UserService, get_user_service
from apps.users.domain.auth_dto import (
    AdminResetPasswordDTO,
    AssignRoleDTO,
    AuthAuditEventDTO,
    AuthAuditEventQuery,
    PermissionCreateDTO,
    PermissionDTO,
    PermissionQuery,
    PermissionUpdateDTO,
    RoleCreateDTO,
    RoleDTO,
    RoleQuery,
    RoleUpdateDTO,
)
from apps.users.domain.auth_entity import (
    AuthAuditEventEntity,
    PermissionEntity,
    RoleEntity,
    RolePermissionEntity,
    UserRoleEntity,
)
from apps.users.domain.dto import UserCreateDTO, UserDTO, UserQuery, UserUpdateDTO
from apps.users.domain.entity import UserEntity
from core.deps import SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import create_ref_id, open_ref_id
from utils.base_schema import response_schema
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException
from utils.localization import resolve_language
from utils.pagination import Page, paginate_entities
from utils.presenter import PageResponse, SuccessResponse, page_response, success_response
from utils.security import hash_password

router = APIRouter(responses=response_schema(), prefix="/admin", tags=["admin"])
AdminUser = Annotated[UserEntity, Depends(RequirePermission("admin.users.manage"))]
AdminPermission = Annotated[UserEntity, Depends(RequirePermission("admin.permissions.manage"))]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]


@router.post("/users", response_model=SuccessResponse[UserDTO], status_code=201)
async def create_user(
    request: Request, data: UserCreateDTO, actor: AdminUser, session: SessionDep
) -> SuccessResponse[UserDTO]:
    """Create a user as an administrator."""
    require_user_management(actor, grant_superuser=data.is_superuser)
    values = data.model_dump(exclude={"password"})
    user = UserEntity(**values, hashed_password=await hash_password(data.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return success_response(
        request, TypeAdapter(UserDTO).validate_python(user, from_attributes=True), code=201
    )


@router.post("/users/search", response_model=PageResponse[Page[UserDTO]])
async def list_admin_users(
    request: Request, query: UserQuery, _: AdminUser, service: UserServiceDep
) -> PageResponse[Page[UserDTO]]:
    """Return a filtered page of users for administrative management."""
    return page_response(request, await service.list_public(query))


@router.post("/users/report", response_model=SuccessResponse[ReportDetailDTO], status_code=202)
async def report_admin_users(
    request: Request, query: UserQuery, actor: AdminUser, session: SessionDep
) -> SuccessResponse[ReportDetailDTO]:
    """Durably queue an AES-encrypted user workbook using the search filters."""
    report = await ReportService(session).create(
        USER_REPORT.key,
        actor,
        query,
        resolve_language(request.headers.get("Accept-Language")),
    )
    detail = TypeAdapter(ReportDetailDTO).validate_python(report, from_attributes=True)
    return success_response(request, detail, code=202)


@router.get("/users/{ref_id}", response_model=SuccessResponse[UserDTO])
async def get_admin_user(
    request: Request, ref_id: str, actor: AdminUser, service: UserServiceDep
) -> SuccessResponse[UserDTO]:
    """Return one user for administrative management."""
    user = await service.get_public_by_id(ref_id)
    require_user_management(actor, user)
    return success_response(request, user, code=200)


@router.put("/users/{ref_id}", response_model=SuccessResponse[UserDTO])
async def update_user(
    request: Request, ref_id: str, data: UserUpdateDTO, actor: AdminUser, session: SessionDep
) -> SuccessResponse[UserDTO]:
    """Update an existing user with optimistic locking."""
    user_id, version = open_ref_id(ref_id)
    user = await session.get(UserEntity, user_id)
    if user is None:
        raise NotFoundException("User not found")
    require_user_management(actor, user)
    if user.version != version:
        raise VersionConflictException("User version is stale")
    values = data.model_dump(exclude_unset=True, exclude={"ref_id", "password"})
    require_user_management(actor, user, grant_superuser=data.is_superuser is True)
    if data.password:
        await AuthService(session).stage_admin_password_reset(
            user, data.password, actor=actor, request_id=getattr(request.state, "request_id", None)
        )
    user.sqlmodel_update(values)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return success_response(
        request, TypeAdapter(UserDTO).validate_python(user, from_attributes=True), code=200
    )


@router.delete("/users/{ref_id}", status_code=200)
async def delete_user(
    request: Request, ref_id: str, actor: AdminUser, session: SessionDep
) -> SuccessResponse[None]:
    """Soft-delete a user account."""
    user_id, version = open_ref_id(ref_id)
    user = await session.get(UserEntity, user_id)
    if user is None:
        raise NotFoundException("User not found")
    require_user_management(actor, user)
    if user.version != version:
        raise VersionConflictException("User version is stale")
    user.deleted_at = get_datetime_utc()
    session.add(user)
    await session.commit()
    return success_response(request, None, code=204)


@router.post("/users/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def user_history(
    request: Request,
    ref_id: str,
    query: HistoryQuery,
    _: AdminUser,
    session: SessionDep,
) -> PageResponse[Page[HistoryRecordDTO]]:
    """Return field-level changes for one user."""
    user_id = open_ref_id(ref_id)[0]
    return page_response(
        request, await HistoryService.for_entity(session, "user").list(query, user_id)
    )


@router.post("/users/{ref_id}/restore", response_model=SuccessResponse[UserDTO])
async def restore_user(
    request: Request, ref_id: str, actor: AdminUser, session: SessionDep
) -> SuccessResponse[UserDTO]:
    """Restore a soft-deleted user with optimistic locking."""
    user_id, version = open_ref_id(ref_id)
    user = await session.get(UserEntity, user_id)
    if user is None:
        raise NotFoundException("User not found")
    require_user_management(actor, user)
    if user.version != version:
        raise VersionConflictException("User version is stale")
    user.deleted_at = None
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return success_response(
        request, TypeAdapter(UserDTO).validate_python(user, from_attributes=True), code=200
    )


@router.post("/permissions", response_model=SuccessResponse[PermissionDTO], status_code=201)
async def create_permission(
    request: Request, data: PermissionCreateDTO, actor: AdminPermission, session: SessionDep
) -> SuccessResponse[PermissionDTO]:
    """Create an atomic permission."""
    permission = PermissionEntity(**data.model_dump())
    session.add_all(
        [permission, AuthAuditEventEntity(user_id=actor.id, event_type="permission.created")]
    )
    await session.commit()
    await session.refresh(permission)
    return success_response(
        request,
        TypeAdapter(PermissionDTO).validate_python(permission, from_attributes=True),
        code=201,
    )


@router.post("/permissions/search", response_model=PageResponse[Page[PermissionDTO]])
async def list_permissions(
    request: Request, query: PermissionQuery, _: AdminPermission, session: SessionDep
) -> PageResponse[Page[PermissionDTO]]:
    """Return a filtered page of atomic permissions."""
    page = await paginate_entities(
        session, PermissionEntity, query, default_ordering=("name", "id")
    )
    return page_response(
        request, TypeAdapter(Page[PermissionDTO]).validate_python(page, from_attributes=True)
    )


@router.post("/permissions/report", response_model=PageResponse[Page[PermissionDTO]])
async def report_permissions(
    request: Request, query: PermissionQuery, actor: AdminPermission, session: SessionDep
) -> PageResponse[Page[PermissionDTO]]:
    """Return permissions using the same filters and page contract as search."""
    return await list_permissions(request, query, actor, session)


async def _permission(ref_id: str, session: SessionDep) -> PermissionEntity:
    permission_id = open_ref_id(ref_id)[0]
    permission = await session.get(PermissionEntity, permission_id)
    if permission is None:
        raise NotFoundException("Permission not found")
    return permission


@router.get("/permissions/{ref_id}", response_model=SuccessResponse[PermissionDTO])
async def get_permission(
    request: Request, ref_id: str, _: AdminPermission, session: SessionDep
) -> SuccessResponse[PermissionDTO]:
    """Return one permission definition."""
    return success_response(
        request,
        TypeAdapter(PermissionDTO).validate_python(
            await _permission(ref_id, session), from_attributes=True
        ),
    )


@router.put("/permissions/{ref_id}", response_model=SuccessResponse[PermissionDTO])
async def update_permission(
    request: Request,
    ref_id: str,
    data: PermissionUpdateDTO,
    actor: AdminPermission,
    session: SessionDep,
) -> SuccessResponse[PermissionDTO]:
    """Update a permission definition with optimistic locking."""
    _, version = open_ref_id(ref_id)
    permission = await _permission(ref_id, session)
    if permission.version != version:
        raise VersionConflictException("Permission version is stale")
    permission.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add_all(
        [permission, AuthAuditEventEntity(user_id=actor.id, event_type="permission.updated")]
    )
    await session.commit()
    await session.refresh(permission)
    return success_response(
        request, TypeAdapter(PermissionDTO).validate_python(permission, from_attributes=True)
    )


@router.delete("/permissions/{ref_id}", status_code=200)
async def delete_permission(
    request: Request, ref_id: str, actor: AdminPermission, session: SessionDep
) -> SuccessResponse[None]:
    """Soft-delete a permission identified by its opaque reference."""
    _, version = open_ref_id(ref_id)
    permission = await _permission(ref_id, session)
    if permission.version != version:
        raise VersionConflictException("Permission version is stale")
    permission.deleted_at = get_datetime_utc()
    session.add_all(
        [permission, AuthAuditEventEntity(user_id=actor.id, event_type="permission.deleted")]
    )
    await session.commit()
    return success_response(request, None, code=204)


@router.post("/permissions/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def permission_history(
    request: Request,
    ref_id: str,
    query: HistoryQuery,
    _: AdminPermission,
    session: SessionDep,
) -> PageResponse[Page[HistoryRecordDTO]]:
    """Return field-level changes for one permission."""
    permission_id = open_ref_id(ref_id)[0]
    return page_response(
        request,
        await HistoryService.for_entity(session, "permission").list(query, permission_id),
    )


@router.post("/audit-events/search", response_model=PageResponse[Page[AuthAuditEventDTO]])
async def list_audit_events(
    request: Request,
    query: AuthAuditEventQuery,
    _: AdminPermission,
    session: SessionDep,
) -> PageResponse[Page[AuthAuditEventDTO]]:
    """Return a filtered page of authentication and authorization audit events."""
    page = await paginate_entities(session, AuthAuditEventEntity, query, default_ordering=("-id",))
    return page_response(
        request, TypeAdapter(Page[AuthAuditEventDTO]).validate_python(page, from_attributes=True)
    )


@router.get("/audit-events/{ref_id}", response_model=SuccessResponse[AuthAuditEventDTO])
async def get_audit_event(
    request: Request, ref_id: str, _: AdminPermission, session: SessionDep
) -> SuccessResponse[AuthAuditEventDTO]:
    """Return one immutable authentication or authorization audit event."""
    event = await session.get(AuthAuditEventEntity, open_ref_id(ref_id)[0])
    if event is None:
        raise NotFoundException("Audit event not found")
    return success_response(
        request, TypeAdapter(AuthAuditEventDTO).validate_python(event, from_attributes=True)
    )


@router.post("/audit-events/report", response_model=PageResponse[Page[AuthAuditEventDTO]])
async def report_audit_events(
    request: Request,
    query: AuthAuditEventQuery,
    actor: AdminPermission,
    session: SessionDep,
) -> PageResponse[Page[AuthAuditEventDTO]]:
    """Return audit events using the same filters and page contract as search."""
    return await list_audit_events(request, query, actor, session)


@router.post("/roles", response_model=SuccessResponse[RoleDTO], status_code=201)
async def create_role(
    request: Request, data: RoleCreateDTO, actor: AdminPermission, session: SessionDep
) -> SuccessResponse[RoleDTO]:
    """Create a role and bind its declared permissions."""
    role = RoleEntity(name=data.name, description=data.description)
    session.add(role)
    await session.flush()
    permissions = list(
        (
            await session.exec(
                select(PermissionEntity).where(col(PermissionEntity.name).in_(data.permissions))
            )
        ).all()
    )
    session.add_all(
        [RolePermissionEntity(role_id=role.id, permission_id=item.id) for item in permissions]
    )
    session.add(AuthAuditEventEntity(user_id=actor.id, event_type="role.created"))
    await session.commit()
    await session.refresh(role)
    return success_response(
        request,
        RoleDTO(
            ref_id=create_ref_id(role.id, role.version),
            name=role.name,
            description=role.description,
            permissions=[p.name for p in permissions],
            created_at=role.created_at,
            updated_at=role.updated_at,
            deleted_at=role.deleted_at,
        ),
        code=201,
    )


async def _role(ref_id: str, session: SessionDep) -> RoleEntity:
    role_id = open_ref_id(ref_id)[0]
    role = await session.get(RoleEntity, role_id)
    if role is None:
        raise NotFoundException("Role not found")
    return role


async def _role_dto(role: RoleEntity, session: SessionDep) -> RoleDTO:
    permissions = list(
        (
            await session.exec(
                select(PermissionEntity)
                .join(
                    RolePermissionEntity,
                    col(RolePermissionEntity.permission_id) == col(PermissionEntity.id),
                )
                .where(
                    col(RolePermissionEntity.role_id) == role.id,
                    col(PermissionEntity.deleted_at).is_(None),
                )
                .order_by(col(PermissionEntity.name))
            )
        ).all()
    )
    return RoleDTO(
        ref_id=create_ref_id(role.id, role.version),
        name=role.name,
        description=role.description,
        permissions=[permission.name for permission in permissions],
        created_at=role.created_at,
        updated_at=role.updated_at,
        deleted_at=role.deleted_at,
    )


@router.post("/roles/search", response_model=PageResponse[Page[RoleDTO]])
async def search_roles(
    request: Request, query: RoleQuery, _: AdminPermission, session: SessionDep
) -> PageResponse[Page[RoleDTO]]:
    """Return a filtered page of roles with their permission names."""
    entities = await paginate_entities(session, RoleEntity, query, default_ordering=("name", "id"))
    items = [await _role_dto(role, session) for role in entities.items]
    return page_response(
        request,
        Page[RoleDTO](
            items=items,
            page=entities.page,
            size=entities.size,
            total=entities.total,
        ),
    )


@router.post("/roles/report", response_model=PageResponse[Page[RoleDTO]])
async def report_roles(
    request: Request, query: RoleQuery, actor: AdminPermission, session: SessionDep
) -> PageResponse[Page[RoleDTO]]:
    """Return roles using the same filters and page contract as search."""
    return await search_roles(request, query, actor, session)


@router.get("/roles/{ref_id}", response_model=SuccessResponse[RoleDTO])
async def get_role(
    request: Request, ref_id: str, _: AdminPermission, session: SessionDep
) -> SuccessResponse[RoleDTO]:
    """Return one role and all assigned permissions."""
    return success_response(request, await _role_dto(await _role(ref_id, session), session))


@router.put("/roles/{ref_id}", response_model=SuccessResponse[RoleDTO])
async def update_role(
    request: Request,
    ref_id: str,
    data: RoleUpdateDTO,
    actor: AdminPermission,
    session: SessionDep,
) -> SuccessResponse[RoleDTO]:
    """Update a role and optionally replace its permission assignments."""
    _, version = open_ref_id(ref_id)
    role = await _role(ref_id, session)
    if role.version != version:
        raise VersionConflictException("Role version is stale")
    role.sqlmodel_update(data.model_dump(exclude_unset=True, exclude={"permissions"}))
    if data.permissions is not None:
        await session.exec(
            delete(RolePermissionEntity).where(col(RolePermissionEntity.role_id) == role.id)
        )
        permissions = list(
            (
                await session.exec(
                    select(PermissionEntity).where(
                        col(PermissionEntity.name).in_(data.permissions),
                        col(PermissionEntity.deleted_at).is_(None),
                    )
                )
            ).all()
        )
        session.add_all(
            [RolePermissionEntity(role_id=role.id, permission_id=item.id) for item in permissions]
        )
    session.add_all([role, AuthAuditEventEntity(user_id=actor.id, event_type="role.updated")])
    await session.commit()
    await session.refresh(role)
    return success_response(request, await _role_dto(role, session))


@router.delete("/roles/{ref_id}", status_code=200)
async def delete_role(
    request: Request, ref_id: str, actor: AdminPermission, session: SessionDep
) -> SuccessResponse[None]:
    """Soft-delete a role identified by its opaque reference."""
    _, version = open_ref_id(ref_id)
    role = await _role(ref_id, session)
    if role.version != version:
        raise VersionConflictException("Role version is stale")
    role.deleted_at = get_datetime_utc()
    session.add_all([role, AuthAuditEventEntity(user_id=actor.id, event_type="role.deleted")])
    await session.commit()
    return success_response(request, None, code=204)


@router.post("/roles/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def role_history(
    request: Request,
    ref_id: str,
    query: HistoryQuery,
    _: AdminPermission,
    session: SessionDep,
) -> PageResponse[Page[HistoryRecordDTO]]:
    """Return field-level changes for one role."""
    role_id = open_ref_id(ref_id)[0]
    return page_response(
        request, await HistoryService.for_entity(session, "role").list(query, role_id)
    )


@router.post("/users/{ref_id}/roles", status_code=200)
async def assign_role(
    request: Request, ref_id: str, data: AssignRoleDTO, actor: AdminPermission, session: SessionDep
) -> SuccessResponse[None]:
    """Assign a named role to a user."""
    user_id, _ = open_ref_id(ref_id)
    role = (
        await session.exec(select(RoleEntity).where(RoleEntity.name == data.role_name))
    ).one_or_none()
    if (
        role is None
        or role.deleted_at is not None
        or await session.get(UserEntity, user_id) is None
    ):
        raise NotFoundException("User or role not found")
    session.add(UserRoleEntity(user_id=user_id, role_id=role.id))
    session.add(
        AuthAuditEventEntity(
            user_id=actor.id,
            event_type="role.assigned",
            details={"target_user_id": str(user_id), "role": role.name},
        )
    )
    await session.commit()
    return success_response(request, None, code=204)


@router.post("/users/{ref_id}/reset-password", response_model=SuccessResponse[None])
async def reset_user_password(
    request: Request,
    ref_id: str,
    data: AdminResetPasswordDTO,
    actor: AdminUser,
    session: SessionDep,
) -> SuccessResponse[None]:
    """Reset an active user's password and revoke all existing credentials."""
    user_id, version = open_ref_id(ref_id)
    user = await session.get(UserEntity, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundException("User not found")
    require_user_management(actor, user)
    if user.version != version:
        raise VersionConflictException("User version is stale")
    await AuthService(session).stage_admin_password_reset(
        user, data.new_password, actor=actor, request_id=getattr(request.state, "request_id", None)
    )
    await session.commit()
    return success_response(request, None, code=204)
