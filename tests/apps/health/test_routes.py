"""Tests for health presentation routes."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request

from apps.health import routes
from apps.health.service import HealthReport


def request_context() -> Request:
    return Request({"type": "http", "headers": []})


@pytest.mark.anyio
async def test_health_routes_return_and_raise_correct_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness and internal probes translate dependency state to HTTP status."""
    ready_report = HealthReport(status="ready", services={})
    monkeypatch.setattr(routes, "readiness", AsyncMock(return_value=ready_report))
    assert (await routes.liveness(request_context())).data == {"status": "alive"}
    assert (await routes.ready(request_context())).data == ready_report

    down_report = HealthReport(status="not_ready", services={})
    monkeypatch.setattr(routes, "readiness", AsyncMock(return_value=down_report))
    with pytest.raises(HTTPException) as unavailable:
        await routes.ready(request_context())
    assert unavailable.value.status_code == 503

    with pytest.raises(HTTPException) as missing:
        await routes.internal_health(request_context(), "missing")
    assert missing.value.status_code == 404

    async def healthy() -> None:
        return None

    monkeypatch.setitem(routes.CHECKS, "test", healthy)
    assert (await routes.internal_health(request_context(), "test")).data.status == "up"

    async def unhealthy() -> None:
        raise ConnectionError

    monkeypatch.setitem(routes.CHECKS, "test-down", unhealthy)
    with pytest.raises(HTTPException) as dependency_down:
        await routes.internal_health(request_context(), "test-down")
    assert dependency_down.value.status_code == 503
