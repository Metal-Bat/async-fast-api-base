"""Explicit acknowledgment commands; static frontend help remains independently renderable."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from apps.users.application.help_state import HelpStateService
from apps.users.data.help_release import load_help_release
from apps.users.domain.help_state import (
    HelpAction,
    HelpActionResult,
    HelpReleaseMetadata,
    HelpReset,
    HelpResetResult,
    HelpStatePage,
    HelpStateQuery,
)
from core.deps import CurrentUser, SessionDep
from core.i18n import _
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.presenter import SuccessResponse, private_no_store, success_response

router = APIRouter(prefix="/me/help-state", tags=["me"], responses=response_schema())
HelpReleaseDep = Annotated[HelpReleaseMetadata | None, Depends(load_help_release)]


@router.get(
    "",
    response_model=SuccessResponse[HelpStatePage],
    summary=_("Read personal multilingual help state"),
    description=_(
        "Read only this authenticated user's acknowledgment metadata with page/size bounds and optional en/fa locale filter. Ordered by help_key, revision, locale. This read records no seen or dismissal action and grants no business access. release_key is null when paired frontend metadata is unavailable. Help content remains frontend-owned and is never stored here."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def read_help_state(
    request: Request,
    response: Response,
    query: Annotated[HelpStateQuery, Query()],
    user: CurrentUser,
    session: SessionDep,
    metadata: HelpReleaseDep,
) -> SuccessResponse[HelpStatePage]:
    private_no_store(response)
    return success_response(request, await HelpStateService(session, metadata).read(user, query))


@router.post(
    "/seen",
    response_model=SuccessResponse[HelpActionResult],
    summary=_("Record an explicit help open"),
    description=_(
        "Call only after the user actually opens this help revision in the supplied locale. Ownership and timestamps are server-derived. An atomic tuple upsert preserves first_viewed_at and updates last_viewed_at; another locale/revision is independent. Missing/stale metadata returns saved=false with a compatibility reason and writes nothing. Maximum 512 records per actor; deliberate self reset frees this small state. No content, duration, form values, actor identifiers or arbitrary event payloads are accepted. Static help must still render if this save fails."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def see_help(
    request: Request,
    response: Response,
    data: HelpAction,
    user: CurrentUser,
    session: SessionDep,
    metadata: HelpReleaseDep,
) -> SuccessResponse[HelpActionResult]:
    result = await HelpStateService(session, metadata).record(user, data)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@router.post(
    "/dismiss",
    response_model=SuccessResponse[HelpActionResult],
    summary=_("Record an explicit help dismissal"),
    description=_(
        "Record a deliberate dismissal for this authenticated actor and exact frontend help key/revision/locale. Repeats preserve the first dismissed_at. Dismissing unopened help leaves viewed timestamps null; it does not pretend the content was read. Compatibility and bounded-state behavior match seen. Neither dismissal nor acknowledgment changes business permissions or workflow state."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def dismiss_help(
    request: Request,
    response: Response,
    data: HelpAction,
    user: CurrentUser,
    session: SessionDep,
    metadata: HelpReleaseDep,
) -> SuccessResponse[HelpActionResult]:
    result = await HelpStateService(session, metadata).record(user, data, dismiss=True)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@router.post(
    "/reset",
    response_model=SuccessResponse[HelpResetResult],
    summary=_("Reset only personal help state"),
    description=_(
        "Deliberately remove only the authenticated actor's help acknowledgment metadata. The body must be an empty object; actor fields are forbidden. Repeat is safe and returns zero removed records. Preferences, profiles, accounts and business data survive. This command does not restore definitions or reset an installation."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def reset_help(
    request: Request,
    response: Response,
    data: HelpReset,
    user: CurrentUser,
    session: SessionDep,
    metadata: HelpReleaseDep,
) -> SuccessResponse[HelpResetResult]:
    result = await HelpStateService(session, metadata).reset(user)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)
