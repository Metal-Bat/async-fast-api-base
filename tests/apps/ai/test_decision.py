"""Network-free typed decision boundary and bounded data disclosure."""

from decimal import Decimal

import pytest
from pydantic_ai.models.test import TestModel

from apps.ai.application.decision import pinned_decision, run_decision
from apps.ai.domain.agent import AIAgentPublishedSpec, AIInputDecision, AIPrice
from apps.ai.domain.contracts import AIChoice, AIPermittedData, AITaskLimits


def spec() -> AIAgentPublishedSpec:
    limits = AITaskLimits(
        requests=1,
        tool_calls=0,
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        elapsed_seconds=10,
        spend_usd=Decimal("0.50"),
        strict_spend=False,
    )
    return AIAgentPublishedSpec(
        connection_ref="opaque",
        provider_key="openai",
        model_id="fake",
        prompt_version="1",
        instructions="Classify the submitted ticket.",
        decision=AIInputDecision(question="Which area?", options_input_key="options"),
        data_policy=AIPermittedData(
            allowed_fields={"ticket", "options"},
            allowed_classifications={"INTERNAL"},
        ),
        field_classifications={"ticket": "INTERNAL", "options": "INTERNAL"},
        user_limits=limits,
        effective_limits=limits,
        price=AIPrice(
            version="test",
            input_per_million_usd=Decimal(1),
            output_per_million_usd=Decimal(1),
            fixed_per_request_usd=Decimal("0.01"),
        ),
    )


@pytest.mark.anyio
async def test_decision_filters_private_fields_and_requires_review_without_confidence() -> None:
    config = spec()
    values = {
        "ticket": "Button is broken",
        "password": "never send me",
        "options": [
            AIChoice(
                key="bug", labels={"en": "Bug", "fa": "اشکال"}, description="Defect"
            ).model_dump(),
            AIChoice(key="billing", labels={"en": "Billing"}, description="Invoice").model_dump(),
        ],
    }
    contract, permitted = pinned_decision(config, values)
    assert "password" not in permitted
    result = await run_decision(
        config,
        contract,
        permitted,
        TestModel(custom_output_args={"choice": "bug"}),
    )
    assert result.decision.choice == "bug"
    assert result.decision.needs_review
    assert result.schema_hash == contract.schema_hash
    assert result.usage.requests == 1
    with pytest.raises(TypeError, match="options"):
        pinned_decision(config, {"ticket": "missing options"})
    with pytest.raises(ValueError):
        contract.output_model().model_validate({"choice": "translated label"})


@pytest.mark.anyio
async def test_jev_confidence_metadata_controls_review_with_pinned_choice(monkeypatch) -> None:
    from types import SimpleNamespace

    from pydantic_ai import RunUsage
    from pydantic_ai.messages import ModelResponse
    from pydantic_ai.models.typesafe import TypeSafeModel
    from pydantic_ai.providers.typesafe import TypeSafeProvider

    from apps.ai.application import decision as adapter

    class FakeAgent:
        def __init__(self, model, *, output_type, instructions, retries, tools):
            self.output_type = output_type

        async def run(self, prompt, **kwargs):
            assert "Button is broken" in prompt
            return SimpleNamespace(
                output=self.output_type.model_validate({"choice": "bug"}),
                response=ModelResponse(
                    parts=[],
                    model_name="jev-1.13.0",
                    provider_details={"confidence": {"choice": 0.91}},
                ),
                usage=RunUsage(requests=1, input_tokens=10, output_tokens=3),
            )

    monkeypatch.setattr(adapter, "Agent", FakeAgent)
    config = spec().model_copy(update={"provider_key": "typesafe", "model_id": "jev-1.13.0"})
    contract, permitted = pinned_decision(
        config,
        {
            "ticket": "Button is broken",
            "options": [
                AIChoice(key="bug", labels={"en": "Bug"}, description="Defect").model_dump(),
                AIChoice(
                    key="billing", labels={"en": "Billing"}, description="Invoice"
                ).model_dump(),
            ],
        },
    )
    model = TypeSafeModel("jev-1.13.0", provider=TypeSafeProvider(api_key="test-only"))
    result = await run_decision(config, contract, permitted, model)
    assert result.decision.choice == "bug"
    assert result.decision.confidence == 0.91
    assert not result.decision.needs_review
    assert result.model_used == "jev-1.13.0"


def test_price_rejects_unknown_cost_and_unreservable_token_caps() -> None:
    with pytest.raises(ValueError, match="zero or unknown"):
        AIPrice(
            version="missing",
            input_per_million_usd=Decimal(0),
            output_per_million_usd=Decimal(0),
            fixed_per_request_usd=Decimal(0),
        )
    config = spec()
    incompatible = config.effective_limits.model_copy(update={"total_tokens": 100})
    with pytest.raises(ValueError, match="total-token"):
        config.price.upper(incompatible)
