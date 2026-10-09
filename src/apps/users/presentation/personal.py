"""Self-only profile/preferences contracts; identity security stays under /auth."""

from fastapi import APIRouter, Request, Response

from apps.users.application.preferences import PersonalSettingsService
from apps.users.domain.preferences import PreferencesDTO, PreferencesPatch, ProfileDTO, ProfilePatch
from core.deps import CurrentUser, SessionDep
from core.i18n import _
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.presenter import SuccessResponse, private_no_store, success_response

router = APIRouter(prefix="/me", tags=["me"], responses=response_schema())


@router.get(
    "/preferences",
    response_model=SuccessResponse[PreferencesDTO],
    summary=_("Read personal workspace preferences"),
    description=_(
        "Read only the authenticated user's preferences. Missing settings return typed defaults and a version-zero reference without inserting a row. No other actor identifier is accepted. Returns private, no-store JSON. Authentication and user deactivation follow existing auth rules."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def read_preferences(
    request: Request, response: Response, user: CurrentUser, session: SessionDep
) -> SuccessResponse[PreferencesDTO]:
    private_no_store(response)
    return success_response(request, await PersonalSettingsService(session).read(user))


@router.patch(
    "/preferences",
    response_model=SuccessResponse[PreferencesDTO],
    summary=_("Apply personal workspace preferences"),
    description=_(
        "Atomically update self settings with the current ref_id from GET. Omitted groups and nested fields are preserved; null resets an entire supplied group to documented defaults. Nested scalar nulls and unknown keys are rejected with 422. Wrong-owner references return non-disclosing 404; stale references return 409 without applying changes. A no-op keeps the current reference. Returns a fresh reference after change. Locale supports en/fa, Gregorian calendar and valid IANA zones; settings never grant screen permissions."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def apply_preferences(
    request: Request,
    response: Response,
    data: PreferencesPatch,
    user: CurrentUser,
    session: SessionDep,
) -> SuccessResponse[PreferencesDTO]:
    result = await PersonalSettingsService(session).apply(user, data)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@router.get(
    "/profile",
    response_model=SuccessResponse[ProfileDTO],
    summary=_("Read personal profile"),
    description=_(
        "Return editable given/family names and the current owned private image reference. No public URL is returned. Contact details, passwords and sessions use the existing /auth APIs. Missing or removed image bindings resolve to null. This read does not modify preferences or media."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def read_profile(
    request: Request, response: Response, user: CurrentUser, session: SessionDep
) -> SuccessResponse[ProfileDTO]:
    private_no_store(response)
    return success_response(request, await PersonalSettingsService(session).profile(user))


@router.patch(
    "/profile",
    response_model=SuccessResponse[ProfileDTO],
    summary=_("Apply personal profile changes"),
    description=_(
        "Update only self given/family names and an owned private avatar using the current profile ref_id. Omitted fields survive; null clears a name or detaches the avatar. Upload images through the existing authenticated media image endpoint, which enforces size/type and strips metadata. An avatar reference must identify an existing live image owned by this actor; missing, stale, wrong-kind and outsider images return non-disclosing 404. Detachment preserves the private upload because it may be referenced by retained case data. Security/privilege fields are rejected. Stale profile references return 409. Returns the authoritative current profile reference."
    ),
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def apply_profile(
    request: Request, response: Response, data: ProfilePatch, user: CurrentUser, session: SessionDep
) -> SuccessResponse[ProfileDTO]:
    result = await PersonalSettingsService(session).update_profile(user, data)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)
