"""Personal/team manual events and a read-only workflow deadline projection."""

from fastapi import APIRouter, Request, Response

from apps.calendar.application.reminders import (
    cancel_source_reminders,
    configure_work_reminders,
    read_reminders,
    responsible,
)
from apps.calendar.application.service import CalendarService
from apps.calendar.domain.dto import (
    CalendarHistoryDTO,
    CalendarInput,
    CalendarItemDTO,
    CalendarQuery,
    ReminderDTO,
    ReminderInput,
)
from core.deps import CurrentUser, SessionDep
from core.i18n import _
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
    "Authenticated Gregorian calendar. Personal events belong to their creator; a team event is "
    "visible only to current active members of its explicitly selected active work group. Only "
    "the creator can update/delete. No superuser bypass grants another person's calendar. "
    "Timed events use aware ISO-8601 instants and an IANA timezone; storage/output are UTC. "
    "A supplied non-UTC offset must match the named local wall time, rejecting DST gaps; explicit "
    "offsets disambiguate folds. All-day events retain start_date/end_date, exclusive end, without "
    "conversion into timed events. Each event spans at most 366 days. command_key binds exact "
    "create/update intent; same-key replay returns the current result, another intent conflicts. "
    "Updates/deletes require a current revision ref (409 stale); unavailable source is 404. "
    "Search/report require a half-open Gregorian date range of 1–93 days and IANA timezone, "
    "size 1–100, at most 20 filters and 10 sorts. Actual live work_item.due_at values appear as "
    "read-only deadline points only with requests.start and current available/claimed cartable "
    "authority. Live visibility and overlap precede filtering, count, ordering and pagination. "
    "Derived items link to work_items and cannot be edited as calendar events. Manual links use "
    "calendar_events. History returns only transition timestamps/operations, at most 1000, "
    "without private snapshots. Delete is soft and cancels pending reminders in the same "
    "transaction. Up to three distinct reminder offsets of 0–2592000 seconds are supported. "
    "Existing envelopes, snake_case, en/fa localization, and private no-store apply."
)
router = APIRouter(prefix="/calendar", tags=["calendar-events"], responses=response_schema())


@router.post(
    "/events",
    response_model=SuccessResponse[CalendarItemDTO],
    summary=_("Create a calendar event"),
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def create(
    request: Request,
    data: CalendarInput,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
):
    result = await CalendarService(session).create(data, actor)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@router.post(
    "/events/report",
    response_model=PageResponse[Page[CalendarItemDTO]],
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
@router.post(
    "/events/search",
    response_model=PageResponse[Page[CalendarItemDTO]],
    summary=_("Search calendar events and deadlines"),
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def search(
    request: Request,
    data: CalendarQuery,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
):
    private_no_store(response)
    return page_response(request, await CalendarService(session).search(data, actor))


@router.get(
    "/events/{ref_id}",
    response_model=SuccessResponse[CalendarItemDTO],
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def detail(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
):
    service = CalendarService(session)
    private_no_store(response)
    return success_response(request, await service.dto(await service.get(ref_id, actor), actor))


@router.put(
    "/events/{ref_id}",
    response_model=SuccessResponse[CalendarItemDTO],
    summary=_("Update a calendar event"),
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def update(
    request: Request,
    ref_id: str,
    data: CalendarInput,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
):
    result = await CalendarService(session).update(ref_id, data, actor)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@router.delete(
    "/events/{ref_id}",
    response_model=SuccessResponse[None],
    description=DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def delete(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
):
    await CalendarService(session).delete(ref_id, actor)
    await session.commit()
    private_no_store(response)
    return success_response(request, None)


@router.post(
    "/events/{ref_id}/history",
    response_model=PageResponse[Page[CalendarHistoryDTO]],
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
):
    private_no_store(response)
    return page_response(request, await CalendarService(session).history(ref_id, actor, data))


REMINDER_DESCRIPTION = _(
    "Authenticated source-owned reminder state. Manual configuration is part of event create/update; "
    "work reminders require requests.start and current available/claimed cartable responsibility, "
    "a current source revision ref, and an actual due_at. Configure one to three distinct offsets "
    "0–2592000 seconds; command_key binds exact intent, changed intent conflicts 409. DELETE "
    "cancels this actor's work reminders without changing the workflow deadline. Read exposes at "
    "most the latest 100 owned reminder states, never another recipient's schedule or destination. "
    "Existing database clocked one-off scheduling, durable outbox and MAP-10/11 own delivery. "
    "Event edits/deletes and terminal/forwarded work changes cancel old state in the source "
    "transaction; recipient authority and source revision/deadline are checked again at fire and "
    "delivery. Replays cannot create duplicate notices. Late reminders deliver once within 24 "
    "hours if still relevant; older occurrences expire and record bounded support lag. This "
    "never changes business state, guarantees provider receipt, or creates a second timer loop. "
    "Private no-store, existing snake_case envelopes and en/fa localization apply."
)


@router.get(
    "/events/{ref_id}/reminders",
    response_model=SuccessResponse[list[ReminderDTO]],
    description=REMINDER_DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def event_reminders(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
):
    private_no_store(response)
    return success_response(request, await read_reminders(session, ref_id, actor, kind="manual"))


@router.get(
    "/work-reminders/{ref_id}",
    response_model=SuccessResponse[list[ReminderDTO]],
    description=REMINDER_DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def work_reminders(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
):
    private_no_store(response)
    return success_response(request, await read_reminders(session, ref_id, actor, kind="work_item"))


@router.put(
    "/work-reminders/{ref_id}",
    response_model=SuccessResponse[list[ReminderDTO]],
    description=REMINDER_DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def configure_reminders(
    request: Request,
    ref_id: str,
    data: ReminderInput,
    response: Response,
    actor: CurrentUser,
    session: SessionDep,
):
    result = await configure_work_reminders(session, ref_id, data, actor)
    await session.commit()
    private_no_store(response)
    return success_response(request, result)


@router.delete(
    "/work-reminders/{ref_id}",
    response_model=SuccessResponse[None],
    description=REMINDER_DESCRIPTION,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def cancel_reminders(
    request: Request, ref_id: str, response: Response, actor: CurrentUser, session: SessionDep
):
    from apps.users.application.authorization import user_permissions
    from apps.work_items.application.service import WorkItemService
    from utils.exceptions import NotFoundException

    actor = await CalendarService(session)._actor(actor, write=True)
    permissions = await user_permissions(actor, session)
    if "*" not in permissions and "requests.start" not in permissions:
        raise NotFoundException()
    item = await WorkItemService(session).get(ref_id, actor, update_row=True)
    if not await responsible(session, item, actor):
        raise NotFoundException()
    await cancel_source_reminders(session, "work_item", item.id, actor.id)
    await session.commit()
    private_no_store(response)
    return success_response(request, None)
