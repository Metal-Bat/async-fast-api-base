"""Small chart-neutral metrics with explicit populations and bounded calendar buckets."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ConfigDict, Field, field_validator, model_validator

from apps.requests.domain.dto import BusinessRequestQuery
from apps.work_items.domain.dto import CartableQueryDTO
from core.base_dto import BaseDTO
from core.i18n import _

type MetricKey = Literal[
    "submitted_requests",
    "active_requests",
    "available_work",
    "claimed_work",
    "overdue_work",
    "terminal_duration",
    "correction_frequency",
    "integration_outcomes",
    "business_outcomes",
]


class MetricQuery(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    metric_key: MetricKey
    start_date: date = Field(description=_("Inclusive civil date in the requested IANA timezone."))
    end_date: date = Field(
        description=_("Exclusive civil date; at most 366 days after start_date.")
    )
    timezone: str = Field(default="UTC", max_length=128)
    granularity: Literal["day"] = "day"
    dimension: Literal["none", "status"] = "none"

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def bounded_window(self):
        if not 1 <= (self.end_date - self.start_date).days <= 366:
            raise ValueError("Metric range must contain 1 to 366 civil days")
        metric_window(self)
        # Every per-day drill-down must have valid boundaries, including skipped civil days.
        zone = ZoneInfo(self.timezone)
        for offset in range((self.end_date - self.start_date).days):
            day = self.start_date + timedelta(days=offset)
            local = datetime.combine(day, time.min, zone)
            if local.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local.replace(
                tzinfo=None
            ):
                raise ValueError("Metric bucket is a nonexistent local midnight")
        return self


def metric_window(query: MetricQuery) -> tuple[datetime, datetime]:
    """Convert civil midnights to exact UTC instants and refuse nonexistent boundaries."""
    zone = ZoneInfo(query.timezone)
    values = []
    for day in (query.start_date, query.end_date):
        local = datetime.combine(day, time.min, zone)
        utc = local.astimezone(UTC)
        if utc.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
            raise ValueError("Metric boundary is a nonexistent local midnight")
        values.append(utc)
    return values[0], values[1]


class MetricDefinition(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    metric_key: MetricKey
    version: Literal[1] = 1
    unit: Literal["count", "seconds"]
    population: str
    timestamp: str | None
    availability: Literal["available", "unavailable"] = "available"
    reason: str | None = None


class MetricDrilldown(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    route_key: Literal["requests", "work_items"]
    query: BusinessRequestQuery | CartableQueryDTO


class MetricBucket(BaseDTO):
    date: date
    value: float | None
    population_count: int = Field(ge=0)
    sample_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    drilldown: MetricDrilldown


class MetricSeries(BaseDTO):
    key: str
    buckets: list[MetricBucket] = Field(max_length=366)


class MetricResult(BaseDTO):
    metric_key: MetricKey
    version: Literal[1] = 1
    unit: Literal["count", "seconds"]
    availability: Literal["available", "unavailable"]
    reason: str | None = None
    generated_at: datetime
    as_of: datetime
    timezone: str
    series: list[MetricSeries] = Field(default_factory=list, max_length=8)
    population_count: int | None = Field(default=None, ge=0)
    sample_count: int | None = Field(default=None, ge=0)
    unknown_count: int | None = Field(default=None, ge=0)
    total_value: float | None = None
    drilldown: MetricDrilldown | None = None
