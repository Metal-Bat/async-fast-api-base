"""Date-only all-day events, explicit timed instants and read-only deadlines."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any, ClassVar, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, ConfigDict, Field, field_validator, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from utils.pagination import SearchRequest


def calendar_zone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError, ValueError:
        raise ValueError("Calendar requires an IANA timezone") from None


def day_instant(value: date, zone: str) -> datetime:
    """Resolve local midnight to a UTC boundary; wire dates remain dates."""
    timezone = calendar_zone(zone)
    local = datetime.combine(value, time(), timezone)
    instant = local.astimezone(UTC)
    if instant.astimezone(timezone).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError("Nonexistent calendar date boundary")
    return instant


class ZonedSchedule(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    timezone: str = Field(
        min_length=1,
        max_length=64,
        description=_("IANA timezone for local presentation; canonical dates remain Gregorian."),
    )

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value: str) -> str:
        calendar_zone(value)
        return value


class TimedSchedule(ZonedSchedule):
    kind: Literal["timed"] = "timed"
    start_at: AwareDatetime = Field(description=_("Inclusive aware instant, normalized to UTC."))
    end_at: AwareDatetime = Field(
        description=_("Exclusive aware instant after start_at, normalized to UTC.")
    )

    @model_validator(mode="after")
    def validate_instants(self):
        zone = calendar_zone(self.timezone)
        for value in (self.start_at, self.end_at):
            # UTC denotes an unambiguous instant. Non-UTC input must match its named wall zone.
            local = value.astimezone(zone)
            if value.utcoffset() != timedelta(0) and (
                local.replace(tzinfo=None) != value.replace(tzinfo=None)
                or local.utcoffset() != value.utcoffset()
            ):
                raise ValueError("Nonexistent wall time or timezone offset mismatch")
        if self.end_at <= self.start_at or self.end_at - self.start_at > timedelta(days=366):
            raise ValueError("End must follow start by at most 366 days")
        self.start_at, self.end_at = self.start_at.astimezone(UTC), self.end_at.astimezone(UTC)
        return self


class AllDaySchedule(ZonedSchedule):
    kind: Literal["all_day"] = "all_day"
    start_date: date = Field(
        description=_("Inclusive Gregorian date; no conversion into a timed event.")
    )
    end_date: date = Field(description=_("Exclusive Gregorian end date."))

    @model_validator(mode="after")
    def validate_dates(self):
        if not 0 < (self.end_date - self.start_date).days <= 366:
            raise ValueError("Exclusive end must follow start by at most 366 days")
        day_instant(self.start_date, self.timezone)
        day_instant(self.end_date, self.timezone)
        return self


class DeadlineSchedule(BaseDTO):
    kind: Literal["deadline"] = "deadline"
    due_at: AwareDatetime
    timezone: str


EventSchedule = Annotated[TimedSchedule | AllDaySchedule, Field(discriminator="kind")]
CalendarSchedule = Annotated[
    TimedSchedule | AllDaySchedule | DeadlineSchedule, Field(discriminator="kind")
]


ReminderOffset = Annotated[int, Field(strict=True, ge=0, le=2592000)]


class CalendarInput(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "command_key": "meeting-create-1",
                    "title": "Team meeting",
                    "schedule": {
                        "kind": "timed",
                        "start_at": "2028-02-29T10:00:00+04:00",
                        "end_at": "2028-02-29T11:00:00+04:00",
                        "timezone": "Asia/Dubai",
                    },
                    "work_group_ref_id": None,
                    "reminder_offsets": [900],
                },
                {
                    "command_key": "date-create-1",
                    "title": "Leap day",
                    "schedule": {
                        "kind": "all_day",
                        "start_date": "2028-02-29",
                        "end_date": "2028-03-01",
                        "timezone": "UTC",
                    },
                    "reminder_offsets": [],
                },
            ]
        },
    )
    command_key: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=120)
    schedule: EventSchedule
    work_group_ref_id: str | None = Field(
        default=None,
        max_length=512,
        description=_("Current authorized team reference; null creates a personal event."),
    )
    reminder_offsets: list[ReminderOffset] = Field(
        default_factory=list,
        max_length=3,
        description=_(
            "Seconds before start; up to three distinct integers from zero to thirty days. Empty disables reminders."
        ),
    )

    @field_validator("reminder_offsets")
    @classmethod
    def valid_offsets(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)) or any(
            isinstance(item, bool) or not 0 <= item <= 2592000 for item in value
        ):
            raise ValueError("Up to three distinct offsets from zero to thirty days")
        return sorted(value)


class CalendarItemDTO(BaseDTO):
    ref_id: str
    source_kind: Literal["manual", "work_item"]
    title: str
    schedule: CalendarSchedule
    editable: bool
    route_key: Literal["calendar_events", "work_items"]
    work_group_ref_id: str | None = None


class CalendarQuery(SearchRequest):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "start_date": "2028-02-01",
                    "end_date": "2028-03-01",
                    "timezone": "Asia/Dubai",
                    "page": 1,
                    "size": 20,
                    "include_work_deadlines": True,
                    "filters": [],
                    "sort_orders": [],
                }
            ]
        },
    )
    __query_fields__: ClassVar[dict[str, Any]] = {
        "title": str,
        "kind": str,
        "source_kind": str,
        "sort_at": datetime,
    }
    start_date: date
    end_date: date
    timezone: str = Field(default="UTC", max_length=64)
    include_work_deadlines: bool = True

    @model_validator(mode="after")
    def valid_window(self):
        day_instant(self.start_date, self.timezone)
        day_instant(self.end_date, self.timezone)
        if not 0 < (self.end_date - self.start_date).days <= 93:
            raise ValueError("Half-open range must span one to ninety-three dates")
        if len(self.filters) > 20 or len(self.sort_orders) > 10:
            raise ValueError("Calendar query exceeds bounds")
        return self


class CalendarHistoryDTO(BaseDTO):
    changed_at: datetime
    operation: str


class ReminderInput(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"command_key": "deadline-reminders-1", "offsets": [0, 3600]}]
        },
    )
    command_key: str = Field(min_length=1, max_length=128)
    offsets: list[ReminderOffset] = Field(min_length=1, max_length=3)

    @field_validator("offsets")
    @classmethod
    def valid_offsets(cls, value: list[int]) -> list[int]:
        return CalendarInput.valid_offsets(value)


class ReminderDTO(BaseDTO):
    ref_id: str
    due_at: AwareDatetime
    status: Literal["PENDING", "SENT", "CANCELLED", "EXPIRED"]
