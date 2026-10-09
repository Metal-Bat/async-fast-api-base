"""Administrative read-only setup projection."""

from fastapi import APIRouter, Request, Response

from apps.health.setup import SetupReport, SetupService
from core.deps import CurrentUser, SessionDep
from core.i18n import _
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.exceptions import NotAllowedException
from utils.presenter import SuccessResponse, private_no_store, success_response

router = APIRouter(prefix="/setup", tags=["setup"], responses=response_schema())


@router.get(
    "/readiness",
    response_model=SuccessResponse[SetupReport],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Inspect development installation readiness"),
    description=_(
        "Requires a current superuser; ordinary administrators and requesters receive 403. Bounded read-only database facts and internal connectivity probes return ready, blocked, unknown or not_applicable. Required unknown checks prevent green overall readiness. Worker and scheduler execution remain unknown until separately verified by an explicit operator command; broker connectivity is insufficient. This read never installs roles, grants access, publishes definitions, enqueues tasks or invokes live providers. Repair keys identify owning screens; operations requires an operator. Refresh after 30 seconds and display checked_at UTC. Results contain no hosts, DSNs, credentials, user lists or raw errors. Private no-store success envelope; authenticated 401/403 errors use existing public codes."
    ),
)
async def setup_readiness(
    request: Request, response: Response, actor: CurrentUser, session: SessionDep
) -> SuccessResponse[SetupReport]:
    if not actor.is_superuser:
        raise NotAllowedException("Setup inspection requires a superuser")
    private_no_store(response)
    return success_response(request, await SetupService(session).inspect())
