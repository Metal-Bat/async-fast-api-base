"""Governed AI data, Jev decision, budget and catalog contracts."""

from decimal import Decimal

import pytest

from apps.ai.application.catalog import model_suggestions
from apps.ai.domain.contracts import (
    AIChoice,
    AIDecisionContract,
    AIPermittedData,
    AITaskLimits,
    effective_limits,
)


def test_permitted_data_filters_fields_and_redacts_before_provider_boundary() -> None:
    policy = AIPermittedData(
        allowed_fields={"subject", "ticket"},
        allowed_classifications={"PUBLIC", "INTERNAL"},
        redacted_fields={"ticket"},
    )
    payload = policy.prepare(
        {"subject": "bug", "ticket": "account 123", "password": "private"},
        {"subject": "PUBLIC", "ticket": "INTERNAL", "password": "SECRET"},
    )
    assert payload == {"subject": "bug", "ticket": "[REDACTED]"}
    with pytest.raises(ValueError, match="classification"):
        policy.prepare(
            {"subject": "private", "ticket": "123"},
            {"subject": "SECRET", "ticket": "INTERNAL"},
        )


def test_user_limits_are_pinned_under_admin_ceilings_and_strict_spend_requires_quote() -> None:
    ceiling = AITaskLimits(
        requests=4,
        tool_calls=2,
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1200,
        elapsed_seconds=30,
        spend_usd=Decimal("1.00"),
    )
    user = AITaskLimits(
        requests=2,
        tool_calls=1,
        input_tokens=800,
        output_tokens=400,
        total_tokens=1000,
        elapsed_seconds=20,
        spend_usd=Decimal("0.50"),
    )
    effective = effective_limits(user, ceiling)
    assert effective.requests == 2 and effective.spend_usd == Decimal("0.50")
    with pytest.raises(ValueError, match="upper bound"):
        effective.require_strict_spend_bound(None)
    effective.require_strict_spend_bound(Decimal("0.25"))


def test_jev_choice_snapshot_is_stable_and_validates_membership() -> None:
    contract = AIDecisionContract(
        question="Which area owns this ticket?",
        options=[
            AIChoice(
                key="billing", labels={"en": "Billing", "fa": "صورتحساب"}, description="Invoices"
            ),
            AIChoice(key="bug", labels={"en": "Bug", "fa": "اشکال"}, description="Product defect"),
        ],
        review_below=0.8,
    )
    output_type = contract.output_model()
    choices_schema = output_type.model_json_schema()["properties"]["choice"]
    assert choices_schema["anyOf"][0]["description"] == "Invoices"
    assert output_type.model_validate({"choice": "bug"}).model_dump()["choice"] == "bug"
    with pytest.raises(ValueError):
        output_type.model_validate({"choice": "account"})
    assert [(item.key, item.value) for item in contract.select("fa")] == [
        ("billing", "صورتحساب"),
        ("bug", "اشکال"),
    ]
    assert contract.decide("bug", 0.79).needs_review
    assert not contract.decide("bug", 0.81).needs_review
    with pytest.raises(ValueError, match="Duplicate"):
        AIDecisionContract(question="Q", options=[contract.options[0]] * 2)


def test_model_suggestions_merge_known_and_custom_without_constructing_models() -> None:
    suggestions = model_suggestions(
        known=["typesafe:jev-1.13.0", "openai:gpt-example"],
        custom={"connection-a": ["tenant-model", "openai:gpt-example"]},
    )
    assert ("connection-a", "tenant-model", "configured") in suggestions
    assert (None, "typesafe:jev-1.13.0", "library") in suggestions
    assert len(suggestions) == 4


@pytest.mark.anyio
async def test_jev_is_registered_and_can_run_typed_choices_with_a_network_free_fake() -> None:
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.models.typesafe import TypeSafeModel
    from pydantic_ai.providers.typesafe import TypeSafeProvider

    contract = AIDecisionContract(
        question="Classify the support request",
        options=[
            AIChoice(key="billing", labels={"en": "Billing"}, description="Invoice question"),
            AIChoice(key="bug", labels={"en": "Bug"}, description="Software defect"),
        ],
    )
    model = TypeSafeModel("jev-1.13.0", provider=TypeSafeProvider(api_key="test-only"))
    agent = Agent(model, output_type=contract.output_model(), retries=0)
    with agent.override(model=TestModel(custom_output_args={"choice": "bug"})):
        result = await agent.run("A button crashes the app")
    assert result.output.model_dump() == {"choice": "bug"}
    assert result.usage.requests == 1
    assert contract.decide(result.output.model_dump()["choice"], 0.5).needs_review
