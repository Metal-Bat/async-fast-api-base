"""Shared twenty-control vectors exercise the production validator and projections."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from apps.clients.domain.contracts import ClientContext
from apps.forms.application.collections import edit_collection, initialize_identity
from apps.forms.application.designs import resolve_form_documents
from apps.forms.application.runtime import render_scopes, runtime_projection
from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.fields import FIELD_DEFINITIONS
from apps.work_items.application.task_mutations import merge_task_data

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/delivery/runtime-controls-v1.json"


def vector():
    return json.loads(FIXTURE.read_text())


def test_every_shipped_control_uses_the_same_canonical_before_after_vectors():
    fixture = vector()
    assert {row["kind"] for row in fixture["control_matrix"]} == set(FIELD_DEFINITIONS)
    document = FormDocuments.model_validate(fixture["documents"])
    validator = FormValidator()
    for data in (fixture["initial_data"], fixture["correction_data"]):
        assert validator.validate(document, data, publication=True).valid
        for locale in fixture["locales"]:
            design = resolve_form_documents(document, ClientContext.legacy(), locale=locale)
            scopes = render_scopes(design.render_schema)
            hidden = "/properties/private_note"
            for purpose in ("edit", "summary", "print", "correction"):
                projection = runtime_projection(
                    data,
                    initialize_identity(data, schema=document.data_schema),
                    {},
                    document.data_schema,
                    design.render_schema,
                    {"read": list(scopes - {hidden}), "hidden": [hidden]},
                    scopes - {hidden},
                    scopes - {hidden} if purpose in {"edit", "correction"} else set(),
                    set(),
                )
                assert projection["data"] == {
                    key: value for key, value in data.items() if key != "private_note"
                }
                assert "server-only-default" not in str(projection)
                assert projection["data"]["money"] in {"125.750", "200.000"}
                assert type(projection["data"]["choice"]) is int
                assert type(projection["data"]["boolean"]) is bool
                assert projection["data"]["optional"] in (None, "")
                assert "missing" not in projection["data"]
                if purpose in {"summary", "print"}:
                    assert not projection["writable_scopes"]


def test_numeric_strings_typed_keys_false_null_and_noncanonical_money_fail_safely():
    fixture = vector()
    document = FormDocuments.model_validate(fixture["documents"])
    for negative in fixture["negative_values"]:
        data = fixture["initial_data"] | {negative["field"]: negative["value"]}
        result = FormValidator().validate(document, data)
        assert not result.valid
        assert any(issue.code == negative["code"] for issue in result.issues)
        assert all(not hasattr(issue, "input") for issue in result.issues)


def test_nested_rows_retain_identity_and_hidden_values_survive_writable_patch():
    fixture = vector()
    before = deepcopy(fixture["initial_data"])
    identity = initialize_identity(before, schema=fixture["documents"]["data_schema"])
    first = identity["/rows"][0]
    nested = identity["/rows/0/children"][0]
    moved = edit_collection(
        before,
        identity,
        "/rows",
        "reorder",
        item_key=first,
        target_index=1,
        schema=fixture["documents"]["data_schema"],
    )
    assert moved.identity["/rows"][1] == first and moved.identity["/rows/1/children"][0] == nested
    # Only permitted fields are supplied; hidden canonical data stays on the server.
    merged = merge_task_data(
        before,
        {"text": "Corrected"},
        {"write": ["/properties/text"], "hidden": ["/properties/private_note"]},
    )
    assert merged["private_note"] == before["private_note"] and merged["text"] == "Corrected"
    with pytest.raises(ValueError):
        edit_collection(
            before,
            identity,
            "/rows",
            "remove",
            item_key="stale-row",
            schema=fixture["documents"]["data_schema"],
        )


def test_partial_correction_checks_exact_decimal_format_without_swapping_schema_and_data():
    from apps.work_items.application.task_views import validate_action_data
    from utils.exceptions import ValidationDetailsException

    fixture = vector()
    documents = FormDocuments.model_validate(fixture["documents"])
    assert (
        validate_action_data(documents, fixture["initial_data"], None, {}, partial=True)["money"]
        == "125.750"
    )
    with pytest.raises(ValidationDetailsException) as rejected:
        validate_action_data(
            documents, fixture["initial_data"] | {"money": "125.7500"}, None, {}, partial=True
        )
    assert rejected.value.issues == [{"pointer": "/data/money", "code": "data.canonical_format"}]
