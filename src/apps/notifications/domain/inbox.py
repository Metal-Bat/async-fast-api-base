"""Versioned inbox contract with explicit authorized target availability."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from apps.notifications.domain.dto import NotificationQuery
from core.base_dto import BaseDTO


class TargetBase(BaseDTO):
    available: bool
    ref_id: str | None = None


class CaseTarget(TargetBase):
    kind: Literal["case"] = "case"
    route_key: Literal["business_requests"] = "business_requests"


class WorkTarget(TargetBase):
    kind: Literal["work_item", "ai_approval"]
    route_key: Literal["work_items"] = "work_items"


class ReportTarget(TargetBase):
    kind: Literal["report"] = "report"
    route_key: Literal["reports"] = "reports"


class AccountTarget(TargetBase):
    kind: Literal["account"] = "account"
    route_key: Literal["me"] = "me"


class FutureTarget(TargetBase):
    kind: Literal["operation"]
    route_key: None = None


class CalendarTarget(TargetBase):
    kind: Literal["calendar"] = "calendar"
    route_key: Literal["calendar_events"] = "calendar_events"


class SupportTarget(TargetBase):
    kind: Literal["support"] = "support"
    route_key: Literal["support_incidents"] = "support_incidents"


InboxTarget = Annotated[
    CaseTarget
    | WorkTarget
    | ReportTarget
    | AccountTarget
    | SupportTarget
    | CalendarTarget
    | FutureTarget,
    Field(discriminator="kind"),
]


class InboxDTO(BaseDTO):
    schema_version: Literal[1] = 1
    ref_id: str
    template_key: str
    template_version: str
    locale: str
    subject: str
    content: str | None
    priority: int
    status: str
    read_at: datetime | None
    created_at: datetime
    target: InboxTarget


class InboxQuery(NotificationQuery):
    unread: bool | None = Field(
        default=None,
        description="True limits to unread rows; false limits to read rows; omitted/null includes both.",
    )


class UnreadDTO(BaseDTO):
    total: int


class ReadCommand(BaseDTO):
    model_config = ConfigDict(extra="forbid")
