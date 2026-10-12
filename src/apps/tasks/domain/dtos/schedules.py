from datetime import datetime
from math import isfinite
from typing import Any, Literal

from celery.schedules import crontab
from pydantic import AliasChoices, ConfigDict, Field, field_validator, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from core.ref_id import create_ref_id
from utils.pagination import SearchRequest, auto_query_model


class PeriodicTaskFieldsDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=255, description=_("Unique schedule name."))
    task_name: str = Field(max_length=255, description=_("Registered Celery task name."))
    queue: str | None = Field(default=None, max_length=255, description=_("Destination queue."))
    schedule_type: Literal["interval", "crontab", "clocked"] = Field(
        description=_(
            "Schedule variant. Only fields belonging to this variant may be supplied on writes."
        )
    )
    interval_seconds: float | None = Field(
        default=None,
        gt=0,
        description=_(
            "Positive interval in seconds; required only for interval schedules. Retained legacy reads may be null."
        ),
    )
    cron_minute: str | None = Field(
        default=None,
        description=_(
            "Celery cron minute expression; null defaults to * for crontab schedules and must be absent for other variants."
        ),
    )
    cron_hour: str | None = Field(
        default=None,
        description=_(
            "Celery cron hour expression; null defaults to * for crontab schedules and must be absent for other variants."
        ),
    )
    cron_day_of_week: str | None = Field(
        default=None,
        description=_(
            "Celery cron day of week expression; null defaults to * for crontab schedules and must be absent for other variants."
        ),
    )
    cron_day_of_month: str | None = Field(
        default=None,
        description=_(
            "Celery cron day of month expression; null defaults to * for crontab schedules and must be absent for other variants."
        ),
    )
    cron_month_of_year: str | None = Field(
        default=None,
        description=_(
            "Celery cron month of year expression; null defaults to * for crontab schedules and must be absent for other variants."
        ),
    )
    clocked_at: datetime | None = Field(
        default=None,
        description=_(
            "Timezone-aware execution instant; required only for clocked one-off schedules."
        ),
    )
    args: list[object] = Field(
        default_factory=list,
        description=_(
            "JSON positional arguments bound to the registered task signature before saving."
        ),
    )
    kwargs: dict[str, object] = Field(
        default_factory=dict,
        description=_(
            "JSON keyword arguments bound to the registered task signature before saving."
        ),
    )
    enabled: bool = Field(
        default=True,
        description=_(
            "Whether the scheduler may dispatch this row; false pauses it without deleting history."
        ),
    )
    one_off: bool = Field(
        default=False,
        description=_(
            "Whether the schedule disables itself after dispatch; clocked schedules require true."
        ),
    )
    start_at: datetime | None = Field(
        default=None,
        description=_(
            "Optional timezone-aware lower execution bound; omitted preserves it on update, null clears it."
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        description=_(
            "Optional timezone-aware expiry after start and clocked instant; omitted preserves it on update, null clears it."
        ),
    )


class PeriodicTaskCreateDTO(PeriodicTaskFieldsDTO):
    """Write validation is intentionally separate from retained schedule reads."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "health-interval",
                    "task_name": "system.ping",
                    "schedule_type": "interval",
                    "interval_seconds": 60,
                },
                {
                    "name": "health-cron",
                    "task_name": "system.ping",
                    "schedule_type": "crontab",
                    "cron_minute": "*/5",
                },
                {
                    "name": "health-once",
                    "task_name": "system.ping",
                    "schedule_type": "clocked",
                    "clocked_at": "2026-12-01T12:00:00Z",
                    "one_off": True,
                },
            ]
        },
    )

    @model_validator(mode="after")
    def validate_schedule(self) -> PeriodicTaskCreateDTO:
        if self.interval_seconds is not None and not isfinite(self.interval_seconds):
            raise ValueError("interval_seconds must be finite")
        for name in ("clocked_at", "start_at", "expires_at"):
            instant = getattr(self, name)
            if instant is not None and instant.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone")
        if self.start_at and self.expires_at and self.expires_at <= self.start_at:
            raise ValueError("expires_at must be after start_at")
        cron_names = (
            "cron_minute",
            "cron_hour",
            "cron_day_of_week",
            "cron_day_of_month",
            "cron_month_of_year",
        )
        if self.schedule_type != "interval" and self.interval_seconds is not None:
            raise ValueError("interval_seconds belongs only to interval schedules")
        if self.schedule_type != "clocked" and self.clocked_at is not None:
            raise ValueError("clocked_at belongs only to clocked schedules")
        if self.schedule_type != "crontab" and any(
            getattr(self, name) is not None for name in cron_names
        ):
            raise ValueError("cron fields belong only to crontab schedules")
        if self.schedule_type == "interval" and self.interval_seconds is None:
            raise ValueError("interval_seconds is required for an interval schedule")
        if self.schedule_type == "crontab":
            crontab(
                **{name.removeprefix("cron_"): getattr(self, name) or "*" for name in cron_names}
            )
        if self.schedule_type == "clocked" and self.clocked_at is None:
            raise ValueError("clocked_at is required for a clocked schedule")
        if self.schedule_type == "clocked" and not self.one_off:
            raise ValueError("clocked schedules must be one_off")
        if self.clocked_at and self.expires_at and self.expires_at <= self.clocked_at:
            raise ValueError("expires_at must be after clocked_at")
        return self


class PeriodicTaskDTO(PeriodicTaskFieldsDTO):
    model_config = ConfigDict(from_attributes=True, extra="forbid", populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned schedule reference."),
    )
    created_at: datetime = Field(description=_("UTC creation instant of the persisted schedule."))
    updated_at: datetime | None = Field(
        description=_("UTC instant of the most recent change, or null before the first change.")
    )
    deleted_at: datetime | None = Field(
        description=_("UTC soft-deletion instant, or null for a retained active configuration.")
    )

    last_run_at: datetime | None = Field(
        description=_(
            "UTC instant of the most recent scheduler dispatch, or null before any dispatch."
        )
    )
    total_run_count: int = Field(
        description=_("Number of scheduler dispatches recorded for this schedule.")
    )

    @model_validator(mode="before")
    @classmethod
    def create_public_reference(cls, value: Any) -> Any:
        if isinstance(value, dict):
            data = value.copy()
            if "refId" not in data and "ref_id" not in data:
                data["ref_id"] = create_ref_id(data.pop("id"), data.pop("version"))
            return data
        return {field: getattr(value, field) for field in cls.model_fields if field != "ref_id"} | {
            "ref_id": create_ref_id(value.id, value.version)
        }


class PeriodicTaskQuery(SearchRequest):
    __query_fields__ = auto_query_model(
        PeriodicTaskDTO, exclude={"ref_id", "args", "kwargs"}
    ).__query_fields__


class PeriodicTaskUpdateDTO(BaseDTO):
    """Partial command: omission preserves; enabled and interval reject explicit null."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = Field(
        default=None,
        description=_(
            "Whether the scheduler may dispatch this row; false pauses it without deleting history."
        ),
    )
    queue: str | None = Field(
        default=None,
        max_length=255,
        description=_(
            "Configured queue choice; omitted preserves it on update, null uses the scheduler default."
        ),
    )
    interval_seconds: float | None = Field(
        default=None,
        gt=0,
        description=_(
            "Positive interval in seconds; required only for interval schedules. Retained legacy reads may be null."
        ),
    )
    start_at: datetime | None = Field(
        default=None,
        description=_(
            "Optional timezone-aware lower execution bound; omitted preserves it on update, null clears it."
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        description=_(
            "Optional timezone-aware expiry after start and clocked instant; omitted preserves it on update, null clears it."
        ),
    )

    @field_validator("enabled", "interval_seconds")
    @classmethod
    def reject_explicit_null(cls, value):
        if value is None:
            raise ValueError("Omit this field to preserve it; explicit null is not supported")
        return value
