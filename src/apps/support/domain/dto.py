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
    screen_key: ScreenKey = Field(
        description=_("Known client screen identifier; arbitrary paths are not accepted.")
    )
    build: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9._-]+$",
        description=_(
            "Public build identifier, 1 to 80 ASCII letters, digits, dots, underscores or hyphens."
        ),
    )
    error_code: Literal[
        "client.render_failed", "client.network_failed", "client.unexpected_error"
    ] = Field(
        description=_(
            "Stable safe error code; exception messages and stack traces are never accepted."
        )
    )
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
    ref_id: str = Field(description=_("Opaque incident reference containing its current version."))
    support_ref: UUID = Field(
        description=_("Correlation UUID; inspection requires support.incidents.manage.")
    )
    category: Category = Field(
        description=_("Canonical incident category; localized labels do not change this value.")
    )
    error_code: int = Field(
        description=_(
            "Stable safe error code; exception messages and stack traces are never accepted."
        )
    )
    operation: str = Field(
        description=_("Safe operation identifier; contains no submitted business payload.")
    )
    state: IncidentState = Field(
        description=_("Incident lifecycle state: OPEN, ACKNOWLEDGED or RESOLVED.")
    )
    occurrence_count: int = Field(
        description=_("Number of grouped occurrences retained for this incident.")
    )
    first_seen_at: datetime = Field(
        description=_("Timezone-aware UTC instant of the first grouped occurrence.")
    )
    last_seen_at: datetime = Field(
        description=_("Timezone-aware UTC instant of the latest grouped occurrence.")
    )
    expires_at: datetime = Field(
        description=_("Timezone-aware UTC retention deadline; expired incidents may be removed.")
    )


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
    changed_at: datetime = Field(
        description=_("Timezone-aware UTC instant of this lifecycle transition.")
    )
    operation: str = Field(
        description=_("Safe operation identifier; contains no submitted business payload.")
    )
    from_state: str | None = Field(
        description=_("Previous canonical state; null for the initial transition.")
    )
    to_state: str | None = Field(
        description=_("Resulting canonical state; null when no destination state is recorded.")
    )
