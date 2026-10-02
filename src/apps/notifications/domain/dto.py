"""Snake-case notification API and adapter contracts."""

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import Field

from core.base_dto import BaseDTO
from utils.pagination import SearchRequest


class NotificationQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {
        "template_key": str,
        "priority": int,
        "status": str,
        "read_at": datetime | None,
        "created_at": datetime,
    }


class DeliveryDTO(BaseDTO):
    ref_id: str
    channel: str
    status: str
    attempt_count: int
    provider_message_ref: str | None
    last_error_code: str | None
    next_attempt_at: datetime | None
    delivered_at: datetime | None


class NotificationDTO(BaseDTO):
    ref_id: str
    request_ref_id: str
    process_ref_id: str
    template_key: str
    template_version: str
    locale: str
    subject: str
    content: str | None
    priority: int
    status: str
    read_at: datetime | None
    created_at: datetime
    deliveries: list[DeliveryDTO] = Field(default_factory=list)


class DeliveryResult(BaseDTO):
    status: Literal["DELIVERED", "BOUNCED"]
    provider_message_ref: str | None = None


class RenderedNotification(BaseDTO):
    subject: str
    content: str
