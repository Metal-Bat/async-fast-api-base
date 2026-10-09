"""Safe incident and client intake wire contracts."""

from datetime import datetime
from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO
from core.i18n import _
from utils.pagination import SearchRequest

Category = Literal["technical", "database", "cache", "storage", "broker", "client", "notification"]
IncidentState = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
ScreenKey = Literal[
    "calendar", "work_items", "requests", "designer", "reports", "preferences", "support"
]


class ClientFailure(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "screen_key": "calendar",
                    "build": "release.1",
                    "error_code": "client.render_failed",
                    "request_id": "00000000-0000-4000-8000-000000000001",
                }
            ]
        },
    )
    screen_key: ScreenKey
    build: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    error_code: Literal["client.render_failed", "client.network_failed", "client.unexpected_error"]
    request_id: UUID = Field(
        description=_("UUID correlation identity; do not send stack, message or request body.")
    )


class SupportReceipt(BaseDTO):
    persisted: bool = Field(
        description=_(
            "True only after independent incident commit; false means durability is unavailable."
        )
    )
    support_ref: UUID | None = Field(
        description=_(
            "Correlation identity only; support.incidents.manage is still required for inspection."
        )
    )


class IncidentDTO(BaseDTO):
    ref_id: str
    support_ref: UUID
    category: Category
    error_code: int
    operation: str
    state: IncidentState
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    expires_at: datetime


class IncidentQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {
        "state": str,
        "category": str,
        "error_code": int,
        "created_at": datetime,
        "request_id": UUID,
    }


class IncidentCommand(BaseDTO):
    model_config = ConfigDict(extra="forbid")


class IncidentHistoryDTO(BaseDTO):
    changed_at: datetime
    operation: str
    from_state: str | None
    to_state: str | None
