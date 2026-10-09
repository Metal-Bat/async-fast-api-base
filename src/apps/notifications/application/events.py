"""Transactional application notice intents and bounded existing-outbox fanout."""

from uuid import UUID, uuid5

from sqlalchemy import exists, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.notifications.application.inbox import InboxService
from apps.notifications.application.service import DELIVERY_TASK, NotificationService
from apps.notifications.application.templates import NotificationTemplateRegistry
from apps.notifications.domain.entity import NotificationDeliveryEntity, NotificationEntity
from apps.processes.domain.entity import (
    ProcessEventEntity,
    ProcessInstanceEntity,
)
from apps.requests.domain.entity import BusinessRequestEntity
from apps.tasks.application.outbox import enqueue_task
from apps.tasks.domain.entity import TaskOutboxEntity
from apps.users.application.preferences import PersonalSettingsService
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.work_items.domain.entity import WorkItemCandidateEntity, WorkItemEntity
from core.deps import SessionFactory
from core.i18n import translate
from core.ref_id import open_ref_id
from core.settings import settings
from utils.exceptions import InvalidReferenceException, VersionConflictException

FANOUT_TASK = "bpms.fanout_application_notice"
PROCESS_MAP = {
    "request.submitted": "MAP-01",
    "work_item.created": "MAP-02",
    "work_item.claimed": "MAP-03",
    "work_item.released": "MAP-03",
    "work_item.forwarded": "MAP-03",
    "work_item.returned": "MAP-04",
    "work_item.completed": "MAP-05",
    "work_item.rejected": "MAP-05",
    "process.completed": "MAP-06",
    "process.failed": "MAP-06",
}
BLOCKED_MAPS = frozenset({"MAP-07", "MAP-08"})


def stage_process_intent(session: AsyncSession, event: ProcessEventEntity) -> None:
    """The business owner commits this intent with its domain event, or neither persists."""
    if event.event_type in PROCESS_MAP:
        identity = uuid5(event.id, "application-notice:initial")
        enqueue_task(
            session,
            FANOUT_TASK,
            kwargs={"event_id": str(event.id)},
            queue=settings.CELERY_AUTOMATION_QUEUE,
            task_id=str(identity),
            idempotency_key=identity,
        )


async def stage_notice(
    session: AsyncSession,
    *,
    map_id: str,
    event_id: UUID,
    recipient_id: UUID,
    target_kind: str,
    target_id: UUID,
    request_id: UUID | None = None,
    process_id: UUID | None = None,
) -> NotificationEntity | None:
    """Stage one deduped in-app row and optional email through the existing delivery task."""
    if map_id in BLOCKED_MAPS:
        raise ValueError("Producer is not implemented")
    recipient = await session.get(
        UserEntity, recipient_id, with_for_update=True, populate_existing=True
    )
    if recipient is None or recipient.deleted_at is not None:
        return None
    templates = NotificationTemplateRegistry()
    number = int(map_id.removeprefix("MAP-"))
    key = f"application.map_{number:02d}"
    identity = uuid5(event_id, key + ":" + str(recipient_id))
    existing = await session.get(NotificationEntity, identity)
    if existing is not None:
        if existing.target_kind != target_kind or existing.target_id != target_id:
            raise VersionConflictException(
                "Notification occurrence target changed", conflict_kind="idempotency"
            )
        return existing
    preferences = await PersonalSettingsService(session).read(recipient)
    rendered = templates.render(
        key,
        "1",
        preferences.locale.language,
        {
            "resource_name": translate(
                {
                    "case": "Request",
                    "work_item": "Human task",
                    "ai_approval": "Read-only approval",
                    "report": "Report",
                    "account": "Account",
                }.get(target_kind, "Resource"),
                preferences.locale.language,
            )
        },
    )
    row = NotificationEntity(
        id=identity,
        recipient_user_id=recipient_id,
        business_request_id=request_id,
        process_instance_id=process_id,
        template_key=key,
        template_version="1",
        locale=preferences.locale.language,
        subject=rendered.subject,
        content=rendered.content,
        event_id=event_id,
        target_kind=target_kind,
        target_id=target_id,
    )
    if not (await InboxService(session).target(row, recipient)).available:
        return None
    session.add(row)
    await session.flush()
    mandatory = map_id in {"MAP-12", "MAP-14"}
    if (
        recipient.email is None
        or (not mandatory and not preferences.notifications.email_enabled)
        or settings.APPLICATION_NOTIFICATION_CONNECTION_REF is None
    ):
        return row
    try:
        connection_id, expected = open_ref_id(settings.APPLICATION_NOTIFICATION_CONNECTION_REF)
    except InvalidReferenceException:
        return row
    connection = await session.get(IntegrationConnectionEntity, connection_id)
    if (
        connection is None
        or connection.version != expected
        or connection.deleted_at is not None
        or connection.kind != "NOTIFICATION"
        or connection.status != "ACTIVE"
        or connection.verification_status != "VERIFIED"
    ):
        return row
    delivery = NotificationDeliveryEntity(
        notification_id=row.id,
        channel="EMAIL",
        destination_fingerprint=NotificationService._fingerprint(str(recipient.email)),
        integration_connection_id=connection.id,
    )
    session.add(delivery)
    await session.flush()
    enqueue_task(
        session,
        DELIVERY_TASK,
        kwargs={"delivery_id": str(delivery.id)},
        queue=settings.CELERY_AUTOMATION_QUEUE,
        task_id=f"notification:{delivery.id}",
        idempotency_key=delivery.id,
    )
    return row


async def fanout_event(event_id: UUID, after_user_id: UUID | None = None) -> int:
    """Resolve at most 100 live recipients per task; continuation contains opaque IDs only."""
    async with SessionFactory() as session, session.begin():
        event = await session.get(ProcessEventEntity, event_id, with_for_update=True)
        if event is None or event.event_type not in PROCESS_MAP:
            return 0
        process = await session.get(ProcessInstanceEntity, event.process_instance_id)
        request = await session.get(BusinessRequestEntity, event.business_request_id)
        if process is None or request is None or request.deleted_at is not None:
            return 0
        map_id = PROCESS_MAP[event.event_type]
        item = await session.get(WorkItemEntity, event.work_item_id) if event.work_item_id else None
        if map_id == "MAP-02" and item is not None:
            from apps.ai.domain.entity import AIToolApprovalEntity

            approval = (
                await session.exec(
                    select(AIToolApprovalEntity).where(AIToolApprovalEntity.work_item_id == item.id)
                )
            ).first()
            if approval is not None:
                return 0  # Dedicated mandatory MAP-12 already owns this occurrence.
        if map_id == "MAP-04":
            # The engine owns the correction recipient. Resolve its newly created work item,
            # not the reviewer whose old item emitted RETURN.
            item = (
                await session.exec(
                    select(WorkItemEntity)
                    .where(
                        WorkItemEntity.business_request_id == request.id,
                        WorkItemEntity.created_at >= event.occurred_at,
                        col(WorkItemEntity.deleted_at).is_(None),
                    )
                    .order_by(col(WorkItemEntity.created_at), col(WorkItemEntity.id))
                    .limit(1)
                )
            ).first()
        target_kind, target_id = (
            ("work_item", item.id)
            if map_id in {"MAP-02", "MAP-03", "MAP-04"} and item is not None
            else ("case", request.id)
        )
        if map_id in {"MAP-02", "MAP-04"} and (item is None or item.status != "OPEN"):
            return 0
        statement = select(UserEntity).where(col(UserEntity.deleted_at).is_(None))
        if target_kind == "work_item" and item is not None:
            groups = (
                select(WorkGroupMemberEntity.work_group_id)
                .join(
                    WorkGroupEntity,
                    col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id),
                )
                .where(
                    WorkGroupMemberEntity.user_id == UserEntity.id,
                    col(WorkGroupMemberEntity.is_active).is_(True),
                    col(WorkGroupEntity.deleted_at).is_(None),
                    col(WorkGroupEntity.is_active).is_(True),
                )
            )
            eligible = exists(
                select(WorkItemCandidateEntity.id).where(
                    WorkItemCandidateEntity.work_item_id == item.id,
                    or_(
                        col(WorkItemCandidateEntity.user_id) == col(UserEntity.id),
                        col(WorkItemCandidateEntity.work_group_id).in_(groups),
                    ),
                )
            )
            statement = statement.where(
                or_(
                    eligible,
                    col(UserEntity.id) == item.claimed_by_user_id,
                    col(UserEntity.id) == event.actor_user_id,
                )
                if map_id == "MAP-03"
                else eligible
            )
        else:
            statement = statement.where(UserEntity.id == request.requester_user_id)
        if after_user_id is not None:
            statement = statement.where(col(UserEntity.id) > after_user_id)
        recipients = list(
            (await session.exec(statement.order_by(col(UserEntity.id)).limit(101))).all()
        )
        count = 0
        for recipient in recipients[:100]:
            count += int(
                await stage_notice(
                    session,
                    map_id=map_id,
                    event_id=event.id,
                    recipient_id=recipient.id,
                    target_kind=target_kind,
                    target_id=target_id,
                    request_id=request.id,
                    process_id=process.id,
                )
                is not None
            )
        if len(recipients) > 100:
            cursor = recipients[99].id
            identity = uuid5(event.id, "application-notice:" + str(cursor))
            previous = (
                await session.exec(
                    select(TaskOutboxEntity).where(TaskOutboxEntity.task_id == str(identity))
                )
            ).first()
            if previous is not None:
                return count
            enqueue_task(
                session,
                FANOUT_TASK,
                kwargs={"event_id": str(event.id), "after_user_id": str(cursor)},
                queue=settings.CELERY_AUTOMATION_QUEUE,
                task_id=str(identity),
                idempotency_key=identity,
            )
        return count
