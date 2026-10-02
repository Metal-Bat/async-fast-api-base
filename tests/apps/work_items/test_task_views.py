"""Human task policies filter data independently of render visibility."""

import pytest

from apps.forms.domain.dto import FormDocuments
from apps.work_items.application.task_views import (
    TaskPolicyError,
    action_for,
    enforce_writes,
    filter_identity,
    filter_render,
    project_data,
    validate_action_data,
    validate_contract,
)
from apps.work_items.domain.task_contract import HumanTaskContract
from utils.exceptions import ValidationDetailsException


def contract():
    return HumanTaskContract.model_validate(
        {
            "default_view": "review",
            "views": [
                {
                    "key": "review",
                    "purpose": "edit",
                    "title": {"en": "Review"},
                    "scopes": ["/properties/amount", "/properties/decision"],
                },
                {
                    "key": "print",
                    "purpose": "print",
                    "title": {"en": "Print"},
                    "scopes": ["/properties/amount"],
                },
            ],
            "actions": [
                {
                    "key": "approve",
                    "kind": "complete",
                    "outcome_key": "approve",
                    "title": {"en": "Approve"},
                    "required_scopes": ["/properties/decision"],
                },
                {
                    "key": "send_back",
                    "kind": "return",
                    "outcome_key": "return",
                    "title": {"en": "Return"},
                    "require_comment": True,
                    "validation": "partial",
                },
            ],
        }
    )


def policy():
    return {
        "read": ["/properties/amount"],
        "write": ["/properties/decision"],
        "required": [],
        "hidden": ["/properties/secret"],
    }


def documents():
    return FormDocuments(
        data_schema={
            "type": "object",
            "properties": {
                "amount": {"type": "integer"},
                "decision": {"type": "string"},
                "secret": {"type": "string"},
            },
            "required": ["amount", "decision"],
        },
        render_schema={
            "root": {
                "component": "vertical",
                "children": [
                    {"component": "integer", "scope": "/properties/amount"},
                    {"component": "text", "scope": "/properties/decision"},
                    {"component": "text", "scope": "/properties/secret"},
                ],
            },
            "outcomes": ["approve", "return"],
        },
    )


def test_task_views_project_data_and_render_without_hidden_values():
    validate_contract(
        contract(), policy(), documents().data_schema, {"approve", "return"}, {"approve", "return"}
    )
    data = {"amount": 7, "decision": "yes", "secret": "private"}
    assert project_data(data, {"/properties/amount"}) == {"amount": 7}
    render = filter_render(documents().render_schema, {"/properties/amount"})
    assert [node["scope"] for node in render["root"]["children"]] == ["/properties/amount"]
    with pytest.raises(ValidationDetailsException):
        enforce_writes(data, {**data, "secret": "guess"}, policy())
    enforce_writes(data, {**data, "decision": "no"}, policy())


def test_actions_reject_undeclared_outcomes_and_validate_profiles():
    with pytest.raises(ValidationDetailsException):
        action_for(contract(), "complete", "return")
    with pytest.raises(TaskPolicyError, match="task.action.outcome"):
        validate_contract(
            contract(), policy(), documents().data_schema, {"approve", "return"}, {"approve"}
        )
    approve = action_for(contract(), "complete", "approve")
    with pytest.raises(ValidationDetailsException):
        validate_action_data(documents(), {"amount": 7}, approve, None)
    returning = action_for(contract(), "return", "return")
    assert validate_action_data(documents(), {"amount": 7}, returning, None) == {"amount": 7}
    with pytest.raises(ValidationDetailsException):
        validate_action_data(
            documents(),
            {"amount": 7},
            returning,
            None,
            policy_required=["/properties/decision"],
        )


def test_draft_save_rejects_invalid_supplied_type_without_required_fields():
    assert validate_action_data(documents(), {"decision": "pending"}, None, None, partial=True) == {
        "decision": "pending"
    }
    with pytest.raises(ValidationDetailsException):
        validate_action_data(documents(), {"decision": 42}, None, None, partial=True)


def test_feedback_targets_stable_item_key_after_reorder():
    from uuid import uuid7

    from apps.forms.application.collections import edit_collection, initialize_identity
    from apps.requests.domain.entity import FormSubmissionEntity
    from apps.users.domain.entity import UserEntity
    from apps.work_items.application.service import WorkItemService
    from apps.work_items.domain.dto import CorrectionFeedbackInput

    schema = {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {"type": "object", "properties": {"value": {"type": "string"}}},
            }
        },
    }
    data = {"rows": [{"value": "first"}, {"value": "second"}]}
    identity = initialize_identity(data, schema=schema)
    first_key = identity["/rows"][0]
    moved = edit_collection(
        data, identity, "/rows", "reorder", item_key=first_key, target_index=1, schema=schema
    )
    assert moved.identity["/rows"][1] == first_key
    submission = FormSubmissionEntity(
        business_request_id=uuid7(),
        form_version_id=uuid7(),
        data=moved.data,
        item_identity=moved.identity,
    )
    actor = UserEntity(
        id=uuid7(), username=f"feedback-{uuid7()}", hashed_password="hash", version=1
    )
    scope = "/properties/rows/items/properties/value"
    rows = WorkItemService._record_feedback(
        submission,
        [CorrectionFeedbackInput(scope=scope, item_key=first_key, message="Check this row")],
        actor,
        {"read": [scope], "write": [], "hidden": []},
    )
    assert rows[0]["item_key"] == first_key and rows[0]["status"] == "OPEN"
    with pytest.raises(ValidationDetailsException):
        WorkItemService._record_feedback(
            submission,
            [CorrectionFeedbackInput(scope=scope, item_key=str(uuid7()), message="Forged row")],
            actor,
            {"read": [scope], "write": [], "hidden": []},
        )


def test_task_view_filters_hidden_collection_identity():
    identity = {"/rows": ["first"], "/secret_rows": ["hidden"]}
    assert filter_identity(identity, {"/properties/rows/items/properties/value"}) == {
        "/rows": ["first"]
    }


def test_reject_action_must_declare_a_reason_requirement():
    raw = contract().model_dump()
    raw["actions"].append(
        {
            "key": "reject",
            "kind": "reject",
            "outcome_key": "reject",
            "title": {"en": "Reject"},
            "require_comment": False,
        }
    )
    with pytest.raises(TaskPolicyError, match="task.action.reason"):
        validate_contract(
            HumanTaskContract.model_validate(raw),
            policy(),
            documents().data_schema,
            {"approve", "return", "reject"},
            {"approve", "return", "reject"},
        )
