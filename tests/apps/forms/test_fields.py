"""The published primitive catalog and validator must describe the same fields."""

import pytest

from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments, RenderDocument


def test_every_render_component_has_a_typed_versioned_catalog_contract():
    from apps.forms.application.fields import field_catalog
    from core.i18n import use_language

    with use_language("en"):
        english = field_catalog()
    with use_language("fa"):
        persian = field_catalog()
    assert len(english) == 20
    assert {item.key for item in english} == {item.key for item in persian}
    for field in english:
        assert field.version == 1
        assert field.node_kind in {"layout", "display", "control", "action"}
        assert field.options_schema["type"] == "object"
        assert field.options_schema["additionalProperties"] is False
        assert field.renderers == ["default", "compact"]
        assert field.description
    assert (
        next(x for x in english if x.key == "text").description
        != next(x for x in persian if x.key == "text").description
    )
    schema = RenderDocument.model_json_schema()
    assert set(schema["$defs"]["ComponentKind"]["enum"]) == {item.key for item in english}


def test_catalog_option_subset_is_the_validator_subset():
    from apps.forms.application.fields import field_catalog

    catalog = {str(item.key): item for item in field_catalog()}
    assert "rows" in catalog["textarea"].options_schema["properties"]
    assert "rows" not in catalog["integer"].options_schema["properties"]
    doc = FormDocuments(
        data_schema={"type": "object", "properties": {"age": {"type": "integer"}}},
        render_schema={
            "root": {"component": "integer", "scope": "/properties/age", "options": {"rows": 2}}
        },
    )
    assert not FormValidator().validate(doc).valid


def test_field_capabilities_fail_closed_or_use_declared_fallback():
    from apps.clients.domain.contracts import ClientContext
    from apps.forms.application.designs import resolve_form_documents

    doc = FormDocuments(
        data_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        render_schema={
            "root": {
                "component": "text",
                "scope": "/properties/name",
                "interaction": {"picker": "dialog", "required_capabilities": ["people.picker"]},
            }
        },
    )
    assert FormValidator().validate(doc).valid
    with pytest.raises(ValueError):
        resolve_form_documents(doc, ClientContext.legacy())
    doc.render_schema["root"]["interaction"]["fallback_renderer"] = "default"
    view = resolve_form_documents(doc, ClientContext.legacy())
    assert view.render_schema["root"]["interaction"]["picker"] == "inline"
    assert doc.render_schema["root"]["interaction"]["picker"] == "dialog"


def test_new_executable_behavior_is_rejected_until_its_owner_exists():
    doc = FormDocuments(
        data_schema={"type": "object", "properties": {}},
        render_schema={"root": {"component": "vertical", "on_change": "run_script()"}},
    )
    assert not FormValidator().validate(doc).valid
