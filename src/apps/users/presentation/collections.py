"""Self-owned view and favorite CRUD; read/apply commands never execute a target operation."""

from fastapi import APIRouter, Request, Response

from apps.users.application.personal_collections import PersonalCollectionsService
from apps.users.domain.saved_views import (
    AppliedView,
    DefaultCommand,
    FavoriteDTO,
    FavoriteInput,
    PersonalHistoryDTO,
    PersonalHistoryQuery,
    PersonalItemQuery,
    SavedViewDTO,
    SavedViewInput,
)
from core.deps import CurrentUser, SessionDep
from core.i18n import _
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.pagination import Page
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    private_no_store,
    success_response,
)

_VIEWS = _(
    "Self-only saved list presets for forms, workflows, business_requests and work_items. "
    "Current live actor and list permission are checked on every read/apply. Creation and full "
    "PUT use schema_version=1, name 1–120, command_key 1–128, an at most 8 KiB validated query, "
    "up to 20 filters/10 sorts, distinct allowlisted columns and page_size 1–100. Page offsets, "
    "result bodies, actor/privilege fields, reference-valued filters and unknown fields are rejected. "
    "100 live views per scope; unique name per self/scope. Creation keys bind the original payload; "
    "a changed replay conflicts 409. PUT is a full replacement and requires the current path ref; "
    "scope is immutable and the last identical update-key replay is safe. Default selection is "
    "explicit, serializes on the user and preserves exactly one default per scope. GET/search "
    "preserve an incompatible original preset with compatible=false; apply then returns no query, "
    "never a broadened query. Compatible apply returns page=1 and the stored size but executes no "
    "search. DELETE is idempotent for the same owned item, including after permission revocation. "
    "Wrong owner/missing is non-disclosing 404; stale write is 409, invalid contract is 422. "
    "History returns only safe self metadata, not private filters or historical identities. "
    "Report aliases search, not an archive job. Private no-store envelopes; no sharing or cache."
)
_FAVORITES = _(
    "Self-only favorites for the exact resource-link kind allowlist. Create accepts kind and "
    "current target ref_id, authorizes through its existing owner and stores canonical UUID "
    "identity, never a revision reference or target label. Repeated creation converges to one "
    "favorite; recreating an explicitly removed favorite restores that personal item only. "
    "At most 100 per kind and 500 live favorites per user. Search resolves current authorization "
    "and live targets before paging/count; forbidden/deleted targets are omitted without titles. "
    "Version favorites remain pinned to the named version. Possession grants no authority. "
    "Detail rechecks target permission; history returns only safe metadata. DELETE accepts the "
    "favorite's current ref, remains available after target revocation and never deletes the "
    "target. Wrong owner/missing is 404; stale delete is 409. Work-item favorites continue using "
    "the existing work-item personal pin state and are not duplicated here. Report aliases "
    "search; no archive generation, sharing, public URL or shared cache. Private no-store envelopes."
)
views = APIRouter(prefix="/me/saved-views", tags=["saved-views"], responses=response_schema())
favorites = APIRouter(prefix="/me/favorites", tags=["favorites"], responses=response_schema())


@views.post(
    "/report",
    response_model=PageResponse[Page[SavedViewDTO]],
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
@views.post(
    "/search",
    response_model=PageResponse[Page[SavedViewDTO]],
    summary=_("Search private saved views"),
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def search_views(
    request: Request,
    data: PersonalItemQuery,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> PageResponse[Page[SavedViewDTO]]:
    private_no_store(response)
    return page_response(
        request, await PersonalCollectionsService(session).search_views(actor, data)
    )


@views.post(
    "",
    response_model=SuccessResponse[SavedViewDTO],
    summary=_("Create a private saved view"),
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def create_view(
    request: Request,
    data: SavedViewInput,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[SavedViewDTO]:
    result = await PersonalCollectionsService(session).create_view(actor, data)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@views.get(
    "/{ref_id}",
    response_model=SuccessResponse[SavedViewDTO],
    summary=_("Read a private saved view"),
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def read_view(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
) -> SuccessResponse[SavedViewDTO]:
    private_no_store(response)
    return success_response(
        request, await PersonalCollectionsService(session).get_view(actor, ref_id)
    )


@views.put(
    "/{ref_id}",
    response_model=SuccessResponse[SavedViewDTO],
    summary=_("Replace a private saved view"),
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def update_view(
    request: Request,
    ref_id: str,
    data: SavedViewInput,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[SavedViewDTO]:
    result = await PersonalCollectionsService(session).update_view(actor, ref_id, data)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@views.post(
    "/{ref_id}/default",
    response_model=SuccessResponse[SavedViewDTO],
    summary=_("Select the personal default view"),
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def default_view(
    request: Request,
    ref_id: str,
    data: DefaultCommand,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[SavedViewDTO]:
    result = await PersonalCollectionsService(session).set_default(actor, ref_id)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@views.post(
    "/{ref_id}/apply",
    response_model=SuccessResponse[AppliedView],
    summary=_("Resolve a saved view without executing its query"),
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def apply_view(
    request: Request,
    ref_id: str,
    data: DefaultCommand,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[AppliedView]:
    private_no_store(response)
    return success_response(
        request, await PersonalCollectionsService(session).apply_view(actor, ref_id)
    )


@views.delete(
    "/{ref_id}",
    response_model=SuccessResponse[None],
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def delete_view(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
) -> SuccessResponse[None]:
    await PersonalCollectionsService(session).delete(actor, ref_id, "view")
    await session.commit()
    private_no_store(response)
    return success_response(request, None, code=204)


@views.post(
    "/{ref_id}/history",
    response_model=PageResponse[Page[PersonalHistoryDTO]],
    description=_VIEWS,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def view_history(
    request: Request,
    ref_id: str,
    data: PersonalHistoryQuery,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> PageResponse[Page[PersonalHistoryDTO]]:
    private_no_store(response)
    return page_response(
        request, await PersonalCollectionsService(session).history(actor, ref_id, "view", data)
    )


@favorites.post(
    "/report",
    response_model=PageResponse[Page[FavoriteDTO]],
    description=_FAVORITES,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
@favorites.post(
    "/search",
    response_model=PageResponse[Page[FavoriteDTO]],
    summary=_("Search private favorites"),
    description=_FAVORITES,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def search_favorites(
    request: Request,
    data: PersonalItemQuery,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> PageResponse[Page[FavoriteDTO]]:
    private_no_store(response)
    return page_response(
        request, await PersonalCollectionsService(session).search_favorites(actor, data)
    )


@favorites.post(
    "",
    response_model=SuccessResponse[FavoriteDTO],
    summary=_("Create an authorized private favorite"),
    description=_FAVORITES,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def create_favorite(
    request: Request,
    data: FavoriteInput,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[FavoriteDTO]:
    result = await PersonalCollectionsService(session).create_favorite(actor, data)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@favorites.get(
    "/{ref_id}",
    response_model=SuccessResponse[FavoriteDTO],
    summary=_("Read an authorized private favorite"),
    description=_FAVORITES,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def read_favorite(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
) -> SuccessResponse[FavoriteDTO]:
    private_no_store(response)
    return success_response(
        request, await PersonalCollectionsService(session).get_favorite(actor, ref_id)
    )


@favorites.delete(
    "/{ref_id}",
    response_model=SuccessResponse[None],
    description=_FAVORITES,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def delete_favorite(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
) -> SuccessResponse[None]:
    await PersonalCollectionsService(session).delete(actor, ref_id, "favorite")
    await session.commit()
    private_no_store(response)
    return success_response(request, None, code=204)


@favorites.post(
    "/{ref_id}/history",
    response_model=PageResponse[Page[PersonalHistoryDTO]],
    description=_FAVORITES,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def favorite_history(
    request: Request,
    ref_id: str,
    data: PersonalHistoryQuery,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> PageResponse[Page[PersonalHistoryDTO]]:
    private_no_store(response)
    return page_response(
        request, await PersonalCollectionsService(session).history(actor, ref_id, "favorite", data)
    )
