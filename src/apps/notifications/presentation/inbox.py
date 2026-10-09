"""Private unified inbox alongside unchanged case-only legacy serializers."""

from fastapi import APIRouter, Request, Response

from apps.notifications.application.inbox import InboxService
from apps.notifications.domain.inbox import InboxDTO, InboxQuery, ReadCommand, UnreadDTO
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

router = APIRouter(prefix="/inbox", tags=["inbox"], responses=response_schema())
CONTRACT = _(
    "Authenticated recipient-only unified inbox version 1. Case, work_item, ai_approval, report and account destinations resolve current owner-authorized references on every read. Calendar/support/operation targets are reserved and unavailable until their producers exist. An unavailable, deleted, revoked, expired or cancelled target exposes no private subject, content or reference. Stored labels never confer authority. Search is bounded and deterministic with existing filters/order/page/size plus unread=true/false; report is the same paginated search, not a queued archive. Unread totals count live ACTIVE unread inbox rows, including redacted unavailable destinations. Mark-read changes only read metadata, requires a current optimistic ref (409 when stale), and never decides or acts on a workflow. Non-owned refs fail 403; missing/deleted refs fail 404. Null read bodies are rejected; actions accept an empty object. UTC timestamps; en/fa template locale is chosen when staged with en fallback. Private no-store success/page envelopes, existing 401/403/404/409/422 errors. Refresh refs from mutation responses. Optional email defaults off; mandatory notices ignore optional opt-out. No delivery is performed by these reads."
)


@router.post(
    "/search",
    response_model=PageResponse[Page[InboxDTO]],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Search unified notifications"),
    description=CONTRACT,
)
@router.post(
    "/report",
    response_model=PageResponse[Page[InboxDTO]],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Report unified notifications"),
    description=CONTRACT,
)
async def search(
    request: Request, query: InboxQuery, response: Response, actor: CurrentUser, session: SessionDep
):
    private_no_store(response)
    return page_response(request, await InboxService(session).inbox_search(query, actor))


@router.get(
    "/unread",
    response_model=SuccessResponse[UnreadDTO],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Read unified unread total"),
    description=CONTRACT,
)
async def unread(request: Request, response: Response, actor: CurrentUser, session: SessionDep):
    private_no_store(response)
    return success_response(
        request, UnreadDTO(total=await InboxService(session).unread_count(actor))
    )


@router.get(
    "/{ref_id}",
    response_model=SuccessResponse[InboxDTO],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Read unified notification"),
    description=CONTRACT,
)
async def detail(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
):
    service = InboxService(session)
    private_no_store(response)
    return success_response(request, await service.dto(await service.get(ref_id, actor), actor))


@router.post(
    "/{ref_id}/read",
    response_model=SuccessResponse[InboxDTO],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Mark unified notification read"),
    description=CONTRACT,
)
async def mark_read(
    request: Request,
    ref_id: str,
    data: ReadCommand,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
):
    service = InboxService(session)
    row = await service.mark_read(ref_id, actor)
    await session.commit()
    private_no_store(response)
    return success_response(request, await service.dto(row, actor))
