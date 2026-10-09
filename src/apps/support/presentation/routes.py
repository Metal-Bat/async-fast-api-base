"""Private support projection and safe bounded client intake."""

from uuid import UUID

from fastapi import APIRouter, Request, Response

from apps.support.application.recorder import CLIENT_CODES, record_failure
from apps.support.application.service import IncidentService
from apps.support.domain.dto import (
    ClientFailure,
    IncidentCommand,
    IncidentDTO,
    IncidentHistoryDTO,
    IncidentQuery,
    SupportReceipt,
)
from core.deps import CurrentUser, SessionDep
from core.i18n import _
from core.ref_id import create_ref_id
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.pagination import Page, PageRequest
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    private_no_store,
    success_response,
)

DESCRIPTION = _(
    "Support incidents require the current support.incidents.manage capability or superuser authority. "
    "Possession of a support_ref grants no access. Search/report apply live records and thirty-day "
    "retention before count and paging (size 1–100). Safe fields contain category, numeric public "
    "error code, registered operation, episode state/count and timestamps; no body, stack, prompt, "
    "credential or provider message is stored or returned. Identical operation episodes coalesce "
    "for one day, count is capped at 1000000 and the last 100 correlation identities deduplicate "
    "replay. A resolved recurrence starts a new episode. Acknowledge requires OPEN; resolve "
    "accepts OPEN or ACKNOWLEDGED. Both require the current revision ref and audit the transition. "
    "A stale or invalid transition conflicts 409; outsider is 403, absent/expired is 404. "
    "History returns at most 1000 safe state transitions through page/size, not diagnostic snapshots. "
    "Report aliases search. Failure persistence uses an independent transaction after business "
    "rollback; a sink outage returns support_persisted=false with correlation only. No recursive "
    "alert: one bounded MAP-13 fanout per episode, excluding notification failures. Private no-store."
)
CLIENT_DESCRIPTION = _(
    "Authenticated safe client failure intake. Only screen_key from calendar/work_items/requests/"
    "designer/reports/preferences/support, build 1–80 ASCII version characters, one of "
    "client.render_failed/client.network_failed/client.unexpected_error and a UUID request_id are "
    "accepted; unknown fields, text, HTML, stack and arbitrary error codes are rejected 422. "
    "The actor comes from authentication. Ten new reports per actor per UTC calendar minute, serialized "
    "on the user; replay among the last 100 episode correlations does not increment. Excess is 429. "
    "The returned support_ref is a correlation identity, never an authorization capability. "
    "persisted=false and support_ref=null explicitly report sink failure. No business operation "
    "is executed. Private no-store, existing envelope and en/fa messages."
)
router = APIRouter(prefix="/support", tags=["support-incidents"], responses=response_schema())


@router.post(
    "/incidents/report",
    response_model=PageResponse[Page[IncidentDTO]],
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
@router.post(
    "/incidents/search",
    response_model=PageResponse[Page[IncidentDTO]],
    summary=_("Search support incidents"),
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def search(
    request: Request,
    data: IncidentQuery,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> PageResponse[Page[IncidentDTO]]:
    private_no_store(response)
    return page_response(request, await IncidentService(session).search(data, actor))


@router.get(
    "/incidents/{ref_id}",
    response_model=SuccessResponse[IncidentDTO],
    summary=_("Read a support incident"),
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def detail(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
) -> SuccessResponse[IncidentDTO]:
    service = IncidentService(session)
    private_no_store(response)
    return success_response(request, service.dto(await service.get(ref_id, actor)))


@router.get(
    "/incidents/by-support/{support_ref}",
    response_model=SuccessResponse[IncidentDTO],
    summary=_("Resolve an authorized support correlation"),
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def by_support(
    request: Request, support_ref: UUID, response: Response, actor: CurrentUser, session: SessionDep
) -> SuccessResponse[IncidentDTO]:
    service = IncidentService(session)
    private_no_store(response)
    return success_response(
        request, service.dto(await service.get(create_ref_id(support_ref, 0), actor))
    )


@router.post(
    "/incidents/{ref_id}/history",
    response_model=PageResponse[Page[IncidentHistoryDTO]],
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def history(
    request: Request,
    ref_id: str,
    data: PageRequest,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> PageResponse[Page[IncidentHistoryDTO]]:
    private_no_store(response)
    return page_response(request, await IncidentService(session).history(ref_id, actor, data))


@router.post(
    "/incidents/{ref_id}/acknowledge",
    response_model=SuccessResponse[IncidentDTO],
    summary=_("Acknowledge a support incident"),
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def acknowledge(
    request: Request,
    ref_id: str,
    data: IncidentCommand,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[IncidentDTO]:
    result = await IncidentService(session).transition(ref_id, actor, "ACKNOWLEDGED")
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@router.post(
    "/incidents/{ref_id}/resolve",
    response_model=SuccessResponse[IncidentDTO],
    summary=_("Resolve a support incident"),
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def resolve(
    request: Request,
    ref_id: str,
    data: IncidentCommand,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[IncidentDTO]:
    result = await IncidentService(session).transition(ref_id, actor, "RESOLVED")
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@router.post(
    "/client-failures",
    response_model=SuccessResponse[SupportReceipt],
    summary=_("Record a safe client failure"),
    description=CLIENT_DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def client_failure(
    request: Request, data: ClientFailure, response: Response, actor: CurrentUser
) -> SuccessResponse[SupportReceipt]:
    identity = await record_failure(
        category="client",
        error_code=CLIENT_CODES[data.error_code],
        operation=data.screen_key + ":" + data.error_code,
        request_id=data.request_id,
        actor_id=actor.id,
        build=data.build,
    )
    private_no_store(response)
    return success_response(
        request, SupportReceipt(persisted=identity is not None, support_ref=identity)
    )
