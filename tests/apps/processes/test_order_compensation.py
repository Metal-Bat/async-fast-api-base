"""An unresolved external order cannot be silently labeled compensated."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.processes.application.compensation import CompensationService
from apps.processes.application.events import ProcessEventService
from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionAttemptEntity
from utils.exceptions import VersionConflictException


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["DISPATCHING", "UNKNOWN", "CONFIRMED"])
async def test_compensation_without_supported_reversal_cannot_hide_external_order(
    monkeypatch, state
):
    process = ProcessInstanceEntity(
        id=uuid7(), business_request_id=uuid7(), workflow_version_id=uuid7(), status="CANCELLED"
    )
    attempt = StepExecutionAttemptEntity(
        id=uuid7(),
        step_execution_id=uuid7(),
        number=1,
        dispatch_key="test",
        status="CANCELLED",
        automation_snapshot={
            "operation_key": "sandbox.order.create/1",
            "order_dispatch": {"state": state},
        },
    )

    async def execute(statement):
        entity = statement.column_descriptions[0]["entity"]
        return Mock(
            one_or_none=Mock(return_value=attempt if entity is StepExecutionAttemptEntity else None)
        )

    session = Mock(get=AsyncMock(return_value=process), exec=AsyncMock(side_effect=execute))
    monkeypatch.setattr(ProcessEventService, "append", AsyncMock())
    with pytest.raises(VersionConflictException, match="reconciliation|reversal"):
        await CompensationService(session).begin(process.id, "reverse", uuid7())
    assert process.status == "CANCELLED"
