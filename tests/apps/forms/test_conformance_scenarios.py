"""Saved purchase-request vectors executed through the production form seams."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest

from apps.clients.domain.contracts import ClientContext
from apps.forms.application.behavior import apply_manual_override, evaluate_behavior
from apps.forms.application.collections import edit_collection, initialize_identity, issue_item_keys
from apps.forms.application.designs import resolve_form_documents
from apps.forms.application.navigation import apply_navigation_result, navigation_plan
from apps.forms.application.options import OptionService
from apps.forms.application.reuse import ResolvedComponent, compile_instances
from apps.forms.application.validation import FormValidator
from apps.forms.domain.behavior import ManualOverrideRequest
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.options import OptionQuery
from apps.users.domain.entity import UserEntity
from core.i18n import use_language
from core.settings import settings

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/scenarios/purchase-request-v1.json"


def scenario():
    return json.loads(FIXTURE.read_text())


async def replay_saved_purchase_request_form(monkeypatch, vector=None):
    """Exercise the saved client interaction vector through production form services."""
    vector = vector or scenario()
    monkeypatch.setattr(settings, "FORM_NAVIGATION_ROUTES", ["/people/pick"])
    doc = FormDocuments.model_validate(vector["documents"])
    assert FormValidator().validate(doc, publication=True).valid
    actor = UserEntity(username="purchase-actor", hashed_password="hash")
    report = {"views": {}, "trace": [], "issues": [], "submitted": None}
    for locale in vector["locales"]:
        resolved = resolve_form_documents(doc, ClientContext.legacy(), locale=locale)
        assert resolved.localization is not None
        report["views"][locale] = {
            "variant": resolved.key,
            "label": resolved.render_schema["root"]["children"][0]["label"],
            "resolved_locale": resolved.localization.resolved_locale,
        }
    data = deepcopy(vector["initial_data"])
    identity = initialize_identity(data, schema=doc.data_schema)
    report["trace"].append({"step": "initial", "row_count": len(data["lines"])})
    row_labels = {
        key: f"line_{row['sku'][-1]}"
        for key, row in zip(identity["/lines"], data["lines"], strict=True)
    }
    actions = vector["actions"]
    first = identity[actions[0]["path"]][actions[0]["item_index"]]
    moved = edit_collection(
        data,
        identity,
        actions[0]["path"],
        actions[0]["operation"],
        item_key=first,
        target_index=actions[0]["target_index"],
        schema=doc.data_schema,
    )
    data, identity = moved.data, moved.identity
    report["trace"].append(
        {
            "step": "reorder",
            "sku_order": [row["sku"] for row in data["lines"]],
            "index_map": {str(k): v for k, v in moved.index_map.items()},
        }
    )
    removed = edit_collection(
        data,
        identity,
        actions[1]["path"],
        actions[1]["operation"],
        item_key=identity[actions[1]["path"]][actions[1]["item_index"]],
        schema=doc.data_schema,
    )
    data, identity = removed.data, removed.identity
    report["trace"].append(
        {
            "step": "remove",
            "sku_order": [row["sku"] for row in data["lines"]],
            "index_map": {str(k): v for k, v in removed.index_map.items()},
        }
    )
    nested = edit_collection(
        data,
        identity,
        actions[2]["path"],
        actions[2]["operation"],
        item_key=identity[actions[2]["path"]][actions[2]["item_index"]],
        target_index=actions[2]["target_index"],
        schema=doc.data_schema,
    )
    data, identity = nested.data, nested.identity
    report["trace"].append(
        {
            "step": "nested_reorder",
            "reasons": [item["reason"] for item in data["lines"][0]["adjustments"]],
        }
    )
    nested = edit_collection(
        data,
        identity,
        actions[3]["path"],
        actions[3]["operation"],
        item_key=identity[actions[3]["path"]][actions[3]["item_index"]],
        schema=doc.data_schema,
    )
    data, identity = nested.data, nested.identity
    report["trace"].append(
        {
            "step": "nested_remove",
            "reasons": [item["reason"] for item in data["lines"][0]["adjustments"]],
        }
    )
    data = evaluate_behavior(doc, data).data
    report["trace"].append({"step": "calculate", "total": data["total"]})
    hidden = evaluate_behavior(doc, {**data, "country": "GB"})
    report["trace"].append(
        {"step": "rule", "cleared": hidden.cleared, "note_present": "note" in hidden.data}
    )
    denied = FormValidator().validate(
        doc, {**data, "lines": [{**data["lines"][0], "quantity": "bad"}]}
    )
    report["issues"] = [
        {
            "code": issue.code,
            "pointer": issue.pointer,
            "item_keys": [row_labels[key] for key in issue_item_keys(issue.pointer, identity)],
        }
        for issue in denied.issues
    ]
    with use_language("en"):
        older = await OptionService(Mock()).resolve(
            doc, OptionQuery(node_pointer="/root/children/3", data=data, generation=1), actor
        )
        newer_data = {**data, "country": "GB"}
        newer = await OptionService(Mock()).resolve(
            doc, OptionQuery(node_pointer="/root/children/3", data=newer_data, generation=2), actor
        )
    report["trace"].append(
        {
            "step": "option_race",
            "older": older.generation,
            "newer": newer.generation,
            "fingerprints_differ": older.dependency_fingerprint != newer.dependency_fingerprint,
            "new_keys": [item.key for item in newer.items],
        }
    )
    plan = navigation_plan(doc, "/root/children/4", data)
    changed = {**data, "requester": vector["fake_results"]["changed_requester"]}
    with pytest.raises(ValueError, match="stale"):
        apply_navigation_result(
            doc,
            "/root/children/4",
            changed,
            vector["fake_results"]["navigation"],
            plan.data_revision,
        )
    report["trace"].append({"step": "navigation_stale", "preserved": changed["requester"]})
    with pytest.raises(ValueError, match="behavior.override_permission"):
        apply_manual_override(
            doc,
            data,
            None,
            ManualOverrideRequest(
                scope="/properties/total", operation="set", value=30, reason="Approved price"
            ),
            actor_ref_id="actor",
            permissions=set(),
        )
    data, provenance = apply_manual_override(
        doc,
        data,
        None,
        ManualOverrideRequest(
            scope="/properties/total", operation="set", value=30, reason="Approved price"
        ),
        actor_ref_id="actor",
        permissions=set(vector["actor"]["permissions"]),
    )
    report["trace"].append(
        {
            "step": "override",
            "total": data["total"],
            "reason": provenance["/properties/total"]["reason"],
        }
    )
    assert FormValidator().validate(doc, data, overrides=provenance).valid
    report["submitted"] = data
    expected = deepcopy(vector["expected"])
    assert report == expected
    return report


@pytest.mark.anyio
async def test_saved_purchase_request_form_scenario(monkeypatch):
    await replay_saved_purchase_request_form(monkeypatch)


def test_saved_address_component_is_compiled_twice():
    vector = scenario()["reuse"]
    component = ResolvedComponent(**vector["component"])
    parent = FormDocuments.model_validate(vector["parent"])
    compiled, pins = compile_instances(parent, vector["uses"], {component.ref_id: component})
    assert FormValidator().validate(compiled, vector["data"]).valid
    assert [
        child["children"][0]["scope"] for child in compiled.render_schema["root"]["children"]
    ] == vector["expected_scopes"]
    assert pins[0]["checksum"] == component.checksum


def test_saved_unsupported_client_capability():
    vector = scenario()
    doc = FormDocuments.model_validate(vector["documents"])
    missing = ClientContext(kind="WEB", release="2.10")
    with pytest.raises(ValueError, match="required renderer capabilities"):
        resolve_form_documents(doc, missing, locale="fa")
    supported = ClientContext(
        kind="WEB", release="2.10", renderer_capabilities=frozenset({"picker.bottom_sheet"})
    )
    assert resolve_form_documents(doc, supported, locale="fa").key == "web_picker"
