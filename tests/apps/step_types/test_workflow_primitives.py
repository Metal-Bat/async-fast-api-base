"""Workflow construction blocks execute through the deployed registry."""

from dataclasses import replace
from unittest.mock import Mock
from uuid import UUID

import pytest

from apps.step_types.application.invocation import StepInvocationContext
from apps.step_types.application.registry import get_registry


def invocation(inputs):
    return StepInvocationContext(
        actor_id=UUID(int=1),
        process_id=UUID(int=2),
        request_id=UUID(int=3),
        execution_id=UUID(int=4),
        attempt_id=UUID(int=5),
        idempotency_key="primitive-test",
        inputs=inputs,
        services=Mock(),
        cancelled=lambda: False,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "handler,config,inputs,expected,outcome",
    [
        ("arithmetic", {"operation": "add"}, {"left": 4, "right": 3}, 7, None),
        ("arithmetic", {"operation": "subtract"}, {"left": 4, "right": 3}, 1, None),
        ("arithmetic", {"operation": "multiply"}, {"left": 4, "right": 3}, 12, None),
        ("arithmetic", {"operation": "divide"}, {"left": 7, "right": 2}, 3.5, None),
        ("arithmetic", {"operation": "remainder"}, {"left": 7, "right": 2}, 1, None),
        ("number_compare", {"operation": "gt"}, {"left": 4, "right": 3}, True, None),
        ("number_compare", {"operation": "eq"}, {"left": 4, "right": 3}, False, None),
        ("boolean_logic", {"operation": "and"}, {"left": True, "right": False}, False, None),
        ("boolean_logic", {"operation": "or"}, {"left": True, "right": False}, True, None),
        ("boolean_logic", {"operation": "not"}, {"left": False}, True, None),
        ("if_else", {}, {"condition": True}, True, "true"),
        ("if_else", {}, {"condition": False}, False, "false"),
        ("select_value", {}, {"condition": True, "if_true": 12, "if_false": 0}, 12, None),
        ("select_value", {}, {"condition": False, "if_true": 12, "if_false": None}, None, None),
    ],
)
async def test_primitive_executes_typed_inputs(handler, config, inputs, expected, outcome):
    result = await get_registry().invoke(handler, "1", config, invocation(inputs))
    assert result.outputs == {"result": expected}
    assert result.outcome == outcome


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["divide", "remainder"])
async def test_zero_divisor_is_rejected(operation):
    with pytest.raises(ValueError, match="zero"):
        await get_registry().invoke(
            "arithmetic", "1", {"operation": operation}, invocation({"left": 1, "right": 0})
        )


@pytest.mark.anyio
async def test_logic_requires_second_operand_and_numeric_ports_reject_booleans():
    registry = get_registry()
    with pytest.raises(ValueError, match="right"):
        await registry.invoke(
            "boolean_logic", "1", {"operation": "and"}, invocation({"left": True})
        )
    for invalid in (True, "2", float("inf"), float("nan")):
        with pytest.raises(ValueError):
            await registry.invoke(
                "arithmetic", "1", {"operation": "add"}, invocation({"left": invalid, "right": 1})
            )
    with pytest.raises(ValueError, match="cancelled"):
        await registry.invoke(
            "if_else", "1", {}, replace(invocation({"condition": True}), cancelled=lambda: True)
        )
