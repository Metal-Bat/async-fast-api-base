"""Atomic notification creation, protected visibility, and external delivery lifecycle."""

from datetime import timedelta
from hashlib import sha256
from hmac import new as hmac_new
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.contracts import ConnectionPin
from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.notifications.application.templates import NotificationTemplateRegistry
from apps.notifications.domain.dto import NotificationQuery
from apps.notifications.domain.entity import NotificationDeliveryEntity, NotificationEntity
from apps.processes.application.automation import broker_priority
from apps.processes.domain.entity import (
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
)
from apps.requests.domain.entity import BusinessRequestEntity
from apps.step_types.application.registry import HandlerDefinition, NotificationConfigV2
from apps.tasks.application.outbox import enqueue_task
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowStepEntity, WorkflowVersionEntity
from core.ref_id import create_ref_id, open_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, NotFoundException, VersionConflictException
from utils.pagination import Page, paginate_entities

DELIVERY_TASK = "bpms.deliver_notification"
TERMINAL_DELIVERY_STATUSES = frozenset({"DELIVERED", "BOUNCED", "FAILED", "CANCELLED"})


class NotificationService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        templates: NotificationTemplateRegistry | None = None,
    ) -> None:
        self.session = session
        self.templates = templates or NotificationTemplateRegistry()

    async def stage(
        self,
        *,
        attempt: StepExecutionAttemptEntity,
        step: WorkflowStepEntity,
        handler: HandlerDefinition,
        request: BusinessRequestEntity,
        process: ProcessInstanceEntity,
        inputs: dict[str, object],
        connection_service: ConnectionService,
    ) -> list[NotificationEntity]:
        """Create user records, delivery rows, and opaque outbox commands in one transaction."""
        config = NotificationConfigV2.model_validate(step.config)
        rendered = self.templates.render(
            config.template_key,
            config.template_version,
            config.locale,
            inputs.get("data"),
        )
        recipients = inputs.get("recipients")
        if not isinstance(recipients, list) or not recipients:
            raise ValueError("Notification requires at least one recipient")
        version = await self.session.get(WorkflowVersionEntity, request.workflow_version_id)
        actor = (
            await self.session.get(UserEntity, version.published_by_user_id)
            if version is not None and version.published_by_user_id is not None
            else None
        )
        if actor is None:
            raise VersionConflictException("Published workflow has no execution principal")
        pin = await connection_service.pin(
            config.connection_ref,
            actor,
            handler_key=handler.handler_key,
            handler_version=handler.handler_version,
        )
        connection_id = open_ref_id(pin.connection_ref)[0]
        rows: list[NotificationEntity] = []
        seen: set[UUID] = set()
        for recipient_ref in recipients:
            if not isinstance(recipient_ref, str):
                raise TypeError("Notification recipient reference is invalid")
            recipient_id, recipient_version = open_ref_id(recipient_ref)
            if recipient_id in seen:
                continue
            seen.add(recipient_id)
            recipient = await self.session.get(UserEntity, recipient_id)
            if (
                recipient is None
                or recipient.version != recipient_version
                or recipient.deleted_at is not None
                or recipient.email is None
            ):
                raise VersionConflictException("Notification recipient is unavailable")
            notification = (
                await self.session.exec(
                    select(NotificationEntity).where(
                        NotificationEntity.step_execution_id == attempt.step_execution_id,
                        NotificationEntity.recipient_user_id == recipient.id,
                    )
                )
            ).one_or_none()
            if notification is None:
                notification = NotificationEntity(
                    recipient_user_id=recipient.id,
                    business_request_id=request.id,
                    process_instance_id=process.id,
                    step_execution_id=attempt.step_execution_id,
                    template_key=config.template_key,
                    template_version=config.template_version,
                    locale=config.locale,
                    subject=rendered.subject,
                    content=rendered.content,
                    priority=request.priority,
                )
                self.session.add(notification)
                await self.session.flush()
            delivery = (
                await self.session.exec(
                    select(NotificationDeliveryEntity).where(
                        NotificationDeliveryEntity.notification_id == notification.id,
                        NotificationDeliveryEntity.channel == config.channel,
                    )
                )
            ).one_or_none()
            if delivery is None:
                delivery = NotificationDeliveryEntity(
                    notification_id=notification.id,
                    channel=config.channel,
                    destination_fingerprint=self._fingerprint(str(recipient.email)),
                    integration_connection_id=connection_id,
                )
                self.session.add(delivery)
                await self.session.flush()
                enqueue_task(
                    self.session,
                    DELIVERY_TASK,
                    kwargs={"delivery_id": str(delivery.id)},
                    queue=settings.CELERY_AUTOMATION_QUEUE,
                    task_id=f"notification:{delivery.id}",
                    idempotency_key=delivery.id,
                    priority=broker_priority(request.priority),
                )
            rows.append(notification)
        if not rows:
            raise ValueError("Notification requires an eligible recipient")
        attempt.automation_snapshot = {
            "notification_refs": [create_ref_id(row.id, row.version) for row in rows]
        }
        return rows

    async def search(self, query: NotificationQuery, actor: UserEntity) -> Page[NotificationEntity]:
        return await paginate_entities(
            self.session,
            NotificationEntity,
            query,
            criteria=(
                NotificationEntity.recipient_user_id == actor.id,
                col(NotificationEntity.business_request_id).is_not(None),
                col(NotificationEntity.process_instance_id).is_not(None),
            ),
            default_ordering=("-created_at", "id"),
        )

    async def get(
        self, ref_id: str, actor: UserEntity, *, update: bool = False
    ) -> NotificationEntity:
        notification_id, version = open_ref_id(ref_id)
        row = await self.session.get(
            NotificationEntity,
            notification_id,
            with_for_update=update,
            populate_existing=True,
        )
        if row is None or row.deleted_at is not None:
            raise NotFoundException("Notification not found")
        if row.recipient_user_id != actor.id:
            raise NotAllowedException("Notification access denied")
        if update and row.version != version:
            raise VersionConflictException("Notification is stale")
        return row

    async def mark_read(self, ref_id: str, actor: UserEntity) -> NotificationEntity:
        row = await self.get(ref_id, actor, update=True)
        row.read_at = row.read_at or get_datetime_utc()
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def deliveries(self, notification_id: UUID) -> list[NotificationDeliveryEntity]:
        return list(
            (
                await self.session.exec(
                    select(NotificationDeliveryEntity)
                    .where(NotificationDeliveryEntity.notification_id == notification_id)
                    .order_by(
                        col(NotificationDeliveryEntity.created_at),
                        col(NotificationDeliveryEntity.id),
                    )
                )
            ).all()
        )

    async def cancel_process(self, process_id: UUID) -> None:
        notifications = list(
            (
                await self.session.exec(
                    select(NotificationEntity)
                    .where(
                        NotificationEntity.process_instance_id == process_id,
                        NotificationEntity.status == "ACTIVE",
                    )
                    .with_for_update()
                )
            ).all()
        )
        if not notifications:
            return
        for row in notifications:
            row.status = "CANCELLED"
            row.updated_at = get_datetime_utc()
        deliveries = list(
            (
                await self.session.exec(
                    select(NotificationDeliveryEntity)
                    .where(
                        col(NotificationDeliveryEntity.notification_id).in_(
                            [row.id for row in notifications]
                        ),
                        col(NotificationDeliveryEntity.status).in_(["PENDING", "RETRY"]),
                    )
                    .with_for_update()
                )
            ).all()
        )
        for delivery in deliveries:
            delivery.status = "CANCELLED"
            delivery.terminal_at = get_datetime_utc()
            delivery.updated_at = get_datetime_utc()

    async def redact_expired(self, *, limit: int = 100) -> int:
        cutoff = get_datetime_utc() - timedelta(days=settings.NOTIFICATION_RETENTION_DAYS)
        rows = list(
            (
                await self.session.exec(
                    select(NotificationEntity)
                    .where(
                        NotificationEntity.created_at < cutoff,
                        NotificationEntity.status != "EXPIRED",
                    )
                    .order_by(col(NotificationEntity.created_at), col(NotificationEntity.id))
                    .with_for_update(skip_locked=True)
                    .limit(limit)
                )
            ).all()
        )
        for row in rows:
            row.subject = "Expired notification"
            row.content = "Notification content expired by retention policy."
            row.content_ref = None
            row.status = "EXPIRED"
            row.updated_at = get_datetime_utc()
        return len(rows)

    @staticmethod
    def connection_pin(connection: IntegrationConnectionEntity) -> ConnectionPin:
        return ConnectionPin(
            connection_ref=create_ref_id(connection.id, connection.version),
            provider=connection.provider,
            kind=connection.kind,
            endpoint_key=str(connection.non_secret_config["endpoint_key"]),
            secret_ref=connection.secret_ref,
            secret_version=connection.secret_version,
        )

    @staticmethod
    def _fingerprint(destination: str) -> str:
        return hmac_new(
            settings.SECRET_KEY.encode(), destination.strip().casefold().encode(), sha256
        ).hexdigest()


async def claim_delivery(
    session: AsyncSession, delivery_id: UUID
) -> tuple[NotificationDeliveryEntity, NotificationEntity, UserEntity, IntegrationConnectionEntity]:
    delivery = await session.get(
        NotificationDeliveryEntity, delivery_id, with_for_update=True, populate_existing=True
    )
    if delivery is None:
        raise NotFoundException("Notification delivery not found")
    notification = await session.get(NotificationEntity, delivery.notification_id)
    if notification is None:
        raise NotFoundException("Notification not found")
    recipient = await session.get(UserEntity, notification.recipient_user_id)
    connection = await session.get(IntegrationConnectionEntity, delivery.integration_connection_id)
    if recipient is None or connection is None:
        raise VersionConflictException("Notification delivery dependencies are unavailable")
    return delivery, notification, recipient, connection
