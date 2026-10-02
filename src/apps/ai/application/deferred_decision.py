"""Bounded PydanticAI decision calls that pause at one approved read-only tool."""

import json
from typing import Any, cast

from anyio import fail_after
from pydantic import ConfigDict
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, UsageLimits
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelResponse, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.tools import ToolApproved

from apps.ai.application.decision import AIDecisionResult
from apps.ai.application.errors import AIBudgetExhausted
from apps.ai.application.tools import TrustedAITool, resolve_trusted_tools
from apps.ai.domain.agent import AIAgentPublishedSpec
from apps.ai.domain.budget import BudgetAmounts
from apps.ai.domain.contracts import AIDecisionContract
from core.base_dto import BaseDTO


class AIDeferredResult(BaseDTO):
    """Transient checkpoint; persistence must encrypt and limit access to messages."""

    model_config = ConfigDict(extra="forbid")
    tool_key: str
    tool_version: str
    tool_call_id: str
    tool_args: dict[str, Any]
    messages: list[dict[str, Any]]
    usage: BudgetAmounts
    schema_hash: str
    model_used: str


async def begin_tool_decision(
    spec: AIAgentPublishedSpec,
    contract: AIDecisionContract,
    permitted: dict[str, Any],
    model: Model,
    pinned_versions: dict[str, str],
) -> AIDecisionResult | AIDeferredResult:
    """Run one model request and return a validated, unexecuted tool proposal."""
    tools = _tools(spec, pinned_versions)
    agent = _agent(spec, contract, model, tools)
    sanitized = spec.data_policy.prepare(permitted, spec.field_classifications)
    prompt = json.dumps(sanitized, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    with fail_after(spec.effective_limits.elapsed_seconds):
        result = await agent.run(
            prompt,
            usage_limits=_usage_limits(spec, tool_calls=0),
            model_settings={"max_tokens": spec.effective_limits.output_tokens},
        )
    actual = _actual_usage(spec, result.usage, tool_calls=0)
    if isinstance(result.output, DeferredToolRequests):
        requests = result.output
        if requests.calls or len(requests.approvals) != 1:
            raise ValueError("Exactly one approved read-only tool is supported")
        call = requests.approvals[0]
        tool = next((tool for tool in tools if tool.key == call.tool_name), None)
        if tool is None:
            raise ValueError("Model proposed an unregistered tool")
        args = tool.validate_call(call)
        messages = ModelMessagesTypeAdapter.dump_python(result.all_messages(), mode="json")
        if len(json.dumps(messages, separators=(",", ":")).encode()) > 131072:
            raise ValueError("AI approval checkpoint exceeds storage bounds")
        return AIDeferredResult(
            tool_key=tool.key,
            tool_version=tool.version,
            tool_call_id=call.tool_call_id,
            tool_args=args,
            messages=messages,
            usage=actual,
            schema_hash=contract.schema_hash,
            model_used=result.response.model_name or spec.model_id,
        )
    return _validated_decision(spec, contract, result, actual)


async def resume_tool_decision(
    spec: AIAgentPublishedSpec,
    contract: AIDecisionContract,
    checkpoint: AIDeferredResult,
    model: Model,
    pinned_versions: dict[str, str],
    *,
    deps: Any = None,
) -> AIDecisionResult:
    """Approve one exact call and allow one further model request."""
    tools = _tools(spec, pinned_versions)
    if checkpoint.schema_hash != contract.schema_hash:
        raise ValueError("Approval checkpoint decision schema changed")
    tool = next((tool for tool in tools if tool.key == checkpoint.tool_key), None)
    if tool is None or tool.version != checkpoint.tool_version:
        raise ValueError("Approval checkpoint tool changed")
    tool.validate_call(
        ToolCallPart(
            tool_name=checkpoint.tool_key,
            args=checkpoint.tool_args,
            tool_call_id=checkpoint.tool_call_id,
        )
    )
    if checkpoint.usage.requests != 1 or checkpoint.usage.tool_calls != 0:
        raise ValueError("AI approval checkpoint usage is invalid")
    _remaining_usage(spec, checkpoint.usage)
    history = ModelMessagesTypeAdapter.validate_python(checkpoint.messages)
    if len(json.dumps(checkpoint.messages, separators=(",", ":")).encode()) > 131072:
        raise ValueError("AI approval checkpoint exceeds storage bounds")
    pending = [
        part
        for message in history
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, ToolCallPart) and part.tool_call_id == checkpoint.tool_call_id
    ]
    if (
        len(pending) != 1
        or pending[0].tool_name != tool.key
        or tool.validate_call(pending[0]) != checkpoint.tool_args
    ):
        raise ValueError("Approval checkpoint call differs from message history")
    agent = _agent(spec, contract, model, tools)
    with fail_after(spec.effective_limits.elapsed_seconds):
        result = await agent.run(
            None,
            message_history=history,
            deps=deps,
            deferred_tool_results=DeferredToolResults(
                approvals={checkpoint.tool_call_id: ToolApproved()}
            ),
            usage_limits=_usage_limits(spec, tool_calls=1, prior=checkpoint.usage),
            model_settings={
                "max_tokens": spec.effective_limits.output_tokens - checkpoint.usage.output_tokens
            },
        )
    actual = _actual_usage(spec, result.usage, tool_calls=1, prior=checkpoint.usage)
    if isinstance(result.output, DeferredToolRequests):
        raise TypeError("A second deferred tool call is unsupported")
    return _validated_decision(spec, contract, result, actual)


def _tools(
    spec: AIAgentPublishedSpec, pinned_versions: dict[str, str]
) -> tuple[TrustedAITool, ...]:
    if spec.transport_attempts != 1 or spec.effective_limits.tool_calls != 1:
        raise ValueError("One approved tool and one-attempt transport are required")
    if spec.provider_key == "typesafe":
        raise ValueError("TypeSafe/Jev does not support tool calls")
    tools = resolve_trusted_tools(spec.data_policy, pinned_versions)
    if len(tools) != 1:
        raise ValueError("Exactly one approved read-only tool is required")
    return tools


def _agent(
    spec: AIAgentPublishedSpec,
    contract: AIDecisionContract,
    model: Model,
    tools: tuple[TrustedAITool, ...],
) -> Agent[Any, Any]:
    return Agent(
        model,
        output_type=cast(Any, [contract.output_model(), DeferredToolRequests]),
        instructions=spec.instructions,
        tools=[tool.pydantic_tool() for tool in tools],
        retries=0,
    )


def _remaining_usage(spec: AIAgentPublishedSpec, prior: BudgetAmounts) -> None:
    limits = spec.effective_limits
    if (
        limits.requests - prior.requests < 1
        or limits.tool_calls - prior.tool_calls < 1
        or limits.input_tokens - prior.input_tokens < 1
        or limits.output_tokens - prior.output_tokens < 1
        or limits.total_tokens - prior.total_tokens < 1
        or limits.spend_usd - prior.spend_usd <= 0
    ):
        raise AIBudgetExhausted("AI task budget exhausted before approval resume")


def _usage_limits(
    spec: AIAgentPublishedSpec,
    *,
    tool_calls: int,
    prior: BudgetAmounts | None = None,
) -> UsageLimits:
    limits = spec.effective_limits
    used = prior or BudgetAmounts()
    return UsageLimits(
        request_limit=1,
        tool_calls_limit=tool_calls,
        input_tokens_limit=limits.input_tokens - used.input_tokens,
        output_tokens_limit=limits.output_tokens - used.output_tokens,
        total_tokens_limit=limits.total_tokens - used.total_tokens,
    )


def _actual_usage(
    spec: AIAgentPublishedSpec,
    usage: Any,
    *,
    tool_calls: int,
    prior: BudgetAmounts | None = None,
) -> BudgetAmounts:
    limits = spec.effective_limits
    used = prior or BudgetAmounts()
    if (
        usage.requests != 1
        or usage.tool_calls != tool_calls
        or usage.input_tokens + used.input_tokens > limits.input_tokens
        or usage.output_tokens + used.output_tokens > limits.output_tokens
        or usage.input_tokens + usage.output_tokens + used.total_tokens > limits.total_tokens
    ):
        raise AIBudgetExhausted("Provider reported usage outside the pinned bound")
    actual = spec.price.actual(usage.input_tokens, usage.output_tokens)
    if actual.spend_usd + used.spend_usd > limits.spend_usd:
        raise AIBudgetExhausted("AI task spend budget exhausted")
    return actual.model_copy(update={"tool_calls": tool_calls})


def _validated_decision(
    spec: AIAgentPublishedSpec,
    contract: AIDecisionContract,
    result: Any,
    actual: BudgetAmounts,
) -> AIDecisionResult:
    output = contract.output_model().model_validate(result.output.model_dump(mode="json"))
    details = result.response.provider_details or {}
    confidence = (details.get("confidence") or {}).get("choice")
    if not isinstance(confidence, int | float) or not 0 <= confidence <= 1:
        confidence = 0.0
    return AIDecisionResult(
        decision=contract.decide(output.model_dump()["choice"], float(confidence)),
        usage=actual,
        schema_hash=contract.schema_hash,
        model_used=result.response.model_name or spec.model_id,
    )
