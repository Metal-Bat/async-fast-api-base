"""Aggregate fixed populations using the same owned predicates as their drill-down lists."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, case, extract, func, literal
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.reporting.domain.analytics import (
    MetricBucket,
    MetricDefinition,
    MetricDrilldown,
    MetricQuery,
    MetricResult,
    MetricSeries,
    metric_window,
)
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import BusinessRequestQuery
from apps.requests.domain.entity import BusinessRequestEntity
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CartableQueryDTO
from apps.work_items.domain.entity import WorkItemEntity
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException
from utils.pagination import FilterCriteria, FilterOperation, apply_query

_DEFINITIONS = (
    MetricDefinition(
        metric_key="submitted_requests",
        unit="count",
        timestamp="submitted_at",
        population="Live requests owned by me with an actual submission timestamp, including cancelled terminal requests.",
    ),
    MetricDefinition(
        metric_key="active_requests",
        unit="count",
        timestamp="created_at",
        population="Live requests owned by me currently SUBMITTED or RUNNING; current-state cohort, not historical occupancy.",
    ),
    MetricDefinition(
        metric_key="available_work",
        unit="count",
        timestamp="created_at",
        population="My currently claimable OPEN work, excluding my archived items; same live direct/group cartable policy.",
    ),
    MetricDefinition(
        metric_key="claimed_work",
        unit="count",
        timestamp="created_at",
        population="My currently CLAIMED or IN_PROGRESS work, excluding my archived items.",
    ),
    MetricDefinition(
        metric_key="overdue_work",
        unit="count",
        timestamp="created_at",
        population="My currently claimable OPEN work with a non-null deadline strictly before as_of; unclaimed and unarchived.",
    ),
    MetricDefinition(
        metric_key="terminal_duration",
        unit="seconds",
        timestamp="closed_at",
        population="Mean submission-to-close duration of my live COMPLETED/FAILED/CANCELLED requests. Missing or negative timing is unknown, excluded from mean and included in population_count.",
    ),
    MetricDefinition(
        metric_key="correction_frequency",
        unit="count",
        timestamp="closed_at",
        population="My live terminal RETURNED work items; counts actual return decisions, not rejected/failed or inferred outcomes. Archived items excluded.",
    ),
    MetricDefinition(
        metric_key="integration_outcomes",
        unit="count",
        timestamp=None,
        availability="unavailable",
        population="No business-effect receipt registry has been delivered.",
        reason="receipt_metric_not_configured",
    ),
    MetricDefinition(
        metric_key="business_outcomes",
        unit="count",
        timestamp=None,
        availability="unavailable",
        population="Completion status is not business approval.",
        reason="business_outcome_mapping_not_configured",
    ),
)


def metric_catalog() -> list[MetricDefinition]:
    return [item.model_copy(deep=True) for item in _DEFINITIONS]


def _filter(name: str, operation: FilterOperation, value: Any) -> FilterCriteria:
    return FilterCriteria(field_name=name, operation=operation, value=value)


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def source(
        self, query: MetricQuery, actor: UserEntity, as_of: datetime, *, status: str | None = None
    ) -> tuple[Select[Any], Any, MetricDrilldown]:
        """Build only registered owner queries; no caller-provided SQL or actor identity."""
        start, end = metric_window(query)
        if query.metric_key in {"submitted_requests", "active_requests", "terminal_duration"}:
            stamp_name = {
                "submitted_requests": "submitted_at",
                "active_requests": "created_at",
                "terminal_duration": "closed_at",
            }[query.metric_key]
            stamp = getattr(BusinessRequestEntity, stamp_name)
            filters = [
                _filter(stamp_name, FilterOperation.GTE, start),
                _filter(stamp_name, FilterOperation.LT, end),
            ]
            if query.metric_key == "active_requests":
                filters.append(_filter("status", FilterOperation.IN, ["SUBMITTED", "RUNNING"]))
            if query.metric_key == "terminal_duration":
                filters.append(
                    _filter("status", FilterOperation.IN, ["COMPLETED", "FAILED", "CANCELLED"])
                )
            if status is not None:
                filters.append(_filter("status", FilterOperation.EQUAL, status))
            request_query = BusinessRequestQuery(scope="mine", filters=filters)
            statement = select(BusinessRequestEntity).where(
                col(BusinessRequestEntity.deleted_at).is_(None),
                *RequestService(self.session).visibility_criteria(actor, mine=True),
            )
            statement = apply_query(statement, BusinessRequestEntity, request_query, paginate=False)
            return statement, stamp, MetricDrilldown(route_key="requests", query=request_query)
        cartable = "claimed" if query.metric_key == "claimed_work" else "available"
        if query.metric_key == "correction_frequency":
            cartable = "completed"
        work_query = CartableQueryDTO.model_validate(
            {
                "cartable": cartable,
                "time_field": "closed_at"
                if query.metric_key == "correction_frequency"
                else "created_at",
                "after": start,
                "before": end,
                "overdue_before": as_of if query.metric_key == "overdue_work" else None,
                "status": "RETURNED" if query.metric_key == "correction_frequency" else status,
            }
        )
        stamp = (
            col(WorkItemEntity.closed_at)
            if work_query.time_field == "closed_at"
            else col(WorkItemEntity.created_at)
        )
        statement = select(WorkItemEntity).where(
            *WorkItemService(self.session).search_criteria(work_query, actor)
        )
        return statement, stamp, MetricDrilldown(route_key="work_items", query=work_query)

    async def query(self, query: MetricQuery, actor: UserEntity) -> MetricResult:
        current = await self.session.get(UserEntity, actor.id, populate_existing=True)
        if current is None or current.deleted_at is not None:
            raise NotAllowedException("Inactive metric actor")
        permissions = await user_permissions(current, self.session)
        if "*" not in permissions and "requests.start" not in permissions:
            raise NotAllowedException("Request read permission required")
        definition = next(item for item in _DEFINITIONS if item.metric_key == query.metric_key)
        as_of = get_datetime_utc()
        result = MetricResult(
            metric_key=query.metric_key,
            unit=definition.unit,
            availability=definition.availability,
            reason=definition.reason,
            generated_at=as_of,
            as_of=as_of,
            timezone=query.timezone,
        )
        if definition.availability == "unavailable":
            return result
        statement, stamp, drilldown = self.source(query, current, as_of)
        status = (
            col(BusinessRequestEntity.status)
            if drilldown.route_key == "requests"
            else col(WorkItemEntity.status)
        )
        bucket = func.date_trunc("day", func.timezone(query.timezone, stamp))
        key = status if query.dimension == "status" else literal("all")
        count = func.count()
        if query.metric_key == "terminal_duration":
            seconds = extract(
                "epoch",
                col(BusinessRequestEntity.closed_at) - col(BusinessRequestEntity.submitted_at),
            )
            valid = case((seconds >= 0, seconds), else_=None)
            samples, value = func.count(valid), func.avg(valid)
        else:
            samples, value = count, count
        criterion = statement.whereclause
        if criterion is None:
            raise RuntimeError("Metric population requires an owner predicate")
        aggregate = (
            select(bucket, key, count, func.json_build_array(samples, value))
            .where(criterion)
            .group_by(bucket, key)
        )
        rows = (await self.session.exec(aggregate)).all()
        values = {
            (row[0].date(), row[1]): (
                int(row[2]),
                int(row[3][0]),
                float(row[3][1]) if row[3][1] is not None else None,
            )
            for row in rows
        }
        keys = sorted({row[1] for row in rows}) or ["all"]
        result.population_count = sum(item[0] for item in values.values())
        result.sample_count = sum(item[1] for item in values.values())
        result.unknown_count = result.population_count - result.sample_count
        if definition.unit == "count":
            result.total_value = float(result.population_count)
        elif result.sample_count:
            result.total_value = (
                sum((item[2] or 0) * item[1] for item in values.values()) / result.sample_count
            )
        result.drilldown = drilldown
        for series_key in keys:
            buckets = []
            for offset in range((query.end_date - query.start_date).days):
                day = query.start_date + timedelta(days=offset)
                population, sample, value = values.get(
                    (day, series_key), (0, 0, 0.0 if definition.unit == "count" else None)
                )
                bucket_query = query.model_copy(
                    update={"start_date": day, "end_date": day + timedelta(days=1)}
                )
                _, _, descriptor = self.source(
                    bucket_query,
                    current,
                    as_of,
                    status=series_key
                    if query.dimension == "status" and series_key != "all"
                    else None,
                )
                buckets.append(
                    MetricBucket(
                        date=day,
                        value=value,
                        population_count=population,
                        sample_count=sample,
                        unknown_count=population - sample,
                        drilldown=descriptor,
                    )
                )
            result.series.append(MetricSeries(key=series_key, buckets=buckets))
        return result
