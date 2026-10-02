"""Durable notification and external delivery entities."""

from apps.notifications.domain.entities.delivery import NotificationDeliveryEntity
from apps.notifications.domain.entities.notification import NotificationEntity

__all__ = ["NotificationDeliveryEntity", "NotificationEntity"]
