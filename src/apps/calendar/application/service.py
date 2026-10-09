"""Live membership and exact SQL overlap precede filtering, count and paging."""

from types import SimpleNamespace
from uuid import UUID, uuid5

from sqlalchemy import Date, DateTime, Uuid, cast, literal, union_all
from sqlalchemy import select as sql_select
from sqlmodel import col, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.calendar.domain.dto import (
    AllDaySchedule,
    CalendarHistoryDTO,
    CalendarInput,
    CalendarItemDTO,
    CalendarQuery,
    DeadlineSchedule,
    TimedSchedule,
    day_instant,
)
from apps.calendar.domain.entity import CalendarEventEntity, CalendarEventHistory
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CartableQueryDTO
from apps.work_items.domain.entity import WorkItemEntity
from core.i18n import _
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException
from utils.pagination import Page, PageRequest, apply_query, paginate_values


def calendar_groups(actor: UserEntity):
    return (
        select(WorkGroupMemberEntity.work_group_id)
        .join(WorkGroupEntity, col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id))
        .where(
            WorkGroupMemberEntity.user_id == actor.id,
            col(WorkGroupMemberEntity.is_active).is_(True),
            col(WorkGroupEntity.is_active).is_(True),
            col(WorkGroupEntity.deleted_at).is_(None),
        )
    )


def event_visibility(actor: UserEntity):
    return or_(
        (
            col(CalendarEventEntity.work_group_id).is_(None)
            & (col(CalendarEventEntity.owner_id) == actor.id)
        ),
        col(CalendarEventEntity.work_group_id).in_(calendar_groups(actor)),
    )


class CalendarService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _actor(self, actor: UserEntity, *, write: bool = False) -> UserEntity:
        current = await self.session.get(
            UserEntity, actor.id, populate_existing=True, with_for_update=write
        )
        if current is None or current.deleted_at is not None:
            raise NotFoundException()
        return current

    async def _group(self, actor: UserEntity, reference: str | None) -> UUID | None:
        if reference is None:
            return None
        identity, version = open_ref_id(reference)
        group = await self.session.get(WorkGroupEntity, identity, populate_existing=True)
        membership = (
            await self.session.exec(
                select(WorkGroupMemberEntity)
                .where(
                    WorkGroupMemberEntity.work_group_id == identity,
                    WorkGroupMemberEntity.user_id == actor.id,
                )
                .execution_options(populate_existing=True)
            )
        ).first()
        if (
            group is None
            or group.deleted_at is not None
            or not group.is_active
            or membership is None
            or not membership.is_active
        ):
            raise NotFoundException()
        if group.version != version:
            raise VersionConflictException()
        return identity

    async def get(
        self, reference: str, actor: UserEntity, *, write: bool = False
    ) -> CalendarEventEntity:
        actor = await self._actor(actor)
        identity, version = open_ref_id(reference)
        statement = (
            select(CalendarEventEntity)
            .where(
                CalendarEventEntity.id == identity,
                col(CalendarEventEntity.deleted_at).is_(None),
                event_visibility(actor),
            )
            .execution_options(populate_existing=True)
        )
        if write:
            statement = statement.with_for_update()
        row = (await self.session.exec(statement)).first()
        if row is None or (write and row.owner_id != actor.id):
            raise NotFoundException()
        if write and row.version != version:
            raise VersionConflictException()
        return row

    async def dto(self, row: CalendarEventEntity, actor: UserEntity) -> CalendarItemDTO:
        if row.kind == "timed":
            if row.start_at is None or row.end_at is None:
                raise ValueError("Invalid retained timed event")
            schedule = TimedSchedule(
                start_at=row.start_at, end_at=row.end_at, timezone=row.timezone
            )
        else:
            if row.start_date is None or row.end_date is None:
                raise ValueError("Invalid retained date event")
            schedule = AllDaySchedule(
                start_date=row.start_date, end_date=row.end_date, timezone=row.timezone
            )
        group = (
            await self.session.get(WorkGroupEntity, row.work_group_id)
            if row.work_group_id is not None
            else None
        )
        return CalendarItemDTO(
            ref_id=create_ref_id(row.id, row.version),
            source_kind="manual",
            title=row.title,
            schedule=schedule,
            editable=row.owner_id == actor.id,
            route_key="calendar_events",
            work_group_ref_id=create_ref_id(group.id, group.version) if group is not None else None,
        )

    @staticmethod
    def _values(data: CalendarInput) -> dict[str, object]:
        return {
            "title": data.title,
            "kind": data.schedule.kind,
            "timezone": data.schedule.timezone,
            "start_at": data.schedule.start_at
            if isinstance(data.schedule, TimedSchedule)
            else None,
            "end_at": data.schedule.end_at if isinstance(data.schedule, TimedSchedule) else None,
            "start_date": data.schedule.start_date
            if isinstance(data.schedule, AllDaySchedule)
            else None,
            "end_date": data.schedule.end_date
            if isinstance(data.schedule, AllDaySchedule)
            else None,
        }

    async def create(self, data: CalendarInput, actor: UserEntity) -> CalendarItemDTO:
        actor = await self._actor(actor, write=True)
        identity = uuid5(actor.id, "calendar-create:" + data.command_key)
        document = data.model_dump(mode="json")
        previous = await self.session.get(CalendarEventEntity, identity, populate_existing=True)
        if previous is not None:
            if previous.document["creation"] != document:
                raise VersionConflictException("Calendar key binds another intent")
            return await self.dto(
                await self.get(create_ref_id(previous.id, previous.version), actor), actor
            )
        count = (
            await self.session.exec(
                select(func.count())
                .select_from(CalendarEventEntity)
                .where(
                    CalendarEventEntity.owner_id == actor.id,
                    col(CalendarEventEntity.deleted_at).is_(None),
                )
            )
        ).one()
        if count >= 1000:
            raise ValidationDetailsException([{"pointer": "/", "code": "calendar.event_limit"}])
        group_id = await self._group(actor, data.work_group_ref_id)
        row = CalendarEventEntity.model_validate(
            {
                "id": identity,
                "owner_id": actor.id,
                "work_group_id": group_id,
                "document": {"creation": document, "current": document},
                **self._values(data),
            }
        )
        self.session.add(row)
        await self.session.flush()
        from apps.calendar.application.reminders import sync_event_reminders

        await sync_event_reminders(self.session, row, actor, data.reminder_offsets)
        return await self.dto(row, actor)

    async def update(
        self, reference: str, data: CalendarInput, actor: UserEntity
    ) -> CalendarItemDTO:
        actor = await self._actor(actor, write=True)
        identity, version = open_ref_id(reference)
        row = await self.get(create_ref_id(identity, 0), actor)
        if row.owner_id != actor.id:
            raise NotFoundException()
        document = data.model_dump(mode="json")
        if row.document.get("last_update") == data.command_key:
            if row.document["current"] != document:
                raise VersionConflictException("Calendar update key binds another intent")
            return await self.dto(row, actor)
        row = await self.get(create_ref_id(identity, version), actor, write=True)
        group_id = await self._group(actor, data.work_group_ref_id)
        for key, value in self._values(data).items():
            setattr(row, key, value)
        row.work_group_id = group_id
        row.document = row.document | {"current": document, "last_update": data.command_key}
        row.updated_at = get_datetime_utc()
        self.session.add(row)
        await self.session.flush()
        from apps.calendar.application.reminders import sync_event_reminders

        await sync_event_reminders(self.session, row, actor, data.reminder_offsets)
        return await self.dto(row, actor)

    async def delete(self, reference: str, actor: UserEntity) -> None:
        actor = await self._actor(actor, write=True)
        identity, version = open_ref_id(reference)
        row = await self.session.get(
            CalendarEventEntity, identity, populate_existing=True, with_for_update=True
        )
        if row is None or row.owner_id != actor.id:
            raise NotFoundException()
        if row.deleted_at is not None:
            return
        if row.version != version:
            raise VersionConflictException()
        row.deleted_at = get_datetime_utc()
        self.session.add(row)
        await self.session.flush()
        from apps.calendar.application.reminders import cancel_source_reminders

        await cancel_source_reminders(self.session, "manual", row.id)

    async def search(self, query: CalendarQuery, actor: UserEntity) -> Page[CalendarItemDTO]:
        actor = await self._actor(actor)
        start, end = (
            day_instant(query.start_date, query.timezone),
            day_instant(query.end_date, query.timezone),
        )
        timed = (
            (col(CalendarEventEntity.kind) == "timed")
            & (col(CalendarEventEntity.start_at) < end)
            & (col(CalendarEventEntity.end_at) > start)
        )
        dates = (
            (col(CalendarEventEntity.kind) == "all_day")
            & (col(CalendarEventEntity.start_date) < query.end_date)
            & (col(CalendarEventEntity.end_date) > query.start_date)
        )
        manual = sql_select(
            col(CalendarEventEntity.id).label("identity"),
            col(CalendarEventEntity.version).label("version"),
            literal("manual").label("source_kind"),
            col(CalendarEventEntity.title).label("title"),
            col(CalendarEventEntity.kind).label("kind"),
            col(CalendarEventEntity.start_at).label("start_at"),
            col(CalendarEventEntity.end_at).label("end_at"),
            col(CalendarEventEntity.start_date).label("start_date"),
            col(CalendarEventEntity.end_date).label("end_date"),
            col(CalendarEventEntity.timezone).label("timezone"),
            col(CalendarEventEntity.work_group_id).label("group_id"),
            func.coalesce(
                col(CalendarEventEntity.start_at),
                func.timezone(
                    col(CalendarEventEntity.timezone),
                    cast(col(CalendarEventEntity.start_date), DateTime()),
                ),
            ).label("sort_at"),
        ).where(
            col(CalendarEventEntity.deleted_at).is_(None),
            event_visibility(actor),
            or_(timed, dates),
        )
        sources = [manual]
        permissions = await user_permissions(actor, self.session)
        if query.include_work_deadlines and ("*" in permissions or "requests.start" in permissions):
            work = WorkItemService(self.session)
            available = work.search_criteria(CartableQueryDTO(cartable="available"), actor)
            claimed = work.search_criteria(CartableQueryDTO(cartable="claimed"), actor)
            derived = sql_select(
                col(WorkItemEntity.id).label("identity"),
                col(WorkItemEntity.version).label("version"),
                literal("work_item").label("source_kind"),
                literal(_("Work deadline")).label("title"),
                literal("deadline").label("kind"),
                col(WorkItemEntity.due_at).label("start_at"),
                cast(literal(None), DateTime(timezone=True)).label("end_at"),
                cast(literal(None), Date()).label("start_date"),
                cast(literal(None), Date()).label("end_date"),
                literal(query.timezone).label("timezone"),
                cast(literal(None), Uuid()).label("group_id"),
                col(WorkItemEntity.due_at).label("sort_at"),
            ).where(
                or_(self._and(available), self._and(claimed)),
                col(WorkItemEntity.deleted_at).is_(None),
                col(WorkItemEntity.status).in_(["OPEN", "CLAIMED", "IN_PROGRESS"]),
                col(WorkItemEntity.due_at) >= start,
                col(WorkItemEntity.due_at) < end,
            )
            sources.append(derived)
        population = union_all(*sources).subquery("calendar_population")
        columns = SimpleNamespace(**{column.name: column for column in population.c})
        rows_query = sql_select(
            population.c.identity,
            population.c.version,
            population.c.source_kind,
            population.c.title,
            population.c.kind,
            population.c.start_at,
            population.c.end_at,
            population.c.start_date,
            population.c.end_date,
            population.c.timezone,
            population.c.group_id,
            population.c.sort_at,
        )
        await self.session.flush()
        connection = await self.session.connection()
        rows = (
            await connection.execute(
                apply_query(rows_query, columns, query, default_ordering=("sort_at", "identity"))
            )
        ).all()
        total = (
            await self.session.exec(
                apply_query(
                    select(func.count()).select_from(population), columns, query, paginate=False
                )
            )
        ).one()
        items = []
        for record in rows:
            if record[2] == "work_item":
                items.append(
                    CalendarItemDTO(
                        ref_id=create_ref_id(record[0], record[1]),
                        source_kind="work_item",
                        title=record[3],
                        schedule=DeadlineSchedule(due_at=record[5], timezone=query.timezone),
                        editable=False,
                        route_key="work_items",
                    )
                )
            else:
                row = await self.session.get(CalendarEventEntity, record[0], populate_existing=True)
                if row is None:
                    raise NotFoundException()
                items.append(await self.dto(row, actor))
        return Page(items=items, page=query.page, size=query.size, total=total)

    @staticmethod
    def _and(criteria):
        from sqlalchemy import and_

        return and_(*criteria)

    async def history(
        self, reference: str, actor: UserEntity, query: PageRequest
    ) -> Page[CalendarHistoryDTO]:
        row = await self.get(reference, actor)
        records = (
            await self.session.exec(
                select(CalendarEventHistory.c.CHANGED_AT, CalendarEventHistory.c.OPERATION)
                .where(CalendarEventHistory.c.ENTITY_ID == row.id)
                .order_by(CalendarEventHistory.c.CHANGED_AT, CalendarEventHistory.c.ID)
                .limit(1001)
            )
        ).all()
        if len(records) > 1000:
            raise VersionConflictException("Calendar history exceeds projection bound")
        return paginate_values(
            [CalendarHistoryDTO(changed_at=record[0], operation=record[1]) for record in records],
            query,
        )
