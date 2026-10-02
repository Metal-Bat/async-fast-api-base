"""Crash-safe, idempotent notification delivery execution."""

from datetime import timedelta
from uuid import UUID

from sqlmodel import col, select

from apps.integrations.data.secrets import EncryptedFileSecrets
from apps.notifications.application.providers import HttpNotificationProvider, NotificationProvider
from apps.notifications.application.service import (
    TERMINAL_DELIVERY_STATUSES,
    NotificationService,
    claim_delivery,
)
from apps.notifications.domain.entity import NotificationDeliveryEntity, NotificationEntity
from apps.processes.application.service import ProcessService
from apps.processes.domain.entity import StepExecutionAttemptEntity
from core.deps import SessionFactory
from core.ref_id import create_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import ServiceUnavailableException, ValidationDetailsException


def provider() -> HttpNotificationProvider:
    secrets = EncryptedFileSecrets(
        settings.INTEGRATION_SECRETS_DIR,
        [key.get_secret_value().encode() for key in settings.INTEGRATION_SECRET_KEYS],
    )
    return HttpNotificationProvider(secrets, settings.INTEGRATION_HTTP_ENDPOINTS)


async def deliver_notification(
    delivery_id: UUID, adapter: NotificationProvider | None = None
) -> str:
    """Resolve sensitive destination data inside the worker and apply one provider result."""
    async with SessionFactory() as session, session.begin():
        delivery, notification, recipient, connection = await claim_delivery(session, delivery_id)
        if delivery.status in TERMINAL_DELIVERY_STATUSES:
            return "duplicate"
        if notification.status != "ACTIVE":
            delivery.status = "CANCELLED"
            delivery.terminal_at = get_datetime_utc()
            return "cancelled"
        if recipient.deleted_at is not None or recipient.email is None:
            await _terminal(session, delivery, "FAILED", "notification.recipient.unavailable")
            await _finalize_if_ready(session, notification)
            return "failed"
        if (
            connection.deleted_at is not None
            or connection.status != "ACTIVE"
            or connection.verification_status != "VERIFIED"
            or connection.kind != "NOTIFICATION"
        ):
            await _terminal(session, delivery, "FAILED", "notification.connection.unavailable")
            await _finalize_if_ready(session, notification)
            return "failed"
        delivery.status = "RUNNING"
        delivery.attempt_count += 1
        delivery.next_attempt_at = None
        delivery.last_error_code = None
        delivery.updated_at = get_datetime_utc()
        destination = str(recipient.email)
        pin = NotificationService.connection_pin(connection)
        subject, content = notification.subject, notification.content
        if content is None:
            await _terminal(session, delivery, "FAILED", "notification.content.unavailable")
            await _finalize_if_ready(session, notification)
            return "failed"

    try:
        result = await (adapter or provider()).deliver(
            pin,
            destination=destination,
            subject=subject,
            content=content,
            idempotency_key=str(delivery_id),
        )
    except ValidationDetailsException:
        async with SessionFactory() as session, session.begin():
            delivery, notification, _, _ = await claim_delivery(session, delivery_id)
            await _terminal(session, delivery, "FAILED", "notification.delivery.rejected")
            await _finalize_if_ready(session, notification)
        return "failed"
    except Exception:  # noqa: BLE001 -- provider errors are replaced by stable domain codes
        async with SessionFactory() as session, session.begin():
            delivery, _, _, _ = await claim_delivery(session, delivery_id)
            if delivery.status not in TERMINAL_DELIVERY_STATUSES:
                delivery.status = "RETRY"
                delivery.last_error_code = "notification.provider.unavailable"
                delivery.next_attempt_at = get_datetime_utc() + timedelta(
                    seconds=min(300, 2**delivery.attempt_count)
                )
                delivery.updated_at = get_datetime_utc()
        raise ServiceUnavailableException("Notification provider unavailable") from None

    async with SessionFactory() as session, session.begin():
        delivery, notification, _, _ = await claim_delivery(session, delivery_id)
        if delivery.status in TERMINAL_DELIVERY_STATUSES:
            return "duplicate"
        delivery.status = result.status
        delivery.provider_message_ref = result.provider_message_ref
        delivery.delivered_at = get_datetime_utc() if result.status == "DELIVERED" else None
        delivery.terminal_at = get_datetime_utc()
        delivery.last_error_code = (
            "notification.delivery.bounced" if result.status == "BOUNCED" else None
        )
        delivery.updated_at = get_datetime_utc()
        await _finalize_if_ready(session, notification)
    return result.status.lower()


async def fail_delivery(delivery_id: UUID, code: str) -> str:
    """Exhaust one delivery without failing the durable in-application notification."""
    async with SessionFactory() as session, session.begin():
        delivery, notification, _, _ = await claim_delivery(session, delivery_id)
        if delivery.status in TERMINAL_DELIVERY_STATUSES:
            return "duplicate"
        await _terminal(session, delivery, "FAILED", code)
        await _finalize_if_ready(session, notification)
    return "failed"


async def _terminal(session, delivery, status: str, code: str) -> None:
    delivery.status = status
    delivery.last_error_code = code
    delivery.next_attempt_at = None
    delivery.terminal_at = get_datetime_utc()
    delivery.updated_at = get_datetime_utc()
    await session.flush()


async def _finalize_if_ready(session, notification: NotificationEntity) -> None:
    attempt = (
        await session.exec(
            select(StepExecutionAttemptEntity)
            .where(
                StepExecutionAttemptEntity.step_execution_id == notification.step_execution_id,
                col(StepExecutionAttemptEntity.status).in_(["WAITING", "RUNNING"]),
            )
            .order_by(col(StepExecutionAttemptEntity.number).desc())
            .with_for_update()
            .limit(1)
        )
    ).one_or_none()
    if attempt is None:
        return
    statuses = list(
        (
            await session.exec(
                select(NotificationDeliveryEntity.status)
                .join(
                    NotificationEntity,
                    col(NotificationEntity.id) == col(NotificationDeliveryEntity.notification_id),
                )
                .where(NotificationEntity.step_execution_id == notification.step_execution_id)
            )
        ).all()
    )
    if not statuses or any(status not in TERMINAL_DELIVERY_STATUSES for status in statuses):
        return
    first = (
        await session.exec(
            select(NotificationEntity)
            .where(NotificationEntity.step_execution_id == notification.step_execution_id)
            .order_by(col(NotificationEntity.id))
            .limit(1)
        )
    ).one()
    await ProcessService(session).complete_background(
        attempt.id, {"notification": create_ref_id(first.id, first.version)}
    )
