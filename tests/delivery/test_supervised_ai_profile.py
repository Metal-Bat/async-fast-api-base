"""Scripted bilingual contract regressions; never model-quality evidence."""

import json
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from tests.apps.ai.test_decision import spec
from tests.apps.workflows.test_protected_effects import protected_graph

from apps.ai.application.decision import pinned_decision, run_decision
from apps.workflows.application.validation import GraphValidator
from apps.workflows.domain.dto import GraphStep, GraphTransition

PROFILE = json.loads(
    (Path(__file__).parents[1] / "fixtures/delivery/supervised-ai-en-fa.json").read_text()
)


@pytest.mark.anyio
@pytest.mark.parametrize("case", PROFILE["cases"], ids=lambda case: case["id"])
async def test_scripted_bilingual_decision_has_no_tool_or_business_authority(case):
    config = spec()
    inputs = {
        "ticket": case["ticket"],
        "personal_note": "excluded-private-value",
        "attachment_url": "https://private.example.test/file",
        "options": [
            {"key": "bug", "labels": {"en": "Bug", "fa": "اشکال"}, "description": "Defect"},
            {
                "key": "billing",
                "labels": {"en": "Billing", "fa": "صورتحساب"},
                "description": "Invoice",
            },
        ],
    }
    contract, permitted = pinned_decision(config, inputs)
    assert set(permitted) == {"ticket", "options"}

    def scripted(messages, info):
        assert info.function_tools == []
        wire = repr(messages)
        assert "excluded-private-value" not in wire
        assert "private.example.test" not in wire
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"choice": case["choice"]})],
            model_name="deterministic-supervised-profile",
            provider_details={"confidence": {"choice": case["confidence"]}},
        )

    result = await run_decision(
        config,
        contract,
        permitted,
        FunctionModel(scripted, model_name="deterministic-supervised-profile"),
    )
    assert result.model_used == "deterministic-supervised-profile"
    assert result.decision.choice == case["choice"]
    assert result.decision.needs_review == case["needs_review"]
    assert result.usage.requests == 1 and result.usage.tool_calls == 0
    graph = protected_graph()
    graph.steps.insert(1, GraphStep(key="ai", type_code="AI_DECISION"))
    graph.transitions[0].target = "ai"
    graph.transitions.extend(
        [
            GraphTransition(source="ai", target="approval", outcome="next"),
            GraphTransition(source="ai", target="approval", outcome="review"),
        ]
    )
    assert GraphValidator().validate(graph).valid
    for outcome in ("next", "review"):
        bypass = graph.model_copy(deep=True)
        bypass.transitions.append(GraphTransition(source="ai", target="order", outcome=outcome))
        assert "protected_effect.approval.bypass" in {
            issue.code for issue in GraphValidator().validate(bypass).issues
        }
