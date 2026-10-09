"""Readiness reports never promote unknown dependencies or expose probe errors."""

import anyio
import pytest

from apps.health.setup import SetupCheck, SetupReport, probe_check
from main import app


def test_required_unknown_is_not_ready_but_optional_unknown_is_allowed():
    check = SetupCheck(
        key="worker",
        required=True,
        status="unknown",
        reason="operator_probe_required",
        repair_key="operations",
    )
    assert SetupReport.from_checks([check]).status == "unknown"
    assert SetupReport.from_checks([check.model_copy(update={"required": False})]).status == "ready"
    assert (
        SetupReport.from_checks([check.model_copy(update={"status": "blocked"})]).status
        == "blocked"
    )


@pytest.mark.anyio
async def test_timeout_and_exception_details_are_private():
    async def timeout():
        await anyio.sleep(1)

    async def fails():
        raise ValueError("private host and credentials")

    for check in (timeout, fails):
        result = await probe_check("storage", check, timeout=0.01)
        assert result.status == "unknown"
        assert "private" not in result.model_dump_json()
        assert result.repair_key == "operations"


def test_setup_route_is_authenticated_and_private():
    operation = app.openapi()["paths"]["/api/v1/setup/readiness"]["get"]
    assert operation["security"]
    assert "Cache-Control" in operation["responses"]["200"]["headers"]
