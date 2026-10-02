"""Tests for application readiness aggregation."""

import pytest

from apps.health import service as health


@pytest.mark.anyio
async def test_readiness_aggregates_dependency_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Readiness becomes unavailable when any required dependency fails."""

    async def healthy() -> None:
        return None

    async def unhealthy() -> None:
        raise ConnectionError

    monkeypatch.setattr(health, "CHECKS", {"postgres": healthy, "cache": unhealthy})
    report = await health.readiness()
    assert report.status == "not_ready"
    assert report.services["postgres"].status == "up"
    assert report.services["cache"].status == "down"
