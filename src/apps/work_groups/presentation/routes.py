"""Administrative work-group HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import TypeAdapter
from sqlmodel import col

from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from apps.work_groups.application.service import WorkGroupService
from apps.work_groups.domain.dto import (
    MemberChangeDTO,
    UserSelectQuery,
    WorkGroupCreateDTO,
    WorkGroupDTO,
    WorkGroupQuery,
    WorkGroupSelectDTO,
    WorkGroupSelectQuery,
    WorkGroupUpdateDTO,
)
from apps.work_groups.domain.entity import WorkGroupEntity
from core.deps import SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import create_ref_id, open_ref_id
from utils.base_schema import response_schema
from utils.pagination import Page, paginate_entities
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    select_response,
    success_response,
)
from utils.select import SelectResponseFormat

router = APIRouter(prefix="/admin/work-groups", tags=["work-groups"], responses=response_schema())
user_selector_router = APIRouter(prefix="/admin/users", tags=["users"], responses=response_schema())
GroupAdmin = Annotated[UserEntity, Depends(RequirePermission("admin.work_groups.manage"))]


def _service(session: SessionDep) -> WorkGroupService:
    return WorkGroupService(session)


GroupServiceDep = Annotated[WorkGroupService, Depends(_service)]


@router.post("/search", response_model=PageResponse[Page[WorkGroupDTO]])
async def search_groups(
    request: Request, query: WorkGroupQuery, _: GroupAdmin, session: SessionDep
) -> PageResponse[Page[WorkGroupDTO]]:
    page = await paginate_entities(session, WorkGroupEntity, query, default_ordering=("code", "id"))
    return page_response(
        request, TypeAdapter(Page[WorkGroupDTO]).validate_python(page, from_attributes=True)
    )


@router.get("/{ref_id}", response_model=SuccessResponse[WorkGroupDTO])
async def get_group(
    request: Request, ref_id: str, _: GroupAdmin, service: GroupServiceDep
) -> SuccessResponse[WorkGroupDTO]:
    return success_response(
        request, WorkGroupDTO.model_validate(await service.get_group(ref_id), from_attributes=True)
    )


@router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def group_history(
    request: Request, ref_id: str, query: HistoryQuery, _: GroupAdmin, session: SessionDep
) -> PageResponse[Page[HistoryRecordDTO]]:
    group_id = open_ref_id(ref_id)[0]
    return page_response(
        request, await HistoryService.for_entity(session, "work_group").list(query, group_id)
    )


@router.post("/report", response_model=PageResponse[Page[WorkGroupDTO]])
async def report_groups(
    request: Request, query: WorkGroupQuery, actor: GroupAdmin, session: SessionDep
) -> PageResponse[Page[WorkGroupDTO]]:
    return await search_groups(request, query, actor, session)


@router.post("", response_model=SuccessResponse[WorkGroupDTO], status_code=201)
async def create_group(
    request: Request,
    data: WorkGroupCreateDTO,
    actor: GroupAdmin,
    service: GroupServiceDep,
    session: SessionDep,
) -> SuccessResponse[WorkGroupDTO]:
    group = await service.create_group(data, actor.id)
    await session.commit()
    await session.refresh(group)
    return success_response(
        request, WorkGroupDTO.model_validate(group, from_attributes=True), code=201
    )


@router.put("/{ref_id}", response_model=SuccessResponse[WorkGroupDTO])
async def update_group(
    request: Request,
    ref_id: str,
    data: WorkGroupUpdateDTO,
    actor: GroupAdmin,
    service: GroupServiceDep,
    session: SessionDep,
) -> SuccessResponse[WorkGroupDTO]:
    group = await service.replace_group(ref_id, data, actor.id)
    await session.commit()
    await session.refresh(group)
    return success_response(request, WorkGroupDTO.model_validate(group, from_attributes=True))


@router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete_group(
    request: Request, ref_id: str, actor: GroupAdmin, service: GroupServiceDep, session: SessionDep
) -> SuccessResponse[None]:
    await service.delete_group(ref_id, actor.id)
    await session.commit()
    return success_response(request, None, code=204)


@router.post("/select")
async def select_groups(
    request: Request,
    query: WorkGroupSelectQuery,
    _: GroupAdmin,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[WorkGroupSelectDTO]] | list[WorkGroupSelectDTO]:
    criteria = []
    if not query.include_deleted:
        criteria.append(col(WorkGroupEntity.deleted_at).is_(None))
    if not query.include_inactive:
        criteria.append(col(WorkGroupEntity.is_active).is_(True))
    page = await paginate_entities(
        session,
        WorkGroupEntity,
        query,
        criteria=tuple(criteria),
        default_ordering=("name", "id"),
        live_only=not query.include_deleted,
    )
    return select_response(
        request,
        Page[WorkGroupSelectDTO](
            items=[
                WorkGroupSelectDTO(key=create_ref_id(item.id, item.version), value=item.name)
                for item in page.items
            ],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
        response_format,
    )


@user_selector_router.post("/select")
async def select_users(
    request: Request,
    query: UserSelectQuery,
    _: GroupAdmin,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[WorkGroupSelectDTO]] | list[WorkGroupSelectDTO]:
    criteria = () if query.include_deleted else (col(UserEntity.deleted_at).is_(None),)
    page = await paginate_entities(
        session,
        UserEntity,
        query,
        criteria=criteria,
        default_ordering=("username", "id"),
        live_only=not query.include_deleted,
    )
    return select_response(
        request,
        Page[WorkGroupSelectDTO](
            items=[
                WorkGroupSelectDTO(key=create_ref_id(item.id, item.version), value=item.username)
                for item in page.items
            ],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
        response_format,
    )


@router.post("/{ref_id}/members", response_model=SuccessResponse[None])
async def add_member(
    request: Request,
    ref_id: str,
    data: MemberChangeDTO,
    actor: GroupAdmin,
    service: GroupServiceDep,
    session: SessionDep,
) -> SuccessResponse[None]:
    await service.add_member(ref_id, open_ref_id(data.user_ref_id)[0], actor_id=actor.id)
    await session.commit()
    return success_response(request, None)


@router.post("/{ref_id}/members/deactivate", response_model=SuccessResponse[None])
async def deactivate_member(
    request: Request,
    ref_id: str,
    data: MemberChangeDTO,
    actor: GroupAdmin,
    service: GroupServiceDep,
    session: SessionDep,
) -> SuccessResponse[None]:
    await service.deactivate_member(ref_id, open_ref_id(data.user_ref_id)[0], actor_id=actor.id)
    await session.commit()
    return success_response(request, None)


@router.delete("/{ref_id}/members/{user_ref_id}", response_model=SuccessResponse[None])
async def remove_member(
    request: Request,
    ref_id: str,
    user_ref_id: str,
    actor: GroupAdmin,
    service: GroupServiceDep,
    session: SessionDep,
) -> SuccessResponse[None]:
    await service.remove_member(ref_id, open_ref_id(user_ref_id)[0], actor_id=actor.id)
    await session.commit()
    return success_response(request, None, code=204)
