"""Permission-protected workflow authoring and publication endpoints."""

from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request, Response

from apps.step_types.application.registry import get_registry
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from apps.workflows.application.defaults import WorkflowDefaultsService
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.defaults import (
    LayoutResetInput,
    RestoreApplyInput,
    RestorePlan,
    RestorePreviewInput,
    RestoreResult,
)
from apps.workflows.domain.dto import (
    GraphSnapshot,
    GraphValidationResult,
    WorkflowCreateDTO,
    WorkflowDTO,
    WorkflowGrantDTO,
    WorkflowGrantQuery,
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
from core.i18n import _
from core.ref_id import create_ref_id, open_ref_id
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.pagination import Page, paginate_entities
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    private_no_store,
    success_response,
)

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
    "/{ref_id}/grants/search",
    response_model=PageResponse[Page[WorkflowGrantViewDTO]],
    dependencies=[Depends(private_no_store)],
    summary="Read current workflow access grants",
    responses=PRIVATE_NO_STORE_RESPONSES,
    description="Requires workflows.manage, matching the authoring grant-mutation boundary. Returns current nondeleted grants with current opaque workflow/grant/user/group refs and can_view/can_start. Shared filters allow only these capabilities; page/size default 1/20, maximum size 100. Does not reconstruct audit history or expose confidential assignment/configuration. Missing workflows return 404; private no-store response.",
)
async def search_workflow_grants(
    request: Request,
    ref_id: str,
    query: WorkflowGrantQuery,
    _actor: WorkflowAdmin,
    session: SessionDep,
):
    return page_response(
        request, await WorkflowService(session, get_registry()).search_grants(ref_id, query)
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
    parent = await WorkflowService(session, get_registry()).get(query.workflow_ref_id)
    page = await paginate_entities(
        session,
        WorkflowVersionEntity,
        query,
        criteria=(WorkflowVersionEntity.workflow_definition_id == parent.id,),
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


from apps.workflows.application.workspace import WorkspaceService
from apps.workflows.domain.workspace import (
    WorkflowWorkspaceDTO,
    WorkspacePromoteDTO,
    WorkspaceUpdateDTO,
)


@versions_router.get(
    "/{ref_id}/workspace",
    response_model=SuccessResponse[WorkflowWorkspaceDTO],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary="Read workflow authoring workspace / خواندن فضای طراحی",
    description="Requires workflows.manage. Returns independently revisioned WIP, stable-key layout and viewport; never an executable graph. Missing WIP starts from the current saved snapshot. / نیازمند مجوز طراحی؛ فضای کار مستقل از گراف اجرایی است.",
)
async def get_workspace(
    request: Request, response: Response, ref_id: str, _: WorkflowAdmin, session: SessionDep
):
    private_no_store(response)
    result = await WorkspaceService(WorkflowService(session, get_registry())).get(ref_id)
    return success_response(request, result)


@versions_router.put(
    "/{ref_id}/workspace",
    response_model=SuccessResponse[WorkflowWorkspaceDTO],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary="Save incomplete workflow workspace / ذخیره فضای طراحی",
    description="Requires workflows.manage and a current DRAFT workflow ref. Bounded incomplete graph/layout is accepted without execution validation. workspace_ref_id null creates once; a stale workspace or workflow ref returns 409. Save does not modify graph rows or execution pins; no automatic replay. / طراحی ناقص با نسخه مستقل ذخیره می‌شود؛ تعارض نسخه پاسخ ۴۰۹ دارد.",
)
async def save_workspace(
    request: Request,
    response: Response,
    ref_id: str,
    data: WorkspaceUpdateDTO,
    _: WorkflowAdmin,
    session: SessionDep,
):
    private_no_store(response)
    service = WorkspaceService(WorkflowService(session, get_registry()))
    await service.save(ref_id, data)
    await session.commit()
    return success_response(request, await service.get(ref_id))


@versions_router.post(
    "/{ref_id}/workspace/promote",
    response_model=SuccessResponse[WorkflowVersionDTO],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary="Promote validated workspace graph / ارتقای گراف معتبر",
    description="Requires workflows.manage, current DRAFT/workspace refs and all dependency authorizations. Validates GraphSnapshot then atomically replaces executable rows, retaining WIP/layout. 422 preserves the invalid workspace; 409 requires reconciliation. This does not publish. Publication requires the current graph to have been promoted and revalidates all dependencies. / ارتقا پس از اعتبارسنجی انجام می‌شود و انتشار دستور جداگانه است.",
)
async def promote_workspace(
    request: Request,
    response: Response,
    ref_id: str,
    data: WorkspacePromoteDTO,
    actor: WorkflowAdmin,
    session: SessionDep,
):
    private_no_store(response)
    row = await WorkspaceService(WorkflowService(session, get_registry())).promote(
        ref_id, data, actor.id
    )
    await session.commit()
    return success_response(request, version_dto(row))


@versions_router.post(
    "/{ref_id}/workspace/history",
    response_model=PageResponse[Page[HistoryRecordDTO]],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary="Read authoring workspace history / تاریخچه طراحی",
    description="Requires workflows.manage; bounded authorized audit pages include WIP changes. Not an ordinary-user runtime endpoint. / فقط برای طراح مجاز است.",
)
async def workspace_history(
    request: Request,
    response: Response,
    ref_id: str,
    query: HistoryQuery,
    _: WorkflowAdmin,
    session: SessionDep,
):
    private_no_store(response)
    service = WorkspaceService(WorkflowService(session, get_registry()))
    version = await service.workflows.get_version(ref_id)
    row = await service.row(version.id)
    if row is None:
        return page_response(
            request, Page[HistoryRecordDTO](items=[], page=query.page, size=query.size, total=0)
        )
    return page_response(
        request, await HistoryService.for_entity(session, "workflow_workspace").list(query, row.id)
    )


RESTORE_DESCRIPTION = _(
    "Requires live workflows.manage and current template visibility. Preview freezes the exact target/workspace "
    "revisions, published template checksum and symbolic reference bindings for ten minutes. An unassociated "
    "workflow requires explicit source_ref_id. Dependencies are validated through existing publication rules; "
    "blockers return no plan_token. replace_draft changes only DRAFT; successor creates a new DRAFT for any "
    "live target including PUBLISHED/RETIRED. Apply requires the reviewed token and command_key; replay returns "
    "the same result and changed-plan key reuse conflicts. Stale target/workspace, expired plan or changed "
    "dependencies conflict 409; unavailable source is 404 and invalid bindings/graph are 422. Graph/workspace "
    "and the replay receipt commit atomically. No automatic publication, request-type retargeting, form edit, "
    "execution-pin change, secret/grant reset or provider operation occurs. Existing private no-store "
    "snake_case success envelopes and en/fa localization apply."
)


@versions_router.post(
    "/{ref_id}/default-preview",
    response_model=SuccessResponse[RestorePlan],
    summary=_("Preview a workflow default restoration"),
    description=RESTORE_DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def default_preview(
    request: Request,
    ref_id: str,
    data: RestorePreviewInput,
    response: Response,
    actor: WorkflowAdmin,
    session: SessionDep,
):
    private_no_store(response)
    return success_response(
        request, await WorkflowDefaultsService(session).preview(ref_id, data, actor)
    )


@versions_router.post(
    "/{ref_id}/default-apply",
    response_model=SuccessResponse[RestoreResult],
    summary=_("Apply the reviewed workflow default"),
    description=RESTORE_DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def default_apply(
    request: Request,
    ref_id: str,
    data: RestoreApplyInput,
    response: Response,
    actor: WorkflowAdmin,
    session: SessionDep,
):
    result = await WorkflowDefaultsService(session).apply(ref_id, data, actor)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@versions_router.post(
    "/{ref_id}/layout-reset",
    response_model=SuccessResponse[WorkflowWorkspaceDTO],
    summary=_("Reset draft workspace layout"),
    description=_(
        "Requires workflows.manage and current DRAFT/workspace revisions. Clears positions, routes, collapsed nodes and viewport; preserves graph and promotion checksum. This never restores a definition, discards server graph changes, publishes or resets environment data. Local unsaved-edit discard belongs to the client. Private no-store."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def layout_reset(
    request: Request,
    ref_id: str,
    data: LayoutResetInput,
    response: Response,
    actor: WorkflowAdmin,
    session: SessionDep,
):
    result = await WorkflowDefaultsService(session).reset_layout(
        ref_id, data.workspace_ref_id, actor
    )
    await session.commit()
    private_no_store(response)
    return success_response(request, result)
