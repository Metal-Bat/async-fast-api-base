"""Recipient-owned inbox projection; destinations recheck existing domain authority."""

from sqlmodel import col, func, select

from apps.notifications.application.service import NotificationService
from apps.notifications.domain.entity import NotificationEntity
from apps.notifications.domain.inbox import (
    AccountTarget,
    CalendarTarget,
    CaseTarget,
    FutureTarget,
    InboxDTO,
    InboxQuery,
    InboxTarget,
    ReportTarget,
    SupportTarget,
    WorkTarget,
)
from apps.reporting.domain.entity import ReportEntity
from apps.requests.application.service import RequestService
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from core.i18n import _
from core.ref_id import create_ref_id
from utils.exceptions import NotAllowedException, NotFoundException
from utils.pagination import Page, paginate_entities


class InboxService(NotificationService):
    async def target(self, row: NotificationEntity, actor: UserEntity) -> InboxTarget:
        kind = row.target_kind
        identity = row.target_id or row.business_request_id
        available = row.status == "ACTIVE" and identity is not None
        ref = None
        permissions = await user_permissions(actor, self.session)
        try:
            if row.template_key in {"application.map_10", "application.map_11"}:
                from apps.calendar.application.reminders import reminder_eligible
                from apps.calendar.domain.reminder import CalendarReminderEntity

                reminder = (
                    await self.session.get(CalendarReminderEntity, row.event_id)
                    if row.event_id is not None
                    else None
                )
                if (
                    reminder is None
                    or reminder.status != "SENT"
                    or not await reminder_eligible(self.session, reminder, actor)
                ):
                    raise NotFoundException()
            if kind == "account":
                available = available and identity == actor.id and actor.deleted_at is None
                ref = create_ref_id(actor.id, actor.version) if available else None
            elif kind == "case":
                if (
                    identity is None
                    or not available
                    or ("*" not in permissions and "requests.start" not in permissions)
                ):
                    raise NotFoundException()
                request = await RequestService(self.session).get_request(
                    create_ref_id(identity, 0), actor
                )
                ref = create_ref_id(request.id, request.version)
            elif kind in {"work_item", "ai_approval"}:
                if (
                    identity is None
                    or not available
                    or ("*" not in permissions and "requests.start" not in permissions)
                ):
                    raise NotFoundException()
                item = await WorkItemService(self.session).get(create_ref_id(identity, 0), actor)
                # Closed notices may remain readable, but stale actionable reminders may not send.
                ref = create_ref_id(item.id, item.version)
            elif kind == "report":
                report = await self.session.get(ReportEntity, identity) if available else None
                if report is None or report.owner_id != actor.id or report.deleted_at is not None:
                    raise NotFoundException()
                ref = create_ref_id(report.id, report.version)
            elif kind == "calendar":
                from apps.calendar.application.service import CalendarService

                if identity is None or not available:
                    raise NotFoundException()
                event = await CalendarService(self.session).get(create_ref_id(identity, 0), actor)
                ref = create_ref_id(event.id, event.version)
            elif kind == "support":
                from apps.support.application.service import require_support
                from apps.support.domain.entity import SupportIncidentEntity
                from utils.date_utils import get_datetime_utc

                await require_support(self.session, actor)
                incident = (
                    await self.session.get(SupportIncidentEntity, identity) if available else None
                )
                if (
                    incident is None
                    or incident.deleted_at is not None
                    or incident.expires_at <= get_datetime_utc()
                    or incident.state == "RESOLVED"
                ):
                    raise NotFoundException()
                ref = create_ref_id(incident.id, incident.version)
            else:
                available = False
        except NotFoundException, NotAllowedException:
            available, ref = False, None
        if kind == "account":
            return AccountTarget(available=bool(available), ref_id=ref)
        if kind == "case":
            return CaseTarget(available=bool(available), ref_id=ref)
        if kind in {"work_item", "ai_approval"}:
            return WorkTarget(kind=kind, available=bool(available), ref_id=ref)
        if kind == "report":
            return ReportTarget(available=bool(available), ref_id=ref)
        if kind == "support":
            return SupportTarget(available=bool(available), ref_id=ref)
        if kind == "calendar":
            return CalendarTarget(available=bool(available), ref_id=ref)
        return FutureTarget(
            kind="operation",
            available=False,
        )

    async def dto(self, row: NotificationEntity, actor: UserEntity) -> InboxDTO:
        target = await self.target(row, actor)
        return InboxDTO(
            ref_id=create_ref_id(row.id, row.version),
            template_key=row.template_key,
            template_version=row.template_version,
            locale=row.locale,
            subject=row.subject if target.available else _("Notification unavailable"),
            content=row.content if target.available else None,
            priority=row.priority,
            status=row.status,
            read_at=row.read_at,
            created_at=row.created_at,
            target=target,
        )

    async def inbox_search(self, query: InboxQuery, actor: UserEntity) -> Page[InboxDTO]:
        criteria = [NotificationEntity.recipient_user_id == actor.id]
        if query.unread is not None:
            criteria.append(
                col(NotificationEntity.read_at).is_(None)
                if query.unread
                else col(NotificationEntity.read_at).is_not(None)
            )
        page = await paginate_entities(
            self.session,
            NotificationEntity,
            query,
            criteria=tuple(criteria),
            default_ordering=("-created_at", "id"),
        )
        return Page[InboxDTO](
            items=[await self.dto(row, actor) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        )

    async def unread_count(self, actor: UserEntity) -> int:
        return int(
            (
                await self.session.exec(
                    select(func.count())
                    .select_from(NotificationEntity)
                    .where(
                        NotificationEntity.recipient_user_id == actor.id,
                        col(NotificationEntity.deleted_at).is_(None),
                        col(NotificationEntity.read_at).is_(None),
                        NotificationEntity.status == "ACTIVE",
                    )
                )
            ).one()
        )
