"""Publication validation for immutable workflow graphs."""

from uuid import uuid7

from apps.workflows.application.validation import GraphValidator
from apps.workflows.domain.dto import (
    GraphBinding,
    GraphFlow,
    GraphSnapshot,
    GraphStep,
    GraphTransition,
)
from core.ref_id import create_ref_id


def graph() -> GraphSnapshot:
    return GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START"),
            GraphStep(
                key="review",
                type_code="HUMAN_TASK",
                form_ref="form-v1",
                field_policy={"read": [], "write": [], "required": [], "hidden": []},
            ),
            GraphStep(key="finish", type_code="FINISH"),
        ],
        transitions=[
            GraphTransition(source="start", target="review", outcome="next", is_default=True),
            GraphTransition(source="review", target="finish", outcome="approve", is_default=True),
        ],
        targets=[{"step": "review", "user_ref": "user-1"}],
    )


def test_valid_linear_graph_has_canonical_checksum() -> None:
    result = GraphValidator().validate(graph())
    assert result.valid
    assert result.checksum is not None and len(result.checksum) == 64
    assert GraphValidator().validate(graph().model_copy(deep=True)).checksum == result.checksum


def test_checksum_uses_stable_identity_inside_optimistic_references() -> None:
    value = graph()
    entity_id = uuid7()
    value.steps[0].type_version_ref = create_ref_id(entity_id, 1)
    first = GraphValidator().validate(value).checksum
    value.steps[0].type_version_ref = create_ref_id(entity_id, 99)
    assert GraphValidator().validate(value).checksum == first


def test_control_flow_and_invalid_conditions_report_stable_locations() -> None:
    value = graph()
    value.transitions.append(
        GraphTransition(
            source="start",
            target="missing",
            outcome="bad",
            condition="current_user.missing",
        )
    )
    result = GraphValidator().validate(value)
    codes = {(issue.pointer, issue.code) for issue in result.issues}
    assert ("/transitions/2/target", "graph.step.unknown") in codes
    assert ("/transitions/2/condition", "expression.path.unknown") in codes


def test_conditions_compile_as_boolean_and_decision_expressions_are_checked() -> None:
    value = graph()
    value.targets[0].condition = "current_user.is_superuser or process.priority >= 5"
    value.transitions[0].condition = "process.priority < 5"
    value.steps.insert(
        1,
        GraphStep(
            key="decide",
            type_code="DECISION",
            config={"expression": 'choose(current_user.is_superuser, "approve", "review")'},
        ),
    )
    value.transitions[0].target = "decide"
    value.transitions.insert(
        1,
        GraphTransition(source="decide", target="review", outcome="review", is_default=True),
    )
    assert GraphValidator().validate(value).valid

    value.transitions[0].condition = "process.priority + 1"
    result = GraphValidator().validate(value)
    issue = next(item for item in result.issues if item.pointer == "/transitions/0/condition")
    assert issue.code == "expression.result.incompatible"
    assert issue.expected_schema == {"type": "boolean"}
    assert issue.actual_schema == {"type": "integer"}


def test_condition_can_read_only_reachable_declared_step_outputs() -> None:
    value = graph()
    value.transitions[1].condition = 'steps.review.outputs.outcome == "approve"'
    schemas = {"review": {"outcome": {"type": "string"}}}
    assert GraphValidator().validate(value, step_output_schemas=schemas).valid

    value.targets[0].condition = 'steps.review.outputs.outcome == "approve"'
    result = GraphValidator().validate(value, step_output_schemas=schemas)
    assert ("/targets/0/condition", "expression.path.unknown") in {
        (issue.pointer, issue.code) for issue in result.issues
    }


def test_data_bindings_reject_implicit_conversion_and_forward_reference() -> None:
    value = graph()
    value.bindings = [
        GraphBinding(
            step="review",
            target_port="amount",
            target_schema={"type": "integer"},
            source_kind="STEP_OUTPUT",
            source_step="finish",
            source_port="value",
            source_schema={"type": "string"},
        )
    ]
    result = GraphValidator().validate(value)
    codes = {issue.code for issue in result.issues}
    assert "binding.type.incompatible" in codes
    assert "binding.source.not_prior" in codes


def test_explicit_transform_declares_its_input_and_output_binding_schemas() -> None:
    value = graph()
    value.steps.insert(
        1,
        GraphStep(
            key="parse_amount",
            type_code="TRANSFORM",
            config={"conversion_key": "integer"},
        ),
    )
    value.transitions[0].target = "parse_amount"
    value.transitions.insert(
        1,
        GraphTransition(source="parse_amount", target="review", outcome="next", is_default=True),
    )
    value.bindings = [
        GraphBinding(
            step="parse_amount",
            target_port="value",
            target_schema={"type": ["string", "integer"]},
            source_kind="REQUEST",
            source_path="/properties/amount",
            source_schema={
                "type": "object",
                "properties": {"amount": {"type": "string"}},
            },
        ),
        GraphBinding(
            step="review",
            target_port="amount",
            target_schema={"type": "integer"},
            source_kind="STEP_OUTPUT",
            source_step="parse_amount",
            source_port="result",
            source_schema={"type": "integer"},
        ),
    ]
    assert GraphValidator().validate(value).valid

    value.bindings[1].source_schema = {"type": "string"}
    result = GraphValidator().validate(value)
    assert "transform.output_schema.mismatch" in {issue.code for issue in result.issues}


def test_human_steps_require_target_and_published_form_reference() -> None:
    value = graph()
    value.targets = []
    value.steps[1].form_ref = None
    result = GraphValidator().validate(value)
    assert {issue.code for issue in result.issues} >= {
        "human.form.required",
        "human.target.required",
    }


def test_field_policy_rejects_hidden_required_fields() -> None:
    from apps.workflows.application.service import WorkflowService

    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    assert not WorkflowService._valid_field_policy(
        {"read": [], "write": [], "required": [], "hidden": ["/properties/name"]},
        schema,
    )
    assert WorkflowService._valid_field_policy(
        {"read": ["/properties/name"], "write": [], "required": [], "hidden": []},
        schema,
    )


def test_parallel_split_and_join_require_structurally_safe_scope() -> None:
    value = GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START"),
            GraphStep(key="fork", type_code="FUNCTION", flow=GraphFlow(split="ALL")),
            GraphStep(key="left", type_code="FUNCTION"),
            GraphStep(key="right", type_code="FUNCTION"),
            GraphStep(key="join", type_code="FUNCTION", flow=GraphFlow(join="ALL")),
            GraphStep(key="finish", type_code="FINISH"),
        ],
        transitions=[
            GraphTransition(source="start", target="fork", outcome="next"),
            GraphTransition(source="fork", target="left", outcome="left"),
            GraphTransition(source="fork", target="right", outcome="right"),
            GraphTransition(source="left", target="join", outcome="done"),
            GraphTransition(source="right", target="join", outcome="done"),
            GraphTransition(source="join", target="finish", outcome="next"),
        ],
    )
    assert GraphValidator().validate(value).valid

    value.steps[4].flow = GraphFlow(join="ALL", cancelled_branches="FAIL")
    assert GraphValidator().validate(value).valid
    value.transitions[4].target = "finish"
    result = GraphValidator().validate(value)
    assert "graph.join.scope.invalid" in {issue.code for issue in result.issues}


def test_cycles_require_an_explicit_visit_bound() -> None:
    value = graph()
    value.transitions[1].target = "review"
    result = GraphValidator().validate(value)
    assert "graph.loop.unbounded" in {issue.code for issue in result.issues}

    value.steps[1].flow = GraphFlow(max_visits=3)
    assert "graph.loop.unbounded" not in {
        issue.code for issue in GraphValidator().validate(value).issues
    }


def test_compensation_references_must_target_isolated_compensation_steps() -> None:
    value = graph()
    value.steps.insert(
        2,
        GraphStep(
            key="undo_review",
            type_code="TRANSFORM",
            config={"conversion_key": "string"},
            flow=GraphFlow(compensation_only=True),
        ),
    )
    value.steps[1].flow = GraphFlow(compensation_step="undo_review")
    assert GraphValidator().validate(value).valid

    value.steps[1].flow = GraphFlow(compensation_step="missing")
    result = GraphValidator().validate(value)
    assert ("/steps/1/flow/compensation_step", "graph.compensation.unknown") in {
        (issue.pointer, issue.code) for issue in result.issues
    }


def test_client_predicates_compile_in_transition_and_decision_context():
    value = graph()
    value.transitions[0].is_default = False
    value.transitions[
        0
    ].condition = 'client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)'
    result = GraphValidator().validate(value)
    assert result.valid, result.issues
    value.transitions[0].condition = 'client.release >= "2.10"'
    invalid = GraphValidator().validate(value)
    assert any(
        issue.pointer == "/transitions/0/condition"
        and issue.code == "expression.version.predicate_required"
        for issue in invalid.issues
    )


def test_client_ordered_branches_reject_conditioned_or_misplaced_default():
    value = graph()
    value.transitions[0].is_default = False
    value.transitions[0].priority = 10
    value.transitions[0].condition = 'client.kind == "DESKTOP"'
    value.transitions.append(
        GraphTransition(
            source="start", target="finish", outcome="next", priority=20, is_default=True
        )
    )
    invalid = GraphValidator().validate(value)
    assert any(issue.code == "transition.default.order" for issue in invalid.issues)
    value.transitions[-1].priority = 0
    value.transitions[-1].condition = 'client.kind == "B2B"'
    invalid = GraphValidator().validate(value)
    assert any(issue.code == "transition.default.condition" for issue in invalid.issues)


def test_legacy_subprocess_interface_checksum_omits_new_default_metadata() -> None:
    import hashlib
    import json

    from apps.workflows.domain.subprocess import SubprocessInterface

    value = GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START"),
            GraphStep(key="finish", type_code="FINISH"),
        ],
        transitions=[GraphTransition(source="start", target="finish", outcome="next")],
        interface=SubprocessInterface(outcomes={"approved": "finish"}),
    )
    canonical = value.model_dump(mode="json")
    for step in canonical["steps"]:
        step.pop("subprocess", None)
        step.pop("flow", None)
    canonical["steps"].sort(key=lambda item: (item["display_order"], item["key"]))
    for field in ("category", "help_messages", "sample_inputs", "required_capabilities"):
        canonical["interface"].pop(field)
    expected = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert GraphValidator().validate(value).checksum == expected
