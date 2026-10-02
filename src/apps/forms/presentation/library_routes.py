"""Permissioned CRUD, history and lifecycle routes for authored form reuse."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from apps.forms.application.library import LibraryService
from apps.forms.domain.library import (
    LibraryCreate,
    LibraryDTO,
    LibraryGrantCreate,
    LibraryGrantDTO,
    LibraryKind,
    LibraryQuery,
    LibraryVersionCreate,
    LibraryVersionDTO,
    LibraryVersionQuery,
    LibraryVersionUpdate,
)
from apps.forms.domain.library_entity import ComponentEntity, DataTypeEntity
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.deps import SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import create_ref_id, open_ref_id
from utils.base_schema import response_schema
from utils.pagination import Page
from utils.presenter import PageResponse, SuccessResponse, page_response, success_response

LibraryAdmin = Annotated[UserEntity, Depends(RequirePermission("forms.manage"))]


def _definition_dto(row: ComponentEntity | DataTypeEntity) -> LibraryDTO:
    return LibraryDTO(
        ref_id=create_ref_id(row.id, row.version),
        code=row.code,
        name=row.name,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def _routers(kind: LibraryKind, noun: str) -> tuple[APIRouter, APIRouter]:
    roots = APIRouter(prefix=f"/form-{noun}", tags=[f"form-{noun}"], responses=response_schema())
    versions = APIRouter(
        prefix=f"/form-{noun[:-1]}-versions",
        tags=[f"form-{noun[:-1]}-versions"],
        responses=response_schema(),
    )

    # Separate roots retain the standard subject-based CRUD/history route shape.
    @roots.post(
        "/search",
        response_model=PageResponse[Page[LibraryDTO]],
        description="Requires forms.manage. Search only owned or currently granted authored definitions; results are paginated before presentation.",
    )
    async def search(
        request: Request, query: LibraryQuery, actor: LibraryAdmin, session: SessionDep
    ):
        return page_response(
            request, await LibraryService(session).search_definitions(kind, query, actor)
        )

    @roots.get("/{ref_id}", response_model=SuccessResponse[LibraryDTO])
    async def detail(request: Request, ref_id: str, actor: LibraryAdmin, session: SessionDep):
        return success_response(
            request, _definition_dto(await LibraryService(session).definition(kind, ref_id, actor))
        )

    @roots.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
    async def history(
        request: Request, ref_id: str, query: HistoryQuery, actor: LibraryAdmin, session: SessionDep
    ):
        await LibraryService(session).definition(kind, ref_id, actor)
        return page_response(
            request,
            await HistoryService.for_entity(session, f"form_{noun[:-1].replace('-', '_')}").list(
                query, open_ref_id(ref_id)[0]
            ),
        )

    @roots.post("/report", response_model=PageResponse[Page[LibraryDTO]])
    async def report(
        request: Request, query: LibraryQuery, actor: LibraryAdmin, session: SessionDep
    ):
        return await search(request, query, actor, session)

    @roots.post("", response_model=SuccessResponse[LibraryDTO], status_code=201)
    async def create(
        request: Request, data: LibraryCreate, actor: LibraryAdmin, session: SessionDep
    ):
        row = await LibraryService(session).create_definition(kind, data, actor)
        await session.commit()
        return success_response(request, _definition_dto(row), code=201)

    @roots.put("/{ref_id}", response_model=SuccessResponse[LibraryDTO])
    async def update(
        request: Request, ref_id: str, data: LibraryCreate, actor: LibraryAdmin, session: SessionDep
    ):
        row = await LibraryService(session).update_definition(kind, ref_id, data, actor)
        await session.commit()
        return success_response(request, _definition_dto(row))

    @roots.delete("/{ref_id}", response_model=SuccessResponse[None])
    async def delete(request: Request, ref_id: str, actor: LibraryAdmin, session: SessionDep):
        await LibraryService(session).delete_definition(kind, ref_id, actor)
        await session.commit()
        return success_response(request, None)

    @roots.post(
        "/{ref_id}/grants",
        response_model=SuccessResponse[LibraryGrantDTO],
        status_code=201,
        description="Owner or superuser may grant current use to one user or active group. The target ref_id must be current. Grants never authorize editing the library definition.",
    )
    async def grant(
        request: Request,
        ref_id: str,
        data: LibraryGrantCreate,
        actor: LibraryAdmin,
        session: SessionDep,
    ):
        row = await LibraryService(session).grant(kind, ref_id, data, actor)
        await session.commit()
        return success_response(
            request,
            LibraryGrantDTO(
                ref_id=create_ref_id(row.id, row.version),
                user_ref_id=data.user_ref_id,
                work_group_ref_id=data.work_group_ref_id,
                can_use=True,
            ),
            code=201,
        )

    @roots.delete(
        "/{ref_id}/grants/{grant_ref_id}",
        response_model=SuccessResponse[None],
        description="Owner or superuser revokes current use. New resolution rejects this grant immediately; published resolved form snapshots remain immutable.",
    )
    async def revoke_grant(
        request: Request, ref_id: str, grant_ref_id: str, actor: LibraryAdmin, session: SessionDep
    ):
        root = await LibraryService(session).definition(kind, ref_id, actor, update=True)
        grant_id, _ = open_ref_id(grant_ref_id)
        from apps.forms.domain.library_entity import LibraryGrantEntity

        row = await session.get(LibraryGrantEntity, grant_id)
        if row is None or (row.component_id or row.data_type_id) != root.id:
            from utils.exceptions import NotFoundException

            raise NotFoundException("Library grant not found")
        await LibraryService(session).revoke_grant(grant_ref_id, actor)
        await session.commit()
        return success_response(request, None)

    @versions.post("/search", response_model=PageResponse[Page[LibraryVersionDTO]])
    async def search_versions(
        request: Request, query: LibraryVersionQuery, actor: LibraryAdmin, session: SessionDep
    ):
        return page_response(
            request, await LibraryService(session).search_versions(kind, query, actor)
        )

    @versions.get("/{ref_id}", response_model=SuccessResponse[LibraryVersionDTO])
    async def detail_version(
        request: Request, ref_id: str, actor: LibraryAdmin, session: SessionDep
    ):
        row = await LibraryService(session).version(kind, ref_id, actor)
        return success_response(request, LibraryService.version_dto(row))

    @versions.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
    async def history_version(
        request: Request, ref_id: str, query: HistoryQuery, actor: LibraryAdmin, session: SessionDep
    ):
        await LibraryService(session).version(kind, ref_id, actor)
        return page_response(
            request,
            await HistoryService.for_entity(
                session, f"form_{noun[:-1].replace('-', '_')}_version"
            ).list(query, open_ref_id(ref_id)[0]),
        )

    @versions.post("/report", response_model=PageResponse[Page[LibraryVersionDTO]])
    async def report_versions(
        request: Request, query: LibraryVersionQuery, actor: LibraryAdmin, session: SessionDep
    ):
        return await search_versions(request, query, actor, session)

    @versions.post("", response_model=SuccessResponse[LibraryVersionDTO], status_code=201)
    async def create_version(
        request: Request, data: LibraryVersionCreate, actor: LibraryAdmin, session: SessionDep
    ):
        row = await LibraryService(session).create_version(kind, data, actor)
        await session.commit()
        return success_response(request, LibraryService.version_dto(row), code=201)

    @versions.put("/{ref_id}", response_model=SuccessResponse[LibraryVersionDTO])
    async def update_version(
        request: Request,
        ref_id: str,
        data: LibraryVersionUpdate,
        actor: LibraryAdmin,
        session: SessionDep,
    ):
        row = await LibraryService(session).update_version(kind, ref_id, data.document, actor)
        await session.commit()
        return success_response(request, LibraryService.version_dto(row))

    @versions.delete("/{ref_id}", response_model=SuccessResponse[None])
    async def delete_version(
        request: Request, ref_id: str, actor: LibraryAdmin, session: SessionDep
    ):
        await LibraryService(session).delete_version(kind, ref_id, actor)
        await session.commit()
        return success_response(request, None)

    @versions.post(
        "/{ref_id}/publish",
        response_model=SuccessResponse[LibraryVersionDTO],
        description="Requires forms.manage and owner access. Locks the current draft and pins resolved exact dependencies, catalog and checksum; missing, retired or inaccessible dependencies fail.",
    )
    async def publish(request: Request, ref_id: str, actor: LibraryAdmin, session: SessionDep):
        row = await LibraryService(session).publish(kind, ref_id, actor)
        await session.commit()
        return success_response(request, LibraryService.version_dto(row))

    @versions.post(
        "/{ref_id}/retire",
        response_model=SuccessResponse[LibraryVersionDTO],
        description="Requires forms.manage and owner access. Retirement blocks new references; existing published form snapshots remain pinned.",
    )
    async def retire(request: Request, ref_id: str, actor: LibraryAdmin, session: SessionDep):
        row = await LibraryService(session).retire(kind, ref_id, actor)
        await session.commit()
        return success_response(request, LibraryService.version_dto(row))

    return roots, versions


component_router, component_versions_router = _routers("component", "components")
data_type_router, data_type_versions_router = _routers("data_type", "data-types")
