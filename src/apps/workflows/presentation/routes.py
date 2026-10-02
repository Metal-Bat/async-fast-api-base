"""Permission-protected workflow authoring and publication endpoints."""

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request

from apps.step_types.application.registry import get_registry
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphSnapshot,
    GraphValidationResult,
    WorkflowCreateDTO,
    WorkflowDTO,
    WorkflowGrantDTO,
    WorkflowGrantViewDTO,
    WorkflowQuery,
    WorkflowVersionCreateDTO,
    WorkflowVersionDTO,
    WorkflowVersionQuery,
    WorkflowVersionUpdateDTO,
)
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from core.deps import SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import create_ref_id, open_ref_id
from utils.base_schema import response_schema
from utils.pagination import Page, paginate_entities
from utils.presenter import PageResponse, SuccessResponse, page_response, success_response

router = APIRouter(prefix="/workflows", tags=["workflows"], responses=response_schema())
versions_router = APIRouter(
    prefix="/workflow-versions", tags=["workflow-versions"], responses=response_schema()
)
WorkflowAdmin = Annotated[UserEntity, Depends(RequirePermission("workflows.manage"))]


def workflow_dto(row: WorkflowDefinitionEntity) -> WorkflowDTO:
    return WorkflowDTO(
        ref_id=create_ref_id(row.id, row.version),
        code=row.code,
        name=row.name,
        access_mode=cast(Any, row.access_mode),
        is_active=row.is_active,
        created_at=row.created_at,
    )


def version_dto(row: WorkflowVersionEntity) -> WorkflowVersionDTO:
    return WorkflowVersionDTO(
        template_source=row.template_source,
        ref_id=create_ref_id(row.id, row.version),
        workflow_ref_id=create_ref_id(row.workflow_definition_id, 1),
        number=row.number,
        status=row.status,
        default_priority=row.default_priority,
        graph_checksum=row.graph_checksum,
        published_at=row.published_at,
        published_by_ref_id=create_ref_id(row.published_by_user_id, 1)
        if row.published_by_user_id
        else None,
    )


@router.post(
    "/validate",
    response_model=SuccessResponse[GraphValidationResult],
    summary="Validate a workflow graph",
    description="Checks step types, bindings, reusable subprocess interfaces and pinned child calls. The caller needs workflows.manage; this preview has no parent version identity. Save and publication recheck dependencies and self-reference.",
)
async def validate_graph(
    request: Request, graph: GraphSnapshot, actor: WorkflowAdmin, session: SessionDep
):
    return success_response(
        request, await WorkflowService(session, get_registry()).validate_graph(graph, actor.id)
    )


@router.post("/search", response_model=PageResponse[Page[WorkflowDTO]])
async def search_workflows(
    request: Request, query: WorkflowQuery, _: WorkflowAdmin, session: SessionDep
):
    page = await paginate_entities(session, WorkflowDefinitionEntity, query)
    return page_response(
        request,
        Page[WorkflowDTO](
            items=[workflow_dto(row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@router.post("/report", response_model=PageResponse[Page[WorkflowDTO]])
async def report_workflows(
    request: Request, query: WorkflowQuery, actor: WorkflowAdmin, session: SessionDep
):
    return await search_workflows(request, query, actor, session)


@router.post("", response_model=SuccessResponse[WorkflowDTO], status_code=201)
async def create_workflow(
    request: Request, data: WorkflowCreateDTO, actor: WorkflowAdmin, session: SessionDep
):
    row = await WorkflowService(session, get_registry()).create(data, actor.id)
    await session.commit()
    return success_response(request, workflow_dto(row), code=201)


@router.get("/{ref_id}", response_model=SuccessResponse[WorkflowDTO])
async def get_workflow(request: Request, ref_id: str, _: WorkflowAdmin, session: SessionDep):
    return success_response(
        request, workflow_dto(await WorkflowService(session, get_registry()).get(ref_id))
    )


@router.put("/{ref_id}", response_model=SuccessResponse[WorkflowDTO])
async def update_workflow(
    request: Request, ref_id: str, data: WorkflowCreateDTO, _: WorkflowAdmin, session: SessionDep
):
    row = await WorkflowService(session, get_registry()).update(ref_id, data)
    await session.commit()
    return success_response(request, workflow_dto(row))


@router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete_workflow(request: Request, ref_id: str, _: WorkflowAdmin, session: SessionDep):
    await WorkflowService(session, get_registry()).delete(ref_id)
    await session.commit()
    return success_response(request, None)


@router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def workflow_history(
    request: Request, ref_id: str, query: HistoryQuery, _: WorkflowAdmin, session: SessionDep
):
    await WorkflowService(session, get_registry()).get(ref_id)
    return page_response(
        request,
        await HistoryService.for_entity(session, "workflow_definition").list(
            query, open_ref_id(ref_id)[0]
        ),
    )


@router.post(
    "/{ref_id}/grants", response_model=SuccessResponse[WorkflowGrantViewDTO], status_code=201
)
async def add_grant(
    request: Request, ref_id: str, data: WorkflowGrantDTO, actor: WorkflowAdmin, session: SessionDep
):
    row = await WorkflowService(session, get_registry()).add_grant(ref_id, data, actor.id)
    await session.commit()
    return success_response(
        request,
        WorkflowGrantViewDTO(
            ref_id=create_ref_id(row.id, row.version),
            workflow_ref_id=ref_id,
            user_ref_id=data.user_ref_id,
            work_group_ref_id=data.work_group_ref_id,
            can_view=row.can_view,
            can_start=row.can_start,
        ),
        code=201,
    )


@router.delete("/{ref_id}/grants/{grant_ref_id}", response_model=SuccessResponse[None])
async def remove_grant(
    request: Request,
    ref_id: str,
    grant_ref_id: str,
    actor: WorkflowAdmin,
    session: SessionDep,
):
    await WorkflowService(session, get_registry()).remove_grant(ref_id, grant_ref_id, actor.id)
    await session.commit()
    return success_response(request, None)


@versions_router.post("/search", response_model=PageResponse[Page[WorkflowVersionDTO]])
async def search_versions(
    request: Request, query: WorkflowVersionQuery, _: WorkflowAdmin, session: SessionDep
):
    page = await paginate_entities(
        session,
        WorkflowVersionEntity,
        query,
        criteria=(
            WorkflowVersionEntity.workflow_definition_id == open_ref_id(query.workflow_ref_id)[0],
        ),
    )
    return page_response(
        request,
        Page[WorkflowVersionDTO](
            items=[version_dto(row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@versions_router.post("/report", response_model=PageResponse[Page[WorkflowVersionDTO]])
async def report_versions(
    request: Request, query: WorkflowVersionQuery, actor: WorkflowAdmin, session: SessionDep
):
    return await search_versions(request, query, actor, session)


@versions_router.post("", response_model=SuccessResponse[WorkflowVersionDTO], status_code=201)
async def create_version(
    request: Request, data: WorkflowVersionCreateDTO, _: WorkflowAdmin, session: SessionDep
):
    row = await WorkflowService(session, get_registry()).create_version(data)
    await session.commit()
    return success_response(request, version_dto(row), code=201)


@versions_router.get("/{ref_id}", response_model=SuccessResponse[WorkflowVersionDTO])
async def get_version(request: Request, ref_id: str, _: WorkflowAdmin, session: SessionDep):
    return success_response(
        request, version_dto(await WorkflowService(session, get_registry()).get_version(ref_id))
    )


@versions_router.put("/{ref_id}", response_model=SuccessResponse[WorkflowVersionDTO])
async def update_version(
    request: Request,
    ref_id: str,
    data: WorkflowVersionUpdateDTO,
    _: WorkflowAdmin,
    session: SessionDep,
):
    row = await WorkflowService(session, get_registry()).update_version(ref_id, data)
    await session.commit()
    return success_response(request, version_dto(row))


@versions_router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete_version(request: Request, ref_id: str, _: WorkflowAdmin, session: SessionDep):
    await WorkflowService(session, get_registry()).delete_version(ref_id)
    await session.commit()
    return success_response(request, None)


@versions_router.get(
    "/{ref_id}/graph",
    response_model=SuccessResponse[GraphSnapshot],
    summary="Read a pinned workflow graph",
    description="Returns the exact saved graph, including its optional reusable subprocess interface and call pins. Requires workflows.manage.",
)
async def get_graph(request: Request, ref_id: str, _: WorkflowAdmin, session: SessionDep):
    service = WorkflowService(session, get_registry())
    row = await service.get_version(ref_id)
    return success_response(request, await service.snapshot(row.id))


@versions_router.put(
    "/{ref_id}/graph",
    response_model=SuccessResponse[WorkflowVersionDTO],
    summary="Replace a draft workflow graph",
    description="Validates and atomically replaces a draft graph. Subprocess calls require start access to an active published child version, typed input mappings and an explicit failure route. Stale or published versions cannot be changed.",
)
async def replace_graph(
    request: Request, ref_id: str, graph: GraphSnapshot, actor: WorkflowAdmin, session: SessionDep
):
    row = await WorkflowService(session, get_registry()).replace_graph(ref_id, graph, actor.id)
    await session.commit()
    return success_response(request, version_dto(row))


@versions_router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def version_history(
    request: Request, ref_id: str, query: HistoryQuery, _: WorkflowAdmin, session: SessionDep
):
    await WorkflowService(session, get_registry()).get_version(ref_id)
    return page_response(
        request,
        await HistoryService.for_entity(session, "workflow_version").list(
            query, open_ref_id(ref_id)[0]
        ),
    )


@versions_router.post(
    "/{ref_id}/publish",
    response_model=SuccessResponse[WorkflowVersionDTO],
    summary="Publish a workflow version",
    description="Locks and revalidates draft dependencies before making the graph immutable. A published subprocess call pins the exact child version for durable execution.",
)
async def publish_version(request: Request, ref_id: str, actor: WorkflowAdmin, session: SessionDep):
    row = await WorkflowService(session, get_registry()).publish(ref_id, actor.id)
    await session.commit()
    return success_response(request, version_dto(row))


@versions_router.post("/{ref_id}/retire", response_model=SuccessResponse[WorkflowVersionDTO])
async def retire_version(request: Request, ref_id: str, _: WorkflowAdmin, session: SessionDep):
    row = await WorkflowService(session, get_registry()).retire(ref_id)
    await session.commit()
    return success_response(request, version_dto(row))
