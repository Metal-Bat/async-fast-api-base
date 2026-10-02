"""Host navigation results are typed atomic proposals, never implicit field writes."""

from copy import deepcopy

import pytest

from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments
from core.settings import settings


def navigation_documents():
    return FormDocuments(
        data_schema={
            "type": "object",
            "properties": {"person": {"type": "string"}, "name": {"type": "string"}},
        },
        render_schema={
            "root": {
                "component": "text",
                "scope": "/properties/person",
                "navigation": {
                    "route": "/people/pick",
                    "argument_schema": {
                        "type": "object",
                        "properties": {"current": {"type": "string"}},
                        "required": ["current"],
                    },
                    "arguments": {"current": "/properties/person"},
                    "result_schema": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                        "required": ["id", "name"],
                    },
                    "result_mappings": {
                        "/properties/person": "/properties/id",
                        "/properties/name": "/properties/name",
                    },
                },
            }
        },
    )


def test_navigation_results_are_atomic_and_cancel_preserves_values(monkeypatch):
    from apps.forms.application.navigation import apply_navigation_result, navigation_plan

    monkeypatch.setattr(settings, "FORM_NAVIGATION_ROUTES", ["/people/pick"])
    doc = navigation_documents()
    assert FormValidator().validate(doc).valid
    data = {"person": "old", "name": "Original"}
    before = deepcopy(data)
    plan = navigation_plan(doc, "/root", data)
    assert plan.route == "/people/pick" and plan.arguments == {"current": "old"}
    assert (
        apply_navigation_result(doc, "/root", data, None, plan.data_revision, cancelled=True)
        == before
    )
    with pytest.raises(ValueError):
        apply_navigation_result(doc, "/root", data, {"id": "new", "name": 7}, plan.data_revision)
    assert data == before
    assert apply_navigation_result(
        doc, "/root", data, {"id": "new", "name": "Updated"}, plan.data_revision
    ) == {"person": "new", "name": "Updated"}
    assert data == before
    with pytest.raises(ValueError):
        apply_navigation_result(
            doc,
            "/root",
            {"person": "changed", "name": "Original"},
            {"id": "new", "name": "Updated"},
            plan.data_revision,
        )


def test_navigation_cannot_target_read_only_or_unknown_paths(monkeypatch):
    monkeypatch.setattr(settings, "FORM_NAVIGATION_ROUTES", ["/people/pick"])
    doc = navigation_documents()
    doc.data_schema["properties"]["name"]["readOnly"] = True
    result = FormValidator().validate(doc)
    assert not result.valid
    assert result.issues[0].code == "navigation.write_protected"


def test_navigation_requires_host_policy():
    result = FormValidator().validate(navigation_documents())
    assert not result.valid
    assert result.issues[0].code == "navigation.host_policy"


def test_object_mapping_cannot_overwrite_read_only_descendant(monkeypatch):
    monkeypatch.setattr(settings, "FORM_NAVIGATION_ROUTES", ["/people/pick"])
    doc = navigation_documents()
    obj = {"type": "object", "properties": {"locked": {"type": "string", "readOnly": True}}}
    doc.data_schema["properties"]["profile"] = obj
    nav = doc.render_schema["root"]["navigation"]
    nav["result_schema"]["properties"]["profile"] = obj
    nav["result_mappings"] = {"/properties/profile": "/properties/profile"}
    result = FormValidator().validate(doc)
    assert not result.valid and result.issues[0].code == "navigation.write_protected"


def test_navigation_result_bindings_follow_compiled_local_references(monkeypatch):
    from apps.forms.application.navigation import apply_navigation_result, navigation_plan

    monkeypatch.setattr(settings, "FORM_NAVIGATION_ROUTES", ["/people/pick"])
    doc = navigation_documents()
    nav = doc.render_schema["root"]["navigation"]
    nav["result_schema"] = {
        "type": "object",
        "properties": {"person": {"$ref": "#/$defs/Person"}},
        "$defs": {
            "Person": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                "required": ["id", "name"],
            }
        },
        "required": ["person"],
    }
    nav["result_mappings"] = {
        "/properties/person": "/properties/person/properties/id",
        "/properties/name": "/properties/person/properties/name",
    }
    assert FormValidator().validate(doc).valid
    data = {"person": "old", "name": "Old"}
    plan = navigation_plan(doc, "/root", data)
    assert apply_navigation_result(
        doc, "/root", data, {"person": {"id": "new", "name": "New"}}, plan.data_revision
    ) == {"person": "new", "name": "New"}
