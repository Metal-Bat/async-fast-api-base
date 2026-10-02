"""Trusted AI decision step; execution policy is owned by ProcessStepServices."""

from typing import override

from pydantic import JsonValue

from apps.step_types.application.invocation import StepInvocationContext, StepResult
from apps.step_types.application.registry import (
    PortDefinition,
    Reference,
    StepDefinition,
    step_definition,
)
from core.base_dto import BaseDTO


class AIDecisionConfig(BaseDTO):
    agent_ref: Reference


@step_definition
class AIDecisionStep(StepDefinition):
    code = "AI_DECISION"
    name = "AI decision"
    handler_key = "ai_decision"
    handler_version = "1"
    category = "DECISION"
    execution_mode = "BACKGROUND"
    outcomes = ("next", "review")
    config_model = AIDecisionConfig
    ports = (
        PortDefinition("data", "INPUT", dict[str, JsonValue]),
        PortDefinition("choice", "OUTPUT", str),
        PortDefinition("confidence", "OUTPUT", float),
        PortDefinition("needs_review", "OUTPUT", bool),
    )
    name_key = "step.ai_decision.name"
    help_key = "step.ai_decision.help"
    examples = ({"agent_ref": "<published-agent-ref>"},)
    required_capabilities = ("ai.agent.use",)

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        configured = AIDecisionConfig.model_validate(config)
        values = context.inputs["data"]
        if not isinstance(values, dict):
            raise TypeError("AI decision data must be an object")
        outputs = await context.services.ai_decision(
            configured.agent_ref, context.execution_id, context.attempt_id, values
        )
        return StepResult(
            outputs=outputs,
            outcome="review" if outputs["needs_review"] else "next",
        )
