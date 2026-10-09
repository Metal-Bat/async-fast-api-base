"""Fixed actor-authorized business metrics with private chart-neutral responses."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from apps.reporting.application.analytics import AnalyticsService, metric_catalog
from apps.reporting.domain.analytics import MetricDefinition, MetricQuery, MetricResult
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.deps import SessionDep
from core.i18n import _
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.presenter import SuccessResponse, private_no_store, success_response

router = APIRouter(prefix="/analytics", tags=["reports"], responses=response_schema())
MetricUser = Annotated[UserEntity, Depends(RequirePermission("requests.start"))]


@router.get(
    "/catalog",
    response_model=SuccessResponse[list[MetricDefinition]],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Read the registered business metric dictionary"),
    description=_(
        "Requires requests.start. Returns versioned units, exact populations, timestamp and explicit unavailable reasons. No arbitrary SQL, monetary sum or inferred business approval is exposed. Private no-store success envelope."
    ),
)
async def catalog(request: Request, response: Response, actor: MetricUser):
    private_no_store(response)
    return success_response(request, metric_catalog())


@router.post(
    "/query",
    response_model=SuccessResponse[MetricResult],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Aggregate authorized business metrics"),
    description=_(
        "Requires requests.start and a live actor. Uses the registered metric's owner predicates "
        "before aggregation, never a first result page. Requests are requester-owned; work uses "
        "the same direct/group/archive cartable policy as list search. Accepts an exclusive end "
        "civil date, 1–366 day window, valid IANA timezone, day granularity and only none/status "
        "dimensions. DST boundaries are exact UTC instants; nonexistent midnights fail 422. "
        "Returns unit, as_of, generated_at, typed buckets and drill-down descriptors accepted by "
        "existing request/work-item searches. Current-state metrics are snapshots, not historical "
        "occupancy. Live soft-deleted records are excluded. Null or negative terminal timing is "
        "unknown and excluded from mean; unknown_count remains explicit. Integration receipts "
        "and business outcomes without configured mappings return unavailable with null totals, "
        "never false zeros. No shared cache, credentials or private submission values. Empty count "
        "populations return zero; empty duration populations return null. Private no-store envelope."
    ),
)
async def query_metrics(
    request: Request, query: MetricQuery, response: Response, actor: MetricUser, session: SessionDep
) -> SuccessResponse[MetricResult]:
    result = await AnalyticsService(session).query(query, actor)
    private_no_store(response)
    return success_response(request, result)
