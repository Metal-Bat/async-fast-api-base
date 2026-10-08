"""Filtered task patches recompute canonical calculations without permitting tampering."""

import pytest

from apps.forms.domain.dto import FormDocuments
from apps.work_items.application import task_mutations
from utils.exceptions import ValidationDetailsException


def documents():
    return FormDocuments(
        behavior_dialect="bpms.behavior/1",
        data_schema={
            "type": "object",
            "properties": {"amount": {"type": "string"}, "summary": {"type": "string"}},
        },
        render_schema={
            "root": {
                "component": "vertical",
                "children": [
                    {"component": "text", "scope": "/properties/amount"},
                    {
                        "component": "calculated",
                        "scope": "/properties/summary",
                        "calculation": {"function": "concat", "scopes": ["/properties/amount"]},
                    },
                ],
            }
        },
    )


def test_omitted_derived_value_recomputed_after_dependency_patch():
    before = {"amount": "125.750", "summary": "125.750"}
    assert task_mutations.normalize_task_behavior(
        documents(), before, {"amount": "200.000"}, {**before, "amount": "200.000"}, {}
    ) == {"amount": "200.000", "summary": "200.000"}


def test_unchanged_old_derived_value_is_recomputed_not_treated_as_tampering():
    before = {"amount": "125.750", "summary": "125.750"}
    assert (
        task_mutations.normalize_task_behavior(
            documents(),
            before,
            {"amount": "200.000", "summary": "125.750"},
            {**before, "amount": "200.000"},
            {},
        )["summary"]
        == "200.000"
    )


def test_modified_derived_value_still_rejected():
    before = {"amount": "125.750", "summary": "125.750"}
    with pytest.raises(ValidationDetailsException):
        task_mutations.normalize_task_behavior(
            documents(),
            before,
            {"amount": "200.000", "summary": "forged"},
            {"amount": "200.000", "summary": "forged"},
            {},
        )
