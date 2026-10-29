"""Author-provided decision samples never become provider execution evidence."""

import pytest
from pydantic import ValidationError

from apps.ai.application.authoring import decision_preview
from apps.ai.domain.agent import AIAgentDraftSpec, AIInputDecision
from apps.ai.domain.authoring import AIAgentEvaluationInput, AIDecisionPreviewInput


def spec():
    return AIAgentDraftSpec(
        connection_ref="declared-connection",
        provider_key="typesafe",
        model_id="model",
        prompt_version="1",
        instructions="Classify the owned ticket.",
        decision=AIInputDecision(question="Which queue?", options_input_key="options"),
        data_policy={"allowed_fields": ["options"], "allowed_classifications": ["INTERNAL"]},
        field_classifications={"options": "INTERNAL"},
        user_limits={
            "requests": 1,
            "tool_calls": 0,
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "elapsed_seconds": 30,
            "spend_usd": "0.50",
            "strict_spend": False,
        },
    )


def test_choice_preview_distinguishes_missing_empty_invalid_and_valid_without_a_provider():
    definition = spec()
    assert decision_preview(definition, None).sample_state == "MISSING"
    assert decision_preview(definition, {"options": []}).sample_state == "EMPTY"
    assert decision_preview(definition, {"options": ["bad"]}).sample_state == "INVALID"
    value = [{"key": k, "labels": {"en": k}, "description": k} for k in ["support", "finance"]]
    result = decision_preview(definition, {"options": value})
    assert result.sample_state == "VALID"
    assert [item.key for item in result.options] == ["support", "finance"]
    assert result.provider_called is False


def test_extra_or_missing_permitted_fields_cannot_look_like_a_valid_evaluation():
    definition = spec()
    assert decision_preview(definition, {"hidden": "private"}).sample_state == "INVALID"
    raw = {
        "options": [{"key": k, "labels": {"en": k}, "description": k} for k in ["a", "b"]],
        "hidden": "private",
    }
    result = decision_preview(definition, raw)
    assert result.sample_state == "INVALID"
    assert "private" not in result.model_dump_json()


def test_authoring_inputs_are_bounded_and_evaluation_cannot_inject_provider_commands():
    with pytest.raises(ValidationError):
        AIDecisionPreviewInput(sample_inputs={"options": "a" * 32769})
    with pytest.raises(ValidationError):
        AIAgentEvaluationInput.model_validate(
            {"request_ref": "owned-draft", "submit_key": "reviewed", "prompt": "run this instead"}
        )


def test_choice_preview_obeys_runtime_redaction_and_classification_policy():
    definition = spec()
    values = {"options": [{"key": k, "labels": {"en": k}, "description": k} for k in ["a", "b"]]}
    redacted = definition.model_copy(
        update={
            "data_policy": definition.data_policy.model_copy(
                update={"redacted_fields": {"options"}}
            )
        }
    )
    assert decision_preview(redacted, values).sample_state == "INVALID"
    denied = definition.model_copy(
        update={
            "data_policy": definition.data_policy.model_copy(
                update={"allowed_classifications": {"PUBLIC"}}
            )
        }
    )
    assert decision_preview(denied, values).sample_state == "INVALID"
