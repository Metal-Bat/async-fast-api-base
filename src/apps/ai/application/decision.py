"""Single-call typed decision adapter; all business checks remain in BPMS code."""

import json
from typing import Any

from anyio import fail_after
from pydantic_ai import Agent, UsageLimits
from pydantic_ai.models import Model
from pydantic_ai.models.typesafe import TypeSafeModel

from apps.ai.application.errors import AIBudgetExhausted
from apps.ai.domain.agent import AIAgentPublishedSpec
from apps.ai.domain.budget import BudgetAmounts
from apps.ai.domain.contracts import AIDecision, AIDecisionContract
from core.base_dto import BaseDTO


class AIDecisionResult(BaseDTO):
    decision: AIDecision
    usage: BudgetAmounts
    schema_hash: str
    model_used: str


def pinned_decision(
    spec: AIAgentPublishedSpec, inputs: dict[str, Any]
) -> tuple[AIDecisionContract, dict[str, Any]]:
    """Validate and filter bound fields before even constructing a provider request."""
    contract = spec.decision_snapshot(inputs)
    permitted = spec.data_policy.prepare(inputs, spec.field_classifications)
    return contract, permitted


async def run_decision(
    spec: AIAgentPublishedSpec,
    contract: AIDecisionContract,
    permitted: dict[str, Any],
    model: Model,
) -> AIDecisionResult:
    """One bounded provider request, with no model-selected tools or hidden retries."""
    if spec.transport_attempts != 1 or spec.effective_limits.tool_calls != 0:
        raise ValueError("Unsupported AI request retry or tool policy")
    if spec.provider_key == "typesafe" and not isinstance(model, TypeSafeModel):
        raise ValueError("Jev agent requires the registered TypeSafe model")
    output_model = contract.output_model()
    agent = Agent(
        model,
        output_type=output_model,
        instructions=spec.instructions,
        retries=0,
        tools=(),
    )
    prompt = json.dumps(permitted, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    limits = spec.effective_limits
    with fail_after(limits.elapsed_seconds):
        result = await agent.run(
            prompt,
            usage_limits=UsageLimits(
                request_limit=1,
                tool_calls_limit=0,
                input_tokens_limit=limits.input_tokens,
                output_tokens_limit=limits.output_tokens,
                total_tokens_limit=limits.total_tokens,
                count_tokens_before_request=limits.strict_spend,
            ),
            model_settings={"max_tokens": limits.output_tokens},
        )
    # PydanticAI's typed output is independently revalidated against our exact pin.
    validated = output_model.model_validate(result.output.model_dump(mode="json"))
    choice = validated.model_dump()["choice"]
    response = result.response
    details = response.provider_details or {}
    confidence = (details.get("confidence") or {}).get("choice")
    if not isinstance(confidence, int | float) or not 0 <= confidence <= 1:
        confidence = 0.0
    decision = contract.decide(choice, float(confidence))
    usage = result.usage
    if (
        usage.requests != 1
        or usage.input_tokens > limits.input_tokens
        or usage.output_tokens > limits.output_tokens
    ):
        raise AIBudgetExhausted("Provider reported usage outside the pinned bound")
    actual = spec.price.actual(usage.input_tokens, usage.output_tokens)
    if actual.spend_usd > limits.spend_usd:
        raise AIBudgetExhausted("AI task spend budget exhausted")
    return AIDecisionResult(
        decision=decision,
        usage=actual,
        schema_hash=contract.schema_hash,
        model_used=response.model_name or spec.model_id,
    )
