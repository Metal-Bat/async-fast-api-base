"""Filtered mutation contracts preserve undisclosed canonical state."""

import pytest

from utils.exceptions import ValidationDetailsException

POLICY = {
    "read": ["/properties/amount"],
    "write": ["/properties/amount"],
    "hidden": ["/properties/internal_note"],
}


def test_filtered_save_preserves_hidden_values_and_omission_is_not_deletion():
    from apps.work_items.application.task_mutations import merge_task_data

    before = {"amount": 10, "internal_note": "not-disclosed"}
    assert merge_task_data(before, {"amount": None}, POLICY) == {
        "amount": None,
        "internal_note": "not-disclosed",
    }
    assert merge_task_data(before, {}, POLICY) == before
    assert merge_task_data(before, {}, POLICY, delete_paths=["/amount"]) == {
        "internal_note": "not-disclosed"
    }
    with pytest.raises(ValidationDetailsException):
        merge_task_data(before, {"internal_note": "guess"}, POLICY)
    with pytest.raises(ValidationDetailsException):
        merge_task_data(before, {}, POLICY, delete_paths=["/internal_note"])


def test_nested_row_patch_preserves_unseen_columns_and_rejects_structural_edits():
    from apps.work_items.application.task_mutations import merge_task_data

    scope = "/properties/rows/items/properties/value"
    policy = {"read": [scope], "write": [scope]}
    before = {"rows": [{"value": 1, "private": "row-a"}, {"value": 2, "private": "row-b"}]}
    assert merge_task_data(before, {"rows": [{"value": 9}, {"value": 2}]}, policy) == {
        "rows": [{"value": 9, "private": "row-a"}, {"value": 2, "private": "row-b"}]
    }
    with pytest.raises(ValidationDetailsException):
        merge_task_data(before, {"rows": [{"value": 9}]}, policy)
    assert merge_task_data(before, {}, policy, delete_paths=["/rows/0/value"]) == {
        "rows": [{"private": "row-a"}, {"value": 2, "private": "row-b"}]
    }


def test_named_view_cannot_write_other_visible_fields():
    from apps.work_items.application.task_mutations import merge_task_data

    policy = {
        "read": ["/properties/a", "/properties/b"],
        "write": ["/properties/a", "/properties/b"],
    }
    with pytest.raises(ValidationDetailsException):
        merge_task_data({"a": 1, "b": 2}, {"b": 3}, policy, view_scopes={"/properties/a"})


def test_mutation_projection_filters_data_identity_provenance_and_issues():
    from apps.work_items.application.task_mutations import project_task_state

    scope = "/properties/rows"
    policy = {
        "read": [scope],
        "write": [scope],
        "hidden": ["/properties/internal_note", "/properties/secret_rows"],
    }
    result = project_task_state(
        {
            "rows": [{"value": 1}],
            "internal_note": "not-disclosed",
            "secret_rows": [{"secret": "private"}],
        },
        {"/rows": ["visible-key"], "/secret_rows": ["hidden-key"]},
        {"/properties/internal_note": {"value": "private"}},
        [{"pointer": "/data/internal_note", "code": "hidden-code", "item_keys": ["hidden-key"]}],
        policy,
    )
    assert result["data"] == {"rows": [{"value": 1}]}
    assert result["item_identity"] == {"/rows": ["visible-key"]}
    assert result["override_provenance"] == {}
    assert result["issues"] == []


def test_nested_hidden_fields_are_redacted_even_when_parent_collection_is_readable():
    from apps.work_items.application.task_mutations import project_task_state

    result = project_task_state(
        {"rows": [{"visible": 1, "secret": "private"}]},
        {},
        {},
        [],
        {"read": ["/properties/rows"], "hidden": ["/properties/rows/items/properties/secret"]},
    )
    assert result["data"] == {"rows": [{"visible": 1}]}


def test_hidden_descendants_survive_container_replacement_and_explicit_deletion():
    from apps.work_items.application.task_mutations import merge_task_data, project_task_state

    before = {"object": {"visible": 1, "private": "protected"}}
    policy = {
        "read": ["/properties/object"],
        "write": ["/properties/object"],
        "hidden": ["/properties/object/properties/private"],
    }
    with pytest.raises(ValidationDetailsException):
        merge_task_data(before, {"object": None}, policy)
    with pytest.raises(ValidationDetailsException):
        merge_task_data(before, {}, policy, delete_paths=["/object"])
    state = project_task_state(
        before, {}, {"/properties/object": {"value": before["object"]}}, [], policy
    )
    assert state["override_provenance"] == {}
