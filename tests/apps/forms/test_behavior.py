"""Canonical behavior evaluation is deterministic and submission safe."""

import pytest

from apps.forms.application.behavior import BehaviorError, evaluate_behavior
from apps.forms.domain.dto import FormDocuments


def documents():
    return FormDocuments(
        behavior_dialect="bpms.behavior/1",
        data_schema={
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "price": {"type": "number"},
                "quantity": {"type": "number"},
                "total": {"type": "number"},
                "note": {"type": "string"},
            },
        },
        render_schema={
            "root": {
                "component": "vertical",
                "children": [
                    {
                        "component": "calculated",
                        "scope": "/properties/total",
                        "calculation": {
                            "function": "sum",
                            "scopes": ["/properties/price", "/properties/quantity"],
                        },
                    },
                    {
                        "component": "text",
                        "scope": "/properties/note",
                        "rules": [
                            {
                                "scope": "/properties/enabled",
                                "operator": "eq",
                                "value": False,
                                "effect": "hide",
                            }
                        ],
                    },
                ],
            }
        },
    )


def test_initialization_preserves_explicit_null_and_runs_defaults_once():
    result = evaluate_behavior(
        documents(),
        {"enabled": None},
        initial={"enabled": False, "price": 2, "quantity": 3},
        initialize=True,
    )
    assert result.data["enabled"] is None
    assert result.data["total"] == 5
    assert result.data["price"] == 2


def test_hidden_field_clearing_and_computed_tamper_rejection():
    result = evaluate_behavior(
        documents(), {"enabled": False, "price": 2, "quantity": 3, "note": "secret"}
    )
    assert "note" not in result.data and result.data["total"] == 5
    with pytest.raises(BehaviorError, match="behavior.derived_tampered"):
        evaluate_behavior(
            documents(), {"price": 2, "quantity": 3, "total": 999}, authoritative=True
        )


def test_calculation_cycle_is_rejected():
    doc = documents()
    doc.render_schema["root"]["children"].append(
        {
            "component": "calculated",
            "scope": "/properties/price",
            "calculation": {"function": "sum", "scopes": ["/properties/total"]},
        }
    )
    with pytest.raises(BehaviorError, match="behavior.cycle"):
        evaluate_behavior(doc, {"quantity": 1})


def test_authoritative_validation_shares_behavior_engine():
    from apps.forms.application.validation import FormValidator

    doc = documents()
    valid = FormValidator().validate(doc, {"price": 2, "quantity": 3, "total": 5})
    assert valid.valid and valid.evaluated_data is not None
    assert valid.evaluated_data["total"] == 5
    tampered = FormValidator().validate(doc, {"price": 2, "quantity": 3, "total": 7})
    assert not tampered.valid and tampered.issues[0].code == "behavior.derived_tampered"
    cycle = documents()
    cycle.render_schema["root"]["children"].append(
        {
            "component": "calculated",
            "scope": "/properties/price",
            "calculation": {"function": "sum", "scopes": ["/properties/total"]},
        }
    )
    rejected = FormValidator().validate(cycle)
    assert not rejected.valid and rejected.issues[0].code == "behavior.cycle"


def test_expression_calculation_and_cycle():
    doc = documents()
    doc.render_schema["root"]["children"][0]["calculation"] = {
        "expression": "request.price * request.quantity"
    }
    assert evaluate_behavior(doc, {"price": 2, "quantity": 3}).data["total"] == 6
    doc.render_schema["root"]["children"].append(
        {
            "component": "calculated",
            "scope": "/properties/price",
            "calculation": {"expression": "request.total + 1"},
        }
    )
    with pytest.raises(BehaviorError, match="behavior.cycle"):
        evaluate_behavior(doc, {"quantity": 3})


def test_manual_override_requires_permission_and_provenance_and_resets():
    from apps.forms.application.behavior import apply_manual_override
    from apps.forms.domain.behavior import ManualOverrideRequest

    doc = documents()
    doc.render_schema["root"]["children"][0]["calculation"]["override_permission"] = (
        "forms.override"
    )
    data = {"price": 2, "quantity": 3, "total": 5}
    command = ManualOverrideRequest(
        scope="/properties/total", operation="set", value=7, reason="Approved adjustment"
    )
    with pytest.raises(BehaviorError, match="behavior.override_permission"):
        apply_manual_override(doc, data, None, command, actor_ref_id="actor", permissions=set())
    changed, provenance = apply_manual_override(
        doc, data, None, command, actor_ref_id="actor", permissions={"forms.override"}
    )
    assert (
        changed["total"] == 7 and provenance["/properties/total"]["reason"] == "Approved adjustment"
    )
    assert (
        evaluate_behavior(doc, changed, authoritative=True, overrides=provenance).data["total"] == 7
    )
    with pytest.raises(BehaviorError, match="behavior.override_stale"):
        evaluate_behavior(doc, {**changed, "price": 4}, authoritative=True, overrides=provenance)
    reset, cleared = apply_manual_override(
        doc,
        changed,
        provenance,
        ManualOverrideRequest(scope="/properties/total", operation="reset"),
        actor_ref_id="actor",
        permissions={"forms.override"},
    )
    assert reset["total"] == 5 and not cleared


def test_repeated_rows_use_relative_scopes():
    doc = FormDocuments(
        behavior_dialect="bpms.behavior/1",
        data_schema={
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "price": {"type": "number"},
                            "tax": {"type": "number"},
                            "total": {"type": "number"},
                        },
                    },
                }
            },
        },
        render_schema={
            "root": {
                "component": "vertical",
                "children": [
                    {
                        "component": "calculated",
                        "scope": "/properties/rows/items/properties/total",
                        "calculation": {
                            "function": "sum",
                            "scopes": [
                                "/properties/rows/items/properties/price",
                                "/properties/rows/items/properties/tax",
                            ],
                        },
                    }
                ],
            }
        },
    )
    result = evaluate_behavior(doc, {"rows": [{"price": 2, "tax": 1}, {"price": 4, "tax": 2}]})
    assert [row["total"] for row in result.data["rows"]] == [3, 6]


def test_nested_initialization_preserves_null_and_defaults_in_arrays():
    doc = FormDocuments(
        behavior_dialect="bpms.behavior/1",
        data_schema={
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {
                        "city": {"type": ["string", "null"], "default": "Paris"},
                        "zip": {"type": "string", "default": "000"},
                    },
                },
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"flag": {"type": "boolean", "default": True}},
                    },
                },
            },
        },
        render_schema={"root": {"component": "vertical"}},
    )
    result = evaluate_behavior(
        doc,
        {"address": {"city": None}, "rows": [{}]},
        initial={"address": {"city": "Rome", "zip": "123"}},
        initialize=True,
    )
    assert result.data["address"] == {"city": None, "zip": "123"}
    assert result.data["rows"][0]["flag"] is True


def test_decimal_sum_uses_canonical_numeric_precision():
    result = evaluate_behavior(documents(), {"price": 0.1, "quantity": 0.2})
    assert result.data["total"] == 0.3


def test_conditional_requirement_and_canonical_required_invariant():
    from apps.forms.application.validation import FormValidator

    doc = documents()
    doc.render_schema["root"]["children"][1]["rules"].append(
        {"scope": "/properties/enabled", "operator": "eq", "value": True, "effect": "require"}
    )
    with pytest.raises(BehaviorError, match="behavior.required"):
        evaluate_behavior(doc, {"enabled": True, "price": 1, "quantity": 2})
    doc.data_schema["required"] = ["note"]
    result = FormValidator().validate(
        doc, {"enabled": False, "price": 1, "quantity": 2, "note": "stale"}
    )
    assert not result.valid and result.issues[0].code == "behavior.hidden_tampered"
    hidden = FormValidator().validate(doc, {"enabled": False, "price": 1, "quantity": 2})
    assert not hidden.valid and hidden.issues[0].code == "data.required"


def test_undeclared_override_provenance_is_rejected():
    with pytest.raises(BehaviorError, match="behavior.override_invalid"):
        evaluate_behavior(
            documents(),
            {"price": 1, "quantity": 2},
            overrides={"/properties/name": {"value": "forged"}},
        )


def test_shared_client_expected_result_fixture():
    import json
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).resolve().parents[2] / "fixtures/form_behavior_v1.json").read_text()
    )
    doc = FormDocuments.model_validate(fixture["documents"])
    for case in fixture["cases"]:
        result = evaluate_behavior(
            doc, case["data"], initial=case.get("initial"), initialize=case.get("initialize", False)
        )
        assert result.data == case["expected"], case["name"]


def test_publish_rejects_ambiguous_repeated_dependencies():
    from apps.forms.application.validation import FormValidator

    doc = documents()
    doc.data_schema["properties"]["rows"] = {
        "type": "array",
        "items": {"type": "object", "properties": {"price": {"type": "number"}}},
    }
    repeated = "/properties/rows/items/properties/price"
    doc.render_schema["root"]["children"][0]["calculation"]["scopes"] = [repeated]
    result = FormValidator().validate(doc)
    assert not result.valid and result.issues[0].code == "behavior.ambiguous_scope"

    doc.render_schema["root"]["children"][0]["calculation"]["scopes"] = ["/properties/price"]
    doc.render_schema["root"]["children"][1]["rules"][0]["scope"] = repeated
    doc.render_schema["root"]["children"][1]["rules"][0]["value"] = 1
    result = FormValidator().validate(doc)
    assert not result.valid and result.issues[0].code == "behavior.ambiguous_scope"


def test_pinned_variant_uses_authored_render_for_behavior_and_attachments():
    from apps.forms.application.attachments import _collections
    from apps.forms.application.behavior import pinned_behavior_documents

    doc = documents()
    doc.data_schema["properties"]["files"] = {"type": "array", "items": {"type": "string"}}
    variant = {
        "key": "desktop",
        "priority": 1,
        "condition": "true",
        "render_schema": {
            "root": {
                "component": "vertical",
                "children": [
                    {
                        "component": "attachment_collection",
                        "scope": "/properties/files",
                    }
                ],
            }
        },
    }
    doc = FormDocuments.model_validate(doc.model_dump() | {"variants": [variant]})
    selected = pinned_behavior_documents(doc, {"variant_key": "desktop"})
    assert "/files" in _collections(selected.render_schema, {})
    assert selected.variants == []
    assert "/files" not in _collections(doc.render_schema, {})
