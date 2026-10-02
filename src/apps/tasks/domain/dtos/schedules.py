from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from core.ref_id import create_ref_id
from utils.pagination import SearchRequest, auto_query_model


class PeriodicTaskCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=255, description=_("Unique schedule name."))
    task_name: str = Field(max_length=255, description=_("Registered Celery task name."))
    queue: str | None = Field(default=None, max_length=255, description=_("Destination queue."))
    schedule_type: Literal["interval", "crontab", "clocked"]
    interval_seconds: float | None = Field(default=None, gt=0)
    cron_minute: str | None = None
    cron_hour: str | None = None
    cron_day_of_week: str | None = None
    cron_day_of_month: str | None = None
    cron_month_of_year: str | None = None
    clocked_at: datetime | None = None
    args: list[object] = Field(default_factory=list)
    kwargs: dict[str, object] = Field(default_factory=dict)
    enabled: bool = True
    one_off: bool = False
    start_at: datetime | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> PeriodicTaskCreateDTO:
        if self.schedule_type == "interval" and self.interval_seconds is None:
            raise ValueError("interval_seconds is required for an interval schedule")
        if self.schedule_type == "clocked" and self.clocked_at is None:
            raise ValueError("clocked_at is required for a clocked schedule")
        if self.schedule_type == "clocked" and not self.one_off:
            raise ValueError("clocked schedules must be one_off")
        return self


class PeriodicTaskDTO(PeriodicTaskCreateDTO):
    model_config = ConfigDict(from_attributes=True, extra="forbid", populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned schedule reference."),
    )
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None

    last_run_at: datetime | None
    total_run_count: int

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
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    queue: str | None = Field(default=None, max_length=255)
    interval_seconds: float | None = Field(default=None, gt=0)
    start_at: datetime | None = None
    expires_at: datetime | None = None
