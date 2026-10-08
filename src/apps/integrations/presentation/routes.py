"""Connection HTTP operations with UMS and per-connection authorization."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request

from apps.integrations.application.providers import StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.data.secrets import EncryptedFileSecrets
from apps.integrations.domain.dto import (
    AIConnectionConfig,
    ConnectionConfig,
    ConnectionCreateDTO,
    ConnectionDTO,
    ConnectionGrantQuery,
    ConnectionGrantViewDTO,
    ConnectionQuery,
    ConnectionUpdateDTO,
    GrantDTO,
    SecretRotationDTO,
)
from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.base_dto import BaseDTO
from core.deps import SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import create_ref_id, open_ref_id
from core.settings import settings
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.pagination import Page
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    private_no_store,
    select_response,
    success_response,
)
from utils.select import SelectOption, SelectQuery, SelectResponseFormat

router = APIRouter(
    prefix="/integration-connections", tags=["integration-connections"], responses=response_schema()
)
ConnectionActor = Annotated[UserEntity, Depends(RequirePermission("integrations.manage"))]


def service(session: SessionDep) -> ConnectionService:
    secrets = EncryptedFileSecrets(
        settings.INTEGRATION_SECRETS_DIR,
        [key.get_secret_value().encode() for key in settings.INTEGRATION_SECRET_KEYS],
    )
    return ConnectionService(session, StatusProvider(secrets, settings.INTEGRATION_HTTP_ENDPOINTS))


ServiceDep = Annotated[ConnectionService, Depends(service)]


class GrantReferenceDTO(BaseDTO):
    ref_id: str


def connection_dto(row: IntegrationConnectionEntity) -> ConnectionDTO:
    return ConnectionDTO(
        ref_id=create_ref_id(row.id, row.version),
        code=row.code,
        name=row.name,
        provider=row.provider,
        kind=row.kind,
        non_secret_config=(
            AIConnectionConfig.model_validate(row.non_secret_config)
            if row.kind == "AI"
            else ConnectionConfig.model_validate(row.non_secret_config)
        ),
        status=row.status,
        verification_status=row.verification_status,
        created_at=row.created_at,
    )


@router.post(
    "/select",
    summary="Select usable service or notification connections",
    description="Requires workflows.manage and per-connection use access. Returns active verified connections of the requested kind; credentials are never returned. response_format=items gives the same bounded page as a plain key/value array. Pinning rechecks access and verification.",
)
async def select_connections(
    request: Request,
    kind: Literal["SERVICE", "NOTIFICATION"],
    query: SelectQuery,
    actor: Annotated[UserEntity, Depends(RequirePermission("workflows.manage"))],
    application: ServiceDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    return select_response(
        request, await application.select_for_workflow(kind, query, actor), response_format
    )


@router.post("/search", response_model=PageResponse[Page[ConnectionDTO]])
async def search(
    request: Request, query: ConnectionQuery, actor: ConnectionActor, application: ServiceDep
):
    page = await application.search(query, actor)
    return page_response(
        request,
        Page[ConnectionDTO](
            items=[connection_dto(row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@router.get("/{ref_id}", response_model=SuccessResponse[ConnectionDTO])
async def detail(request: Request, ref_id: str, actor: ConnectionActor, application: ServiceDep):
    return success_response(request, connection_dto(await application.get(ref_id, actor)))


@router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def history(
    request: Request,
    ref_id: str,
    query: HistoryQuery,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    await application.get(ref_id, actor, manage=True)
    return page_response(
        request,
        await HistoryService.for_entity(session, "integration_connection").list(
            query, open_ref_id(ref_id)[0]
        ),
    )


@router.post("/report", response_model=PageResponse[Page[ConnectionDTO]])
async def report(
    request: Request, query: ConnectionQuery, actor: ConnectionActor, application: ServiceDep
):
    return await search(request, query, actor, application)


@router.post("", response_model=SuccessResponse[ConnectionDTO], status_code=201)
async def create(
    request: Request,
    data: ConnectionCreateDTO,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    row = await application.create(data, actor)
    await session.commit()
    return success_response(request, connection_dto(row), code=201)


@router.put("/{ref_id}", response_model=SuccessResponse[ConnectionDTO])
async def update(
    request: Request,
    ref_id: str,
    data: ConnectionUpdateDTO,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    row = await application.update(ref_id, data, actor)
    await session.commit()
    return success_response(request, connection_dto(row))


@router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete(
    request: Request,
    ref_id: str,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    await application.delete(ref_id, actor)
    await session.commit()
    return success_response(request, None)


@router.post("/{ref_id}/rotate", response_model=SuccessResponse[ConnectionDTO])
async def rotate(
    request: Request,
    ref_id: str,
    data: SecretRotationDTO,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    row = await application.rotate(ref_id, data, actor)
    await session.commit()
    return success_response(request, connection_dto(row))


@router.post("/{ref_id}/verify", response_model=SuccessResponse[ConnectionDTO])
async def verify(
    request: Request,
    ref_id: str,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    row = await application.verify(ref_id, actor)
    await session.commit()
    return success_response(request, connection_dto(row))


@router.post("/{ref_id}/revoke", response_model=SuccessResponse[ConnectionDTO])
async def revoke(
    request: Request,
    ref_id: str,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    row = await application.revoke(ref_id, actor)
    await session.commit()
    return success_response(request, connection_dto(row))


@router.post(
    "/{ref_id}/grants/search",
    response_model=PageResponse[Page[ConnectionGrantViewDTO]],
    dependencies=[Depends(private_no_store)],
    summary="Read current connection grants",
    responses=PRIVATE_NO_STORE_RESPONSES,
    description="Requires integrations.manage plus per-connection manage/owner/superuser authority. Returns current nondeleted grants with opaque grant/user/group refs and can_use/can_manage; no credentials or historical reconstruction. Shared filters allow only can_use/can_manage; one-based page/size defaults 1/20, maximum size 100. Missing connections return 404; denied manage authority returns 403. Private no-store response; grant visibility does not grant use/manage capability.",
)
async def search_connection_grants(
    request: Request,
    ref_id: str,
    query: ConnectionGrantQuery,
    actor: ConnectionActor,
    application: ServiceDep,
):
    return page_response(request, await application.search_grants(ref_id, query, actor))


@router.post("/{ref_id}/grants", response_model=SuccessResponse[GrantReferenceDTO])
async def grant(
    request: Request,
    ref_id: str,
    data: GrantDTO,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    row = await application.grant(ref_id, data, actor)
    await session.commit()
    return success_response(request, GrantReferenceDTO(ref_id=create_ref_id(row.id, row.version)))


@router.delete("/{ref_id}/grants/{grant_ref_id}", response_model=SuccessResponse[None])
async def remove_grant(
    request: Request,
    ref_id: str,
    grant_ref_id: str,
    actor: ConnectionActor,
    application: ServiceDep,
    session: SessionDep,
):
    await application.remove_grant(ref_id, grant_ref_id, actor)
    await session.commit()
    return success_response(request, None)
