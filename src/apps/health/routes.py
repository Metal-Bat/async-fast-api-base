from fastapi import APIRouter, HTTPException, Request

from apps.health.service import CHECKS, DependencyHealth, HealthReport, _timed, readiness
from utils.base_schema import response_schema
from utils.presenter import SuccessResponse, success_response

router = APIRouter(responses=response_schema(), tags=["health"])


@router.get("/health")
async def liveness(
    request: Request,
) -> SuccessResponse[dict[str, str]]:
    """Report that the API process and event loop are responsive."""
    return success_response(request, {"status": "alive"}, code=200)


@router.get("/ready", response_model=SuccessResponse[HealthReport])
async def ready(
    request: Request,
) -> SuccessResponse[HealthReport]:
    """Report readiness of all required internal dependencies."""
    report = await readiness()
    if report.status != "ready":
        raise HTTPException(status_code=503, detail=report.model_dump())
    return success_response(request, report, code=200)


@router.get("/internal/{service_name}", response_model=SuccessResponse[DependencyHealth])
async def internal_health(request: Request, service_name: str) -> SuccessResponse[DependencyHealth]:
    """Run one internal dependency check for infrastructure probes."""
    check = CHECKS.get(service_name)
    if check is None:
        raise HTTPException(status_code=404, detail="Unknown internal service")
    result = await _timed(check)
    if result.status != "up":
        raise HTTPException(status_code=503, detail=result.model_dump())
    return success_response(request, result, code=200)
