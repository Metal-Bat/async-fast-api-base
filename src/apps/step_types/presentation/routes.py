"""Protected, bounded authoring of deployed step-type versions."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.dto import StepTypeQuery, StepTypeVersionDTO
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.deps import SessionDep
from utils.base_schema import response_schema
from utils.pagination import Page
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    select_response,
    success_response,
)
from utils.select import SelectOption, SelectQuery, SelectResponseFormat

router = APIRouter(prefix="/step-types", tags=["step-types"], responses=response_schema())
StepAdmin = Annotated[UserEntity, Depends(RequirePermission("workflows.manage"))]


@router.post(
    "/search",
    response_model=PageResponse[Page[StepTypeVersionDTO]],
    summary="Search deployed step type versions",
    description="Requires workflows.manage. Includes draft and historical versions; is_available is false when the exact deployed handler is missing or changed.",
)
async def search_step_types(
    request: Request, query: StepTypeQuery, _: StepAdmin, session: SessionDep
) -> PageResponse[Page[StepTypeVersionDTO]]:
    return page_response(request, await StepTypeService(session, get_registry()).search(query))


@router.get(
    "/{ref_id}",
    response_model=SuccessResponse[StepTypeVersionDTO],
    summary="Inspect one pinned step type version",
    description="Requires workflows.manage. Historical metadata remains readable if its code extension is no longer deployed.",
)
async def get_step_type(
    request: Request, ref_id: str, _: StepAdmin, session: SessionDep
) -> SuccessResponse[StepTypeVersionDTO]:
    return success_response(request, await StepTypeService(session, get_registry()).detail(ref_id))


@router.post(
    "/{ref_id}/publish",
    response_model=SuccessResponse[StepTypeVersionDTO],
    summary="Publish a reconciled step type draft",
    description="Requires workflows.manage. Only a draft whose persisted schema exactly matches deployed trusted code can be published. Published contracts are immutable.",
)
async def publish_step_type(
    request: Request, ref_id: str, _: StepAdmin, session: SessionDep
) -> SuccessResponse[StepTypeVersionDTO]:
    service = StepTypeService(session, get_registry())
    await service.publish(ref_id)
    await session.commit()
    return success_response(request, await service.detail(ref_id))


@router.post(
    "/select",
    summary="Select executable published step types",
    description="Requires workflows.manage. Returns only currently registered, matching published versions as key/value choices. response_format=items returns the same bounded page without its envelope.",
)
async def select_step_types(
    request: Request,
    query: SelectQuery,
    _: StepAdmin,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    page = await StepTypeService(session, get_registry()).search(
        StepTypeQuery(page=query.page, size=query.size, search=query.search, status="PUBLISHED"),
        available_only=True,
    )
    options = Page[SelectOption[str]](
        items=[SelectOption(key=item.ref_id, value=item.name) for item in page.items],
        page=page.page,
        size=page.size,
        total=page.total,
    )
    return select_response(request, options, response_format)
