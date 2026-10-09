"""Transaction-owned one-off schedules, live source checks and deduped notices."""

from datetime import timedelta
from uuid import UUID, uuid5

import structlog
from sqlalchemy import and_, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.calendar.application.service import CalendarService
from apps.calendar.domain.dto import ReminderDTO, ReminderInput, day_instant
from apps.calendar.domain.entity import CalendarEventEntity
from apps.calendar.domain.reminder import CalendarReminderEntity
from apps.notifications.application.events import stage_notice
from apps.tasks.domain.entity import PeriodicTaskEntity
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CartableQueryDTO
from apps.work_items.domain.entity import WorkItemEntity
from core.deps import SessionFactory
from core.ref_id import create_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException

logger = structlog.get_logger(__name__)
REMINDER_TASK = "bpms.fire_calendar_reminder"


async def responsible(session: AsyncSession, item: WorkItemEntity, actor: UserEntity) -> bool:
    service = WorkItemService(session)
    criteria = or_(
        and_(*service.search_criteria(CartableQueryDTO(cartable="available"), actor)),
        and_(*service.search_criteria(CartableQueryDTO(cartable="claimed"), actor)),
    )
    return (
        await session.exec(select(WorkItemEntity.id).where(WorkItemEntity.id == item.id, criteria))
    ).first() is not None


def deadline_revision(item: WorkItemEntity) -> str:
    return item.due_at.isoformat() if item.due_at is not None else "absent"


async def cancel_source_reminders(
    session: AsyncSession, kind: str, source_id: UUID, recipient_id: UUID | None = None
) -> None:
    statement = (
        select(CalendarReminderEntity)
        .where(
            CalendarReminderEntity.source_kind == kind,
            CalendarReminderEntity.source_id == source_id,
            col(CalendarReminderEntity.status).in_(["PENDING", "SENT"]),
        )
        .order_by(col(CalendarReminderEntity.id))
        .with_for_update()
    )
    if recipient_id is not None:
        statement = statement.where(CalendarReminderEntity.recipient_id == recipient_id)
    for reminder in (await session.exec(statement)).all():
        reminder.status = "CANCELLED"
        schedule = await session.get(PeriodicTaskEntity, reminder.schedule_id, with_for_update=True)
        if schedule is not None:
            schedule.enabled = False
            session.add(schedule)
        session.add(reminder)
    await session.flush()


async def _configure(
    session: AsyncSession,
    *,
    kind: str,
    source_id: UUID,
    revision: str,
    actor: UserEntity,
    due_at,
    offsets: list[int],
    command_key: str,
) -> list[ReminderDTO]:
    rows = []
    for offset in offsets:
        identity = uuid5(
            source_id, f"calendar-reminder:{kind}:{revision}:{actor.id}:{command_key}:{offset}"
        )
        row = await session.get(CalendarReminderEntity, identity)
        if row is None:
            schedule_id = uuid5(identity, "periodic-task")
            fire_at = due_at - timedelta(seconds=offset)
            schedule = PeriodicTaskEntity(
                id=schedule_id,
                name="calendar-reminder:" + str(identity),
                task_name=REMINDER_TASK,
                queue=settings.CELERY_AUTOMATION_QUEUE,
                schedule_type="clocked",
                clocked_at=fire_at,
                one_off=True,
                kwargs={"reminder_id": str(identity)},
            )
            session.add(schedule)
            await session.flush()
            row = CalendarReminderEntity(
                id=identity,
                source_kind=kind,
                source_id=source_id,
                source_revision=revision,
                recipient_id=actor.id,
                schedule_id=schedule_id,
                command_key=command_key,
                offset_seconds=offset,
                due_at=fire_at,
            )
            session.add(row)
            await session.flush()
        rows.append(reminder_dto(row))
    return rows


def reminder_dto(row: CalendarReminderEntity) -> ReminderDTO:
    from pydantic import TypeAdapter

    return ReminderDTO(
        ref_id=create_ref_id(row.id, row.version),
        due_at=row.due_at,
        status=TypeAdapter(ReminderDTO.model_fields["status"].annotation).validate_python(
            row.status
        ),
    )


async def sync_event_reminders(
    session: AsyncSession, event: CalendarEventEntity, actor: UserEntity, offsets: list[int]
) -> list[ReminderDTO]:
    await cancel_source_reminders(session, "manual", event.id)
    due = (
        event.start_at
        if event.kind == "timed"
        else day_instant(event.start_date, event.timezone)
        if event.start_date
        else None
    )
    if due is None:
        raise ValueError("Invalid calendar source")
    return await _configure(
        session,
        kind="manual",
        source_id=event.id,
        revision=str(event.version),
        actor=actor,
        due_at=due,
        offsets=offsets,
        command_key=event.document["current"]["command_key"],
    )


async def configure_work_reminders(
    session: AsyncSession, reference: str, data: ReminderInput, actor: UserEntity
) -> list[ReminderDTO]:
    actor = await CalendarService(session)._actor(actor, write=True)
    permissions = await user_permissions(actor, session)
    if "*" not in permissions and "requests.start" not in permissions:
        raise NotFoundException()
    item = await WorkItemService(session).get(reference, actor, update_row=True)
    if (
        item.due_at is None
        or item.status not in {"OPEN", "CLAIMED", "IN_PROGRESS"}
        or not await responsible(session, item, actor)
    ):
        raise NotFoundException()
    from core.ref_id import open_ref_id

    if item.version != open_ref_id(reference)[1]:
        raise VersionConflictException()
    previous = (
        await session.exec(
            select(CalendarReminderEntity).where(
                CalendarReminderEntity.source_kind == "work_item",
                CalendarReminderEntity.source_id == item.id,
                CalendarReminderEntity.recipient_id == actor.id,
                CalendarReminderEntity.command_key == data.command_key,
            )
        )
    ).all()
    if previous:
        if sorted(row.offset_seconds for row in previous) != data.offsets or any(
            row.source_revision != deadline_revision(item) for row in previous
        ):
            raise VersionConflictException("Reminder key binds another intent")
        return [reminder_dto(row) for row in previous]
    await cancel_source_reminders(session, "work_item", item.id, actor.id)
    return await _configure(
        session,
        kind="work_item",
        source_id=item.id,
        revision=deadline_revision(item),
        actor=actor,
        due_at=item.due_at,
        offsets=data.offsets,
        command_key=data.command_key,
    )


async def reminder_eligible(
    session: AsyncSession, row: CalendarReminderEntity, actor: UserEntity
) -> bool:
    if actor.deleted_at is not None:
        return False
    try:
        if row.source_kind == "manual":
            source = await CalendarService(session).get(create_ref_id(row.source_id, 0), actor)
            end = (
                source.end_at
                if source.kind == "timed"
                else day_instant(source.end_date, source.timezone)
                if source.end_date
                else None
            )
            return (
                source.owner_id == actor.id
                and str(source.version) == row.source_revision
                and end is not None
                and end > get_datetime_utc()
            )
        permissions = await user_permissions(actor, session)
        if "*" not in permissions and "requests.start" not in permissions:
            return False
        item = await WorkItemService(session).get(create_ref_id(row.source_id, 0), actor)
        return (
            await responsible(session, item, actor)
            and item.status in {"OPEN", "CLAIMED", "IN_PROGRESS"}
            and item.due_at is not None
            and deadline_revision(item) == row.source_revision
        )
    except NotFoundException:
        return False


async def fire_reminder(identity: UUID) -> str:
    async with SessionFactory() as session, session.begin():
        # Source writers lock the actor before reminder rows; the fire path uses the same order.
        initial = await session.get(CalendarReminderEntity, identity)
        if initial is None:
            return "missing"
        actor = await session.get(
            UserEntity, initial.recipient_id, with_for_update=True, populate_existing=True
        )
        row = await session.get(
            CalendarReminderEntity, identity, with_for_update=True, populate_existing=True
        )
        if row is None or row.status != "PENDING":
            return row.status.lower() if row is not None else "missing"
        now = get_datetime_utc()
        if row.due_at > now:
            return "pending"
        lag = (now - row.due_at).total_seconds()
        logger.info("calendar.reminder_lag", lag_seconds=lag, source_kind=row.source_kind)
        if actor is None or not await reminder_eligible(session, row, actor):
            row.status = "CANCELLED"
        elif lag > 86400:
            row.status = "EXPIRED"
            from apps.support.application.recorder import record_failure

            await record_failure(
                category="notification",
                error_code=1098,
                operation="calendar.reminder_late",
                request_id=row.id,
            )
        else:
            row.status = "SENT"
            session.add(row)
            await session.flush()
            notice = await stage_notice(
                session,
                map_id="MAP-10" if row.source_kind == "manual" else "MAP-11",
                event_id=row.id,
                recipient_id=actor.id,
                target_kind="calendar" if row.source_kind == "manual" else "work_item",
                target_id=row.source_id,
            )
            if notice is None:
                row.status = "CANCELLED"
        session.add(row)
        return row.status.lower()


async def read_reminders(
    session: AsyncSession, reference: str, actor: UserEntity, *, kind: str
) -> list[ReminderDTO]:
    source = (
        await CalendarService(session).get(reference, actor)
        if kind == "manual"
        else await WorkItemService(session).get(reference, actor)
    )
    if isinstance(source, CalendarEventEntity) and source.owner_id != actor.id:
        raise NotFoundException()
    if isinstance(source, WorkItemEntity):
        permissions = await user_permissions(actor, session)
        if (
            "*" not in permissions and "requests.start" not in permissions
        ) or not await responsible(session, source, actor):
            raise NotFoundException()
    rows = (
        await session.exec(
            select(CalendarReminderEntity)
            .where(
                CalendarReminderEntity.source_kind == kind,
                CalendarReminderEntity.source_id == source.id,
                CalendarReminderEntity.recipient_id == actor.id,
            )
            .order_by(col(CalendarReminderEntity.created_at).desc(), col(CalendarReminderEntity.id))
            .limit(100)
        )
    ).all()
    return [reminder_dto(row) for row in rows]
