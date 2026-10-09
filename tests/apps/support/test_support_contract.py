"""Support intake accepts only bounded safe facts; recording outages remain observable."""

from unittest.mock import AsyncMock, patch
from uuid import uuid7

import pytest
from pydantic import ValidationError

from apps.support.application.recorder import record_failure
from apps.support.domain.dto import ClientFailure


def test_client_intake_rejects_private_payloads_and_unknown_codes():
    values = {
        "screen_key": "calendar",
        "build": "demo.1",
        "error_code": "client.render_failed",
        "request_id": uuid7(),
    }
    assert ClientFailure.model_validate(values).screen_key == "calendar"
    for extra in ({"message": "private"}, {"error_code": "arbitrary"}, {"build": "x" * 81}):
        with pytest.raises(ValidationError):
            ClientFailure.model_validate(values | extra)


@pytest.mark.anyio
async def test_recorder_outage_never_escapes_or_invents_durability():
    with (
        patch(
            "apps.support.application.recorder._persist",
            new=AsyncMock(side_effect=RuntimeError("private")),
        ),
        patch("apps.support.application.recorder.logger") as log,
    ):
        assert (
            await record_failure(
                category="technical", error_code=1099, operation="api", request_id=uuid7()
            )
            is None
        )
        assert log.error.call_args.kwargs == {"durable": False, "code": 1099}


def test_support_http_is_authenticated_private_and_has_safe_actions():
    from main import app

    paths = app.openapi()["paths"]
    for path, method in (
        ("/api/v1/support/incidents/search", "post"),
        ("/api/v1/support/incidents/{ref_id}/acknowledge", "post"),
        ("/api/v1/support/client-failures", "post"),
    ):
        operation = paths[path][method]
        assert operation["security"]
        assert "Cache-Control" in operation["responses"]["200"]["headers"]
