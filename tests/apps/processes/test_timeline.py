"""Process event redaction and public timeline contract."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.processes.application import events
from apps.processes.application.events import ProcessEventService, public_event_payload
from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
from main import app
from utils.date_utils import get_datetime_utc


def test_public_event_payload_is_allowlisted_redacted_and_bounded() -> None:
    payload = public_event_payload(
        "work_item.completed",
        {
            "action": "complete",
            "outcome": "approve",
            "status": "COMPLETED",
            "data": {"national_id": "secret form value"},
            "access_token": "secret",
            "comment": "x" * 5000,
        },
    )

    assert payload == {
        "action": "complete",
        "outcome": "approve",
        "status": "COMPLETED",
    }


def test_process_routes_expose_paginated_timeline_and_report() -> None:
    schema = app.openapi()
    paths = schema["paths"]

    assert "post" in paths["/api/v1/processes/{ref_id}/timeline"]
    assert "post" in paths["/api/v1/processes/{ref_id}/timeline/report"]
    timeline = schema["components"]["schemas"]["ProcessTimelineDTO"]["properties"]
    assert "current_positions" in timeline
    assert timeline["current_positions"]["type"] == "array"
    assert "events" in timeline
    process = schema["components"]["schemas"]["ProcessDTO"]["properties"]
    assert "current_positions" in process
    assert "current_step_key" not in process


@pytest.mark.anyio
async def test_terminal_event_records_duration_without_business_payload(monkeypatch) -> None:
    now = get_datetime_utc()
    process = ProcessInstanceEntity(
        id=uuid7(),
        business_request_id=uuid7(),
        workflow_version_id=uuid7(),
        started_at=now - timedelta(seconds=12),
    )
    execution = StepExecutionEntity(
        id=uuid7(),
        process_instance_id=process.id,
        execution_token_id=uuid7(),
        workflow_step_id=uuid7(),
        visit_number=1,
        status="FAILED",
        wait_kind="BACKGROUND",
        started_at=now - timedelta(seconds=3),
        ended_at=now,
    )
    session = AsyncMock()
    session.get.side_effect = [process, execution]
    session.add = Mock()
    telemetry = Mock()
    monkeypatch.setattr(events, "bpms_telemetry", telemetry)

    await ProcessEventService(session).append(
        process.id,
        "step.failed",
        step_execution_id=execution.id,
        payload={"error_code": "provider.secret.failure", "status": "FAILED"},
    )

    telemetry.record_process_event.assert_called_once()
    call = telemetry.record_process_event.call_args
    assert call.args == ("step.failed",)
    assert call.kwargs["process_started_at"] == process.started_at
    assert call.kwargs["step_started_at"] == execution.started_at
    assert call.kwargs["wait_kind"] == "BACKGROUND"
    assert "provider.secret.failure" not in repr(call)
