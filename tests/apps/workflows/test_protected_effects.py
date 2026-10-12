"""Protected sandbox effects require a declared human approval on every route."""

import pytest

from apps.work_items.domain.task_contract import HumanTaskContract
from apps.workflows.application.validation import GraphValidator
from apps.workflows.domain.dto import GraphBinding, GraphSnapshot, GraphStep, GraphTransition


def protected_graph() -> GraphSnapshot:
    return GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START"),
            GraphStep(
                key="approval",
                type_code="HUMAN_TASK",
                form_ref="published-form",
                field_policy={"read": [], "write": [], "required": [], "hidden": []},
                task_contract=HumanTaskContract.model_validate(
                    {
                        "default_view": "edit",
                        "views": [
                            {
                                "key": "edit",
                                "purpose": "edit",
                                "title": {"en": "Approve order"},
                                "scopes": [],
                            }
                        ],
                        "actions": [
                            {
                                "key": "approve",
                                "kind": "complete",
                                "outcome_key": "approve",
                                "title": {"en": "Approve"},
                            }
                        ],
                    }
                ),
            ),
            GraphStep(
                key="order",
                type_code="SERVICE_TASK",
                config={
                    "operation_key": "sandbox.order.create/1",
                    "connection_ref": "sandbox-connection",
                },
            ),
            GraphStep(key="finish", type_code="FINISH"),
        ],
        targets=[{"step": "approval", "user_ref": "reviewer"}],
        bindings=[
            GraphBinding(
                step="order",
                target_port="payload",
                target_schema={"type": "object"},
                source_kind="STEP_OUTPUT",
                source_step="approval",
                source_port="submission",
                source_schema={"type": "object"},
            )
        ],
        transitions=[
            GraphTransition(source="start", target="approval", outcome="next"),
            GraphTransition(source="approval", target="order", outcome="approve"),
            GraphTransition(source="order", target="finish", outcome="next"),
        ],
    )


def codes(graph):
    return {issue.code for issue in GraphValidator().validate(graph).issues}


def test_declared_approval_with_identical_submission_payload_is_valid():
    result = GraphValidator().validate(protected_graph())
    assert result.valid, result.issues


@pytest.mark.parametrize("outcome", ["next", "review", "reject", "return", "approve"])
@pytest.mark.parametrize("is_default", [False, True])
def test_alternate_outcomes_and_default_routes_cannot_bypass_approval(outcome, is_default):
    graph = protected_graph()
    graph.transitions.append(
        GraphTransition(
            source="start", target="order", outcome=outcome, is_default=is_default, priority=1
        )
    )
    assert "protected_effect.approval.bypass" in codes(graph)


def test_rejection_after_human_step_is_not_an_approval():
    graph = protected_graph()
    graph.transitions[1].outcome = "reject"
    assert "protected_effect.approval.bypass" in codes(graph)


@pytest.mark.parametrize("kind", ["reject", "return"])
def test_non_completion_action_cannot_relabel_outcome_as_approve(kind):
    graph = protected_graph()
    assert graph.steps[1].task_contract is not None
    graph.steps[1].task_contract.actions[0].kind = kind
    assert "protected_effect.approval.action_required" in codes(graph)


@pytest.mark.parametrize("source", ["REQUEST", "CONTEXT", "CONSTANT"])
def test_payload_must_be_the_declared_human_submission(source):
    graph = protected_graph()
    graph.bindings[0].source_kind = source
    assert "protected_effect.approval.binding_required" in codes(graph)


def test_generic_human_task_and_ai_output_cannot_supply_approval():
    graph = protected_graph()
    graph.steps[1].task_contract = None
    assert "protected_effect.approval.action_required" in codes(graph)
    graph.steps[1].type_code = "AI_DECISION"
    assert "protected_effect.approval.binding_required" in codes(graph)


def test_partial_or_multiple_payload_binding_cannot_change_approved_inputs():
    graph = protected_graph()
    graph.bindings[0].source_path = "/quantity"
    assert "protected_effect.approval.binding_required" in codes(graph)
    graph.bindings[0].source_path = None
    graph.bindings.append(graph.bindings[0].model_copy())
    assert "protected_effect.approval.binding_required" in codes(graph)


def test_completed_unprotected_child_does_not_replace_required_root_human_approval():
    graph = protected_graph()
    graph.steps.insert(1, GraphStep(key="child", type_code="SUBPROCESS"))
    graph.transitions[0].target = "child"
    graph.transitions.append(GraphTransition(source="child", target="approval", outcome="success"))
    assert GraphValidator().validate(graph).valid
    graph.bindings[0].source_step = "child"
    assert "protected_effect.approval.binding_required" in codes(graph)
    graph.bindings[0].source_step = "approval"
    graph.transitions.append(GraphTransition(source="child", target="order", outcome="failure"))
    assert "protected_effect.approval.bypass" in codes(graph)


def test_child_owned_protected_effect_cannot_infer_parent_approval():
    from apps.workflows.domain.subprocess import SubprocessInterface

    graph = protected_graph()
    graph.interface = SubprocessInterface(inputs=[], outputs=[], outcomes={"success": "finish"})
    assert "protected_effect.subprocess.unsupported" in codes(graph)


def test_unprotected_existing_graph_retains_checksum_and_semantics():
    graph = protected_graph()
    graph.steps[2].config["operation_key"] = "connection.status"
    graph.steps[1].task_contract = None
    graph.transitions[1].outcome = "reject"
    assert GraphValidator().validate(graph).valid
