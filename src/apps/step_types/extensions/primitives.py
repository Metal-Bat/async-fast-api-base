"""Pure, typed building blocks for workflow calculations and control flow."""

import operator
from typing import Literal, override

from pydantic import Field, FiniteFloat, JsonValue

from apps.step_types.application.invocation import StepInvocationContext, StepResult
from apps.step_types.application.registry import (
    EmptyConfig,
    PortDefinition,
    StepDefinition,
    step_definition,
)
from core.base_dto import BaseDTO


class ArithmeticConfig(EmptyConfig):
    operation: Literal["add", "subtract", "multiply", "divide", "remainder"] = Field(
        description="Operation on left and right numeric ports. Divide and remainder reject zero right operands. Uses finite JSON numbers, not exact decimal accounting.",
    )


class ComparisonConfig(EmptyConfig):
    operation: Literal["eq", "ne", "lt", "lte", "gt", "gte"] = Field(
        description="Numeric comparison: equal, not equal, less, less or equal, greater, greater or equal. Produces a boolean result.",
    )


class LogicConfig(EmptyConfig):
    operation: Literal["and", "or", "not"] = Field(
        description="AND and OR require left and right boolean ports. NOT uses left and ignores an optional right input.",
    )


@step_definition
class ArithmeticStep(StepDefinition):
    code = "ARITHMETIC"
    name = "Arithmetic"
    name_key = "Arithmetic"
    handler_key = "arithmetic"
    handler_version = "1"
    category = "MATH"
    execution_mode = "SYNC"
    config_model = ArithmeticConfig
    ports = (
        PortDefinition("left", "INPUT", FiniteFloat),
        PortDefinition("right", "INPUT", FiniteFloat),
        PortDefinition("result", "OUTPUT", FiniteFloat),
    )
    help_key = "Calculate two finite numbers; reject zero divisors. Use for quantities and scores, not exact currency accounting."
    examples = tuple(
        {"operation": key} for key in ("add", "subtract", "multiply", "divide", "remainder")
    )

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        operation = ArithmeticConfig.model_validate(config).operation
        left, right = context.inputs["left"], context.inputs["right"]
        if operation in {"divide", "remainder"} and right == 0:
            raise ValueError("Arithmetic divisor cannot be zero")
        functions = {
            "add": operator.add,
            "subtract": operator.sub,
            "multiply": operator.mul,
            "divide": operator.truediv,
            "remainder": operator.mod,
        }
        return StepResult(outputs={"result": functions[operation](left, right)})


@step_definition
class NumberComparisonStep(StepDefinition):
    code = "NUMBER_COMPARE"
    name = "Compare numbers"
    name_key = "Compare numbers"
    handler_key = "number_compare"
    handler_version = "1"
    category = "LOGIC"
    execution_mode = "SYNC"
    config_model = ComparisonConfig
    ports = (
        PortDefinition("left", "INPUT", FiniteFloat),
        PortDefinition("right", "INPUT", FiniteFloat),
        PortDefinition("result", "OUTPUT", bool),
    )
    help_key = "Compare two numbers to produce a boolean for a threshold, equality check or branch."
    examples = tuple({"operation": key} for key in ("eq", "ne", "lt", "lte", "gt", "gte"))

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        functions = {
            "eq": operator.eq,
            "ne": operator.ne,
            "lt": operator.lt,
            "lte": operator.le,
            "gt": operator.gt,
            "gte": operator.ge,
        }
        operation = ComparisonConfig.model_validate(config).operation
        return StepResult(
            outputs={
                "result": functions[operation](context.inputs["left"], context.inputs["right"])
            }
        )


@step_definition
class BooleanLogicStep(StepDefinition):
    code = "BOOLEAN_LOGIC"
    name = "Boolean logic"
    name_key = "Boolean logic"
    handler_key = "boolean_logic"
    handler_version = "1"
    category = "LOGIC"
    execution_mode = "SYNC"
    config_model = LogicConfig
    ports = (
        PortDefinition("left", "INPUT", bool),
        PortDefinition("right", "INPUT", bool, required=False),
        PortDefinition("result", "OUTPUT", bool),
    )
    help_key = "Combine boolean conditions with AND or OR, or invert one condition with NOT."
    examples = ({"operation": "and"}, {"operation": "or"}, {"operation": "not"})

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        operation = LogicConfig.model_validate(config).operation
        left = context.inputs["left"]
        if operation == "not":
            return StepResult(outputs={"result": not left})
        if "right" not in context.inputs:
            raise ValueError("Boolean AND and OR require the right operand")
        right = context.inputs["right"]
        return StepResult(
            outputs={"result": left and right if operation == "and" else left or right}
        )


@step_definition
class IfElseStep(StepDefinition):
    code = "IF_ELSE"
    name = "If / else"
    name_key = "If / else"
    handler_key = "if_else"
    handler_version = "1"
    category = "CONTROL"
    execution_mode = "SYNC"
    config_model = EmptyConfig
    ports = (
        PortDefinition("condition", "INPUT", bool),
        PortDefinition("result", "OUTPUT", bool),
    )
    outcomes = ("true", "false")
    help_key = (
        "Follow the true or false transition according to a boolean input; connect both branches."
    )
    examples = ({},)

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        condition = context.inputs["condition"]
        return StepResult(outputs={"result": condition}, outcome="true" if condition else "false")


@step_definition
class SelectValueStep(StepDefinition):
    code = "SELECT_VALUE"
    name = "Select value"
    name_key = "Select value"
    handler_key = "select_value"
    handler_version = "1"
    category = "DATA"
    execution_mode = "SYNC"
    config_model = EmptyConfig
    ports = (
        PortDefinition("condition", "INPUT", bool),
        PortDefinition("if_true", "INPUT", JsonValue, nullable=True),
        PortDefinition("if_false", "INPUT", JsonValue, nullable=True),
        PortDefinition("result", "OUTPUT", JsonValue, nullable=True),
    )
    help_key = "Select one supplied JSON value using a boolean condition, without branching the workflow. Both inputs are required and may be null."
    examples = ({},)

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        key = "if_true" if context.inputs["condition"] else "if_false"
        return StepResult(outputs={"result": context.inputs[key]})
