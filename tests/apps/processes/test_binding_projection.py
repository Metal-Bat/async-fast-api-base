"""Declared prior-output paths project exact values without changing the saved snapshot."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.processes.application.service import ProcessService
from apps.workflows.domain.entity import WorkflowStepInputBindingEntity


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("pointer", "expected"),
    [
        (None, {"rows": [{"amount": "0.00", "approved": False}], "a/b": {"~key": None}}),
        ("/rows/0/amount", "0.00"),
        ("/rows/0/approved", False),
        ("/a~1b/~0key", None),
    ],
)
async def test_prior_output_projects_the_declared_pointer_without_mutating_snapshot(
    pointer, expected
):
    output = {"rows": [{"amount": "0.00", "approved": False}], "a/b": {"~key": None}}
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(port_key="result")
    rows = Mock()
    rows.one_or_none.return_value = SimpleNamespace(output_snapshot={"result": output})
    session.exec.return_value = rows
    binding = WorkflowStepInputBindingEntity(
        workflow_step_id=uuid7(),
        target_port_id=uuid7(),
        source_kind="STEP_OUTPUT",
        source_step_id=uuid7(),
        source_port_id=uuid7(),
        source_path=pointer,
    )

    result = await ProcessService(session)._step_output(uuid7(), binding)

    assert result == expected
    assert output == {"rows": [{"amount": "0.00", "approved": False}], "a/b": {"~key": None}}


@pytest.mark.anyio
async def test_missing_prior_output_field_fails_instead_of_returning_the_whole_port():
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(port_key="result")
    rows = Mock()
    rows.one_or_none.return_value = SimpleNamespace(output_snapshot={"result": {"public": 0}})
    session.exec.return_value = rows
    binding = WorkflowStepInputBindingEntity(
        workflow_step_id=uuid7(),
        target_port_id=uuid7(),
        source_kind="STEP_OUTPUT",
        source_step_id=uuid7(),
        source_port_id=uuid7(),
        source_path="/missing",
    )

    with pytest.raises(KeyError):
        await ProcessService(session)._step_output(uuid7(), binding)
