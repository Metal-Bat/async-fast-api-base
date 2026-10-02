"""Administrative recovery validates intent before touching runtime state."""

from uuid import uuid7

import pytest
from pydantic import ValidationError

from apps.processes.application.recovery import ProcessRecoveryService
from apps.processes.domain.dto import RecoveryCommandDTO
from apps.users.domain.entity import UserEntity
from main import app
from utils.exceptions import NotAllowedException


@pytest.mark.parametrize("reason", ["", "   ", "x" * 65, "contains secret text"])
def test_recovery_requires_a_bounded_reason_code(reason: str) -> None:
    with pytest.raises(ValidationError):
        RecoveryCommandDTO(command_key="incident-1", action="resume", reason=reason)


@pytest.mark.anyio
async def test_recovery_rejects_non_administrator_before_reading_process() -> None:
    actor = UserEntity(id=uuid7(), username="operator", hashed_password="unused")
    service = ProcessRecoveryService(None)  # ty:ignore[invalid-argument-type]
    with pytest.raises(NotAllowedException):
        await service.recover(
            "opaque",
            RecoveryCommandDTO(command_key="incident", action="resume", reason="incident"),
            actor,
        )


def test_recovery_route_exposes_required_snake_case_intent() -> None:
    schema = app.openapi()
    assert "post" in schema["paths"]["/api/v1/processes/{ref_id}/recover"]
    assert "post" in schema["paths"]["/api/v1/processes/{ref_id}/scheduled-actions/search"]
    dto = schema["components"]["schemas"]["RecoveryCommandDTO"]
    assert {"command_key", "reason", "action"} <= set(dto["required"])
