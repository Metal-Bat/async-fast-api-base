"""Labeled Jev scoring keeps decision safety and report contents reproducible."""

from decimal import Decimal

import pytest
from pydantic_ai.models.test import TestModel

from apps.ai.application.decision import AIDecisionResult
from apps.ai.application.jev_evaluation import JevCase, JevSuite, run_live_suite, score_suite
from apps.ai.domain.agent import AIAgentPublishedSpec, AIPrice
from apps.ai.domain.budget import BudgetAmounts
from apps.ai.domain.contracts import (
    AIChoice,
    AIDecisionContract,
    AIPermittedData,
    AITaskLimits,
)


def suite() -> JevSuite:
    limits = AITaskLimits(
        requests=1,
        tool_calls=0,
        input_tokens=1000,
        output_tokens=100,
        total_tokens=1100,
        elapsed_seconds=10,
        spend_usd=Decimal("0.10"),
        strict_spend=False,
    )
    spec = AIAgentPublishedSpec(
        connection_ref="opaque",
        provider_key="typesafe",
        model_id="jev-1.13.0",
        prompt_version="triage-1",
        instructions="Classify the ticket.",
        decision=AIDecisionContract(
            question="Which queue owns this ticket?",
            review_below=0.8,
            options=[
                AIChoice(key="billing", labels={"en": "Billing"}, description="Invoice problem"),
                AIChoice(key="bug", labels={"en": "Bug"}, description="Software defect"),
            ],
        ),
        data_policy=AIPermittedData(
            allowed_fields={"ticket"},
            allowed_classifications={"INTERNAL"},
        ),
        field_classifications={"ticket": "INTERNAL"},
        user_limits=limits,
        effective_limits=limits,
        price=AIPrice(
            version="test-price-1",
            input_per_million_usd=Decimal(1),
            output_per_million_usd=Decimal(1),
            fixed_per_request_usd=Decimal("0.01"),
        ),
    )
    return JevSuite(
        spec=spec,
        cases=[
            JevCase(data={"ticket": "Invoice is wrong"}, expected_choice="billing"),
            JevCase(data={"ticket": "Button fails"}, expected_choice="bug"),
            JevCase(
                data={"ticket": "Unclear request"}, expected_choice="billing", should_review=True
            ),
        ],
        max_quote_usd=Decimal("0.04"),
    )


def test_labeled_report_tracks_wrong_auto_decisions_and_review_without_case_text() -> None:
    labeled = suite()
    contract = labeled.spec.decision
    assert isinstance(contract, AIDecisionContract)
    choices = [("billing", 0.93), ("billing", 0.90), ("bug", 0.30)]
    results = [
        AIDecisionResult(
            decision=contract.decide(choice, confidence),
            usage=BudgetAmounts(
                requests=1,
                input_tokens=10,
                output_tokens=2,
                total_tokens=12,
                spend_usd=Decimal("0.010012"),
            ),
            schema_hash=contract.schema_hash,
            model_used="jev-1.13.0",
        )
        for choice, confidence in choices
    ]
    report = score_suite(labeled, results)
    assert report.cases == 3
    assert report.correct == 1
    assert report.auto_decisions == 2
    assert report.correct_auto_decisions == 1
    assert report.review_decisions == 1
    assert report.unsafe_auto_decisions == 0
    assert report.incorrect_auto_decisions == 1
    assert report.quoted_upper_usd <= Decimal("0.04")
    assert report.reported_usage_usd == Decimal("0.030036")
    assert "Invoice is wrong" not in report.model_dump_json()
    assert "Button fails" not in report.model_dump_json()


def test_labeled_suite_rejects_unknown_labels_and_quote_overrun() -> None:
    labeled = suite()
    with pytest.raises(ValueError, match="outside the pinned"):
        JevSuite.model_validate(
            labeled.model_dump()
            | {
                "cases": [
                    JevCase(data={"ticket": "x"}, expected_choice="translated label"),
                    *labeled.cases[1:],
                ]
            }
        )
    with pytest.raises(ValueError, match="version-pinned"):
        JevSuite.model_validate(
            labeled.model_dump()
            | {"spec": labeled.spec.model_copy(update={"model_id": "jev-latest"})}
        )
    with pytest.raises(ValueError, match="cannot use tools"):
        JevSuite.model_validate(
            labeled.model_dump()
            | {
                "spec": labeled.spec.model_copy(
                    update={
                        "data_policy": labeled.spec.data_policy.model_copy(
                            update={"allowed_tools": {"lookup"}}
                        )
                    }
                )
            }
        )
    with pytest.raises(ValueError, match="exceeds"):
        JevSuite.model_validate(labeled.model_dump() | {"max_quote_usd": Decimal("0.001")})


def test_labeled_report_rejects_schema_and_model_drift() -> None:
    labeled = suite()
    contract = labeled.spec.decision
    assert isinstance(contract, AIDecisionContract)
    result = AIDecisionResult(
        decision=contract.decide("billing", 0.9),
        usage=BudgetAmounts(requests=1),
        schema_hash="wrong",
        model_used="jev-1.13.0",
    )
    with pytest.raises(ValueError, match="pinned model or choice schema"):
        score_suite(labeled, [result] * len(labeled.cases))


@pytest.mark.anyio
async def test_live_evaluation_stops_before_next_overquoted_call_and_closes_client(
    monkeypatch,
) -> None:
    from apps.ai.application import jev_evaluation as evaluation

    labeled = suite()
    calls = 0
    closed = False

    async def fake_run(spec, contract, permitted, model):
        nonlocal calls
        calls += 1
        return AIDecisionResult(
            decision=contract.decide("billing", 0.95),
            usage=BudgetAmounts(requests=1, spend_usd=Decimal("0.039")),
            schema_hash=contract.schema_hash,
            model_used="jev-1.13.0",
        )

    async def fake_close(model):
        nonlocal closed
        closed = True

    def unexpected_model_creation(*args, **kwargs):
        pytest.fail("Evaluation must use the injected model")

    monkeypatch.setattr(evaluation, "create_model", unexpected_model_creation)
    monkeypatch.setattr(evaluation, "run_decision", fake_run)
    monkeypatch.setattr(evaluation, "close_model", fake_close)
    with pytest.raises(ValueError, match="no quote"):
        await run_live_suite(labeled, TestModel())
    assert calls == 1
    assert closed
