"""Protected client identity and release authoring HTTP contracts."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from apps.clients.application.service import ClientService
from apps.clients.domain.contracts import ClientKind
from apps.clients.domain.dto import (
    ClientCreateDTO,
    ClientCreateResultDTO,
    ClientDTO,
    ClientQuery,
    ClientReleaseCreateDTO,
    ClientReleaseCreateRequestDTO,
    ClientReleaseDTO,
    ClientReleaseQuery,
    ClientUpdateDTO,
)
from apps.clients.domain.entity import ClientEntity, ClientReleaseEntity
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
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
from utils.select import SelectOption, SelectQuery, SelectResponseFormat

router = APIRouter(prefix="/clients", tags=["clients"], responses=response_schema())
releases_router = APIRouter(
    prefix="/client-releases", tags=["client-releases"], responses=response_schema()
)
ClientAdmin = Annotated[UserEntity, Depends(RequirePermission("forms.manage"))]


def client_dto(row: ClientEntity) -> ClientDTO:
    return ClientDTO(
        ref_id=create_ref_id(row.id, row.version),
        code=row.code,
        name=row.name,
        kind=cast(ClientKind, row.kind),
        platform=row.platform,
        confidential=row.secret_hash is not None,
        is_active=row.is_active,
    )


async def release_dto(row: ClientReleaseEntity, session: SessionDep) -> ClientReleaseDTO:
    client = await session.get(ClientEntity, row.client_id)
    if client is None:
        raise RuntimeError("Client release references a missing client")
    return ClientReleaseDTO(
        ref_id=create_ref_id(row.id, row.version),
        client_ref_id=create_ref_id(client.id, client.version),
        version=row.release_version,
        api_version=row.api_version,
        renderer_capabilities=row.renderer_capabilities,
        is_enabled=row.is_enabled,
    )


@router.post(
    "/search",
    response_model=PageResponse[Page[ClientDTO]],
    summary="Search registered application clients",
    description="Requires forms.manage. Client kinds are application identities; device and User-Agent hints never authorize restricted workflows.",
)
async def search_clients(request: Request, query: ClientQuery, _: ClientAdmin, session: SessionDep):
    page = await paginate_entities(session, ClientEntity, query)
    return page_response(
        request,
        Page[ClientDTO](
            items=[client_dto(row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@router.get("/{ref_id}", response_model=SuccessResponse[ClientDTO])
async def get_client(request: Request, ref_id: str, _: ClientAdmin, session: SessionDep):
    return success_response(request, client_dto(await ClientService(session).get_client(ref_id)))


@router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def client_history(
    request: Request, ref_id: str, query: HistoryQuery, _: ClientAdmin, session: SessionDep
):
    await ClientService(session).get_client(ref_id)
    return page_response(
        request,
        await HistoryService.for_entity(session, "client").list(query, open_ref_id(ref_id)[0]),
    )


@router.post("/report", response_model=PageResponse[Page[ClientDTO]])
async def report_clients(
    request: Request, query: ClientQuery, actor: ClientAdmin, session: SessionDep
):
    return await search_clients(request, query, actor, session)


@router.post(
    "",
    response_model=SuccessResponse[ClientCreateResultDTO],
    status_code=201,
    summary="Register an application client",
    description=(
        "Requires forms.manage. Registers an application/channel kind and platform. "
        "For a confidential client the random secret appears only in this response; "
        "public clients receive null and cannot satisfy restricted process starts. "
        "The client key and a registered release are presented with user credentials at login."
    ),
)
async def create_client(
    request: Request, data: ClientCreateDTO, _: ClientAdmin, session: SessionDep
):
    row, secret = await ClientService(session).create_client(data)
    await session.commit()
    return success_response(
        request, ClientCreateResultDTO(client=client_dto(row), secret=secret), code=201
    )


@router.put("/{ref_id}", response_model=SuccessResponse[ClientDTO])
async def update_client(
    request: Request, ref_id: str, data: ClientUpdateDTO, _: ClientAdmin, session: SessionDep
):
    row = await ClientService(session).update_client(ref_id, data)
    await session.commit()
    return success_response(request, client_dto(row))


@router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete_client(request: Request, ref_id: str, _: ClientAdmin, session: SessionDep):
    await ClientService(session).delete_client(ref_id)
    await session.commit()
    return success_response(request, None)


@router.post(
    "/select",
    summary="Choose active client registrations",
    description=(
        "Requires forms.manage. SelectQuery searches code and name before bounded pagination. "
        "response_format=page (default) returns the result envelope; items returns the same "
        "key/value page as an array. Keys are revision-bearing client references."
    ),
)
async def select_clients(
    request: Request,
    query: SelectQuery,
    _: ClientAdmin,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    page = await ClientService(session).select_clients(query)
    return select_response(request, page, response_format)


@router.post("/{ref_id}/rotate-secret", response_model=SuccessResponse[ClientCreateResultDTO])
async def rotate_client_secret(request: Request, ref_id: str, _: ClientAdmin, session: SessionDep):
    row, secret = await ClientService(session).rotate_secret(ref_id)
    await session.commit()
    return success_response(request, ClientCreateResultDTO(client=client_dto(row), secret=secret))


@releases_router.post("/search", response_model=PageResponse[Page[ClientReleaseDTO]])
async def search_releases(
    request: Request, query: ClientReleaseQuery, _: ClientAdmin, session: SessionDep
):
    page = await paginate_entities(
        session,
        ClientReleaseEntity,
        query,
        criteria=(ClientReleaseEntity.client_id == open_ref_id(query.client_ref_id)[0],),
    )
    return page_response(
        request,
        Page[ClientReleaseDTO](
            items=[await release_dto(row, session) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@releases_router.get("/{ref_id}", response_model=SuccessResponse[ClientReleaseDTO])
async def get_release(request: Request, ref_id: str, _: ClientAdmin, session: SessionDep):
    return success_response(
        request, await release_dto(await ClientService(session).get_release(ref_id), session)
    )


@releases_router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def release_history(
    request: Request, ref_id: str, query: HistoryQuery, _: ClientAdmin, session: SessionDep
):
    await ClientService(session).get_release(ref_id)
    return page_response(
        request,
        await HistoryService.for_entity(session, "client_release").list(
            query, open_ref_id(ref_id)[0]
        ),
    )


@releases_router.post("/report", response_model=PageResponse[Page[ClientReleaseDTO]])
async def report_releases(
    request: Request, query: ClientReleaseQuery, actor: ClientAdmin, session: SessionDep
):
    return await search_releases(request, query, actor, session)


@releases_router.post(
    "",
    response_model=SuccessResponse[ClientReleaseDTO],
    status_code=201,
    summary="Register a client release",
    description=(
        "Requires forms.manage and an active client_ref_id. version uses numeric SemVer-like "
        "major.minor[.patch][-prerelease][+build] ordering. api_version is the API contract; "
        "renderer_capabilities are unique. A release has no authentication credential by itself."
    ),
)
async def create_release(
    request: Request, data: ClientReleaseCreateRequestDTO, _: ClientAdmin, session: SessionDep
):
    service = ClientService(session)
    client = await service.get_client(data.client_ref_id)
    row = await service.create_release(
        client.id, ClientReleaseCreateDTO.model_validate(data.model_dump(exclude={"client_ref_id"}))
    )
    await session.commit()
    return success_response(request, await release_dto(row, session), code=201)


@releases_router.post(
    "/select",
    summary="Choose enabled releases for a client",
    description=(
        "Requires forms.manage and client_ref_id query parameter. SelectQuery is bounded; "
        "response_format=page (default) returns metadata, items returns the same key/value slice. "
        "Keys are revision-bearing release references."
    ),
)
async def select_releases(
    request: Request,
    query: SelectQuery,
    client_ref_id: str,
    _: ClientAdmin,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    page = await ClientService(session).select_releases(client_ref_id, query)
    return select_response(request, page, response_format)


@releases_router.post("/{ref_id}/disable", response_model=SuccessResponse[ClientReleaseDTO])
async def disable_release(request: Request, ref_id: str, _: ClientAdmin, session: SessionDep):
    row = await ClientService(session).disable_release(ref_id)
    await session.commit()
    return success_response(request, await release_dto(row, session))
