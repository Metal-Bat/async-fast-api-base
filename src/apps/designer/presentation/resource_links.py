"""Private resource lookup; owning services remain the authority for every target."""

from fastapi import APIRouter, Request, Response

from apps.designer.application.resource_links import ResourceLinkService
from apps.designer.domain.resource_links import (
    LocatorQuery,
    ResourceLink,
    ResourceReference,
    ResourceSummary,
    SelectedQuery,
)
from core.deps import CurrentUser, SessionDep
from core.i18n import _
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.presenter import SuccessResponse, private_no_store, success_response

router = APIRouter(prefix="/resource-links", tags=["designer"], responses=response_schema())
_DESCRIPTION = _(
    "Requires an authenticated live user and the target's existing read permission. "
    "Owner/grant policies are rechecked on every call; locators grant no access. "
    "Missing, deleted, forged and forbidden targets return the same safe 404 envelope. "
    "Inactive or retired readable records report available=false. A version link remains "
    "bound to that exact version, while ref_id refreshes to its current optimistic revision. "
    "Only code-owned route keys are returned, never arbitrary URLs or table names. "
    "Signing-key replacement invalidates locators. Responses use private no-store headers."
)


@router.post(
    "",
    response_model=SuccessResponse[ResourceLink],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Create an authorized stable resource link"),
    description=_DESCRIPTION,
)
async def mint_link(
    request: Request,
    data: ResourceReference,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[ResourceLink]:
    result = await ResourceLinkService(session).mint(data, actor)
    private_no_store(response)
    return success_response(request, result)


@router.post(
    "/resolve",
    response_model=SuccessResponse[ResourceLink],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Resolve a stable link to a current reference"),
    description=_DESCRIPTION,
)
async def resolve_link(
    request: Request,
    data: LocatorQuery,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[ResourceLink]:
    result = await ResourceLinkService(session).resolve(data.locator, actor)
    private_no_store(response)
    return success_response(request, result)


@router.post(
    "/selected",
    response_model=SuccessResponse[list[ResourceSummary]],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Read eligible selected values outside search pages"),
    description=_(
        "Reads at most 50 selected values in request order, independent of page or search. "
        "Uses existing selector permissions and owner policies, not detail authorization: "
        "workflow designers may read only safe user/group labels and use-granted connection labels. "
        "Forms must be actor-owned or superuser-visible; versions must be published. "
        "Selection grants no execution permission. A revoked/deleted/ineligible value fails "
        "the whole request with a safe 404, without partial titles. Unknown kinds or excess "
        "items return 422. Private no-store success envelope contains current references."
    ),
)
async def selected(
    request: Request,
    data: SelectedQuery,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[list[ResourceSummary]]:
    service = ResourceLinkService(session)
    result = [await service.summary(item, actor, selection=True) for item in data.resources]
    private_no_store(response)
    return success_response(request, result)
