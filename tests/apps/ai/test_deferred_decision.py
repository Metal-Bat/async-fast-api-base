"""Network-free PydanticAI pause/resume for one approved read-only lookup."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from apps.ai.application.deferred_decision import (
    AIDeferredResult,
    _actual_usage,
    begin_tool_decision,
    resume_tool_decision,
)
from apps.ai.application.errors import AIBudgetExhausted
from apps.ai.application.tools import TrustedAITool, register_trusted_tool
from apps.ai.domain.agent import AIAgentPublishedSpec, AIPrice
from apps.ai.domain.budget import BudgetAmounts
from apps.ai.domain.contracts import AIChoice, AIDecisionContract, AIPermittedData, AITaskLimits


def spec() -> AIAgentPublishedSpec:
    limits = AITaskLimits(
        requests=2,
        tool_calls=1,
        input_tokens=1000,
        output_tokens=100,
        total_tokens=1100,
        elapsed_seconds=10,
        spend_usd=Decimal("0.10"),
        strict_spend=False,
    )
    return AIAgentPublishedSpec(
        connection_ref="opaque",
        provider_key="openai",
        model_id="fake-model",
        prompt_version="triage-1",
        instructions="Classify a ticket after approved lookup.",
        decision=AIDecisionContract(
            question="Where should this ticket go?",
            options=[
                AIChoice(key="billing", labels={"en": "Billing"}, description="Invoice"),
                AIChoice(key="bug", labels={"en": "Bug"}, description="Defect"),
            ],
        ),
        data_policy=AIPermittedData(
            allowed_fields={"ticket"},
            allowed_classifications={"INTERNAL"},
            allowed_tools={"lookup_deferred_test"},
            allowed_retrieval_sources={"approved_documents"},
        ),
        field_classifications={"ticket": "INTERNAL"},
        user_limits=limits,
        effective_limits=limits,
        price=AIPrice(
            version="test-price",
            input_per_million_usd=Decimal(1),
            output_per_million_usd=Decimal(1),
            fixed_per_request_usd=Decimal("0.01"),
        ),
    )


@pytest.mark.anyio
async def test_deferred_lookup_resumes_only_after_exact_approval() -> None:
    called = 0

    def lookup_document(ctx: RunContext[str], document_id: str) -> str:
        assert ctx.deps == "approved-context"
        nonlocal called
        called += 1
        return f"Approved document {document_id}"

    register_trusted_tool(
        TrustedAITool(
            key="lookup_deferred_test",
            version="1",
            description="Read one approved document",
            function=lookup_document,
            retrieval_source="approved_documents",
        )
    )

    def model_response(messages, info):
        if any(part.part_kind == "tool-return" for message in messages for part in message.parts):
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=info.output_tools[0].name,
                        args={"choice": "billing"},
                    )
                ],
                model_name="fake-model",
            )
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="lookup_deferred_test",
                    args={"document_id": "DOC-1"},
                    tool_call_id="call-1",
                )
            ],
            model_name="fake-model",
        )

    config = spec()
    contract = config.decision
    assert isinstance(contract, AIDecisionContract)
    model = FunctionModel(model_response, model_name="fake-model")
    pending = await begin_tool_decision(
        config,
        contract,
        {"ticket": "Invoice is wrong", "secret": "never disclose"},
        model,
        {"lookup_deferred_test": "1"},
    )
    assert isinstance(pending, AIDeferredResult)
    assert pending.tool_args == {"document_id": "DOC-1"}
    assert pending.usage.requests == 1
    assert pending.usage.tool_calls == 0
    assert "never disclose" not in json.dumps(pending.messages)
    assert called == 0
    with pytest.raises(ValueError, match="differs from message history"):
        await resume_tool_decision(
            config,
            contract,
            pending.model_copy(update={"tool_args": {"document_id": "OTHER"}}),
            model,
            {"lookup_deferred_test": "1"},
        )
    assert called == 0
    with pytest.raises(ValueError, match="checkpoint usage is invalid"):
        await resume_tool_decision(
            config,
            contract,
            pending.model_copy(update={"usage": BudgetAmounts(requests=2)}),
            model,
            {"lookup_deferred_test": "1"},
        )
    for exhausted in (
        BudgetAmounts(requests=1, input_tokens=1000, total_tokens=1000),
        BudgetAmounts(requests=1, spend_usd=Decimal("0.10")),
    ):
        with pytest.raises(AIBudgetExhausted, match="budget exhausted"):
            await resume_tool_decision(
                config,
                contract,
                pending.model_copy(update={"usage": exhausted}),
                model,
                {"lookup_deferred_test": "1"},
            )
    assert called == 0
    result = await resume_tool_decision(
        config, contract, pending, model, {"lookup_deferred_test": "1"}, deps="approved-context"
    )
    assert called == 1
    assert result.decision.choice == "billing"
    assert result.decision.needs_review
    assert result.usage.requests == 1
    assert result.usage.tool_calls == 1
    with pytest.raises(ValueError, match="unavailable or changed"):
        await resume_tool_decision(config, contract, pending, model, {"lookup_deferred_test": "2"})


def test_resumed_usage_must_fit_cumulative_tokens_and_spend() -> None:
    config = spec()
    response = SimpleNamespace(
        requests=1,
        tool_calls=1,
        input_tokens=1,
        output_tokens=1,
    )
    with pytest.raises(AIBudgetExhausted, match="pinned bound"):
        _actual_usage(
            config,
            response,
            tool_calls=1,
            prior=BudgetAmounts(requests=1, output_tokens=100, total_tokens=100),
        )
    with pytest.raises(AIBudgetExhausted, match="spend budget exhausted"):
        _actual_usage(
            config,
            response,
            tool_calls=1,
            prior=BudgetAmounts(requests=1, spend_usd=Decimal("0.095")),
        )
