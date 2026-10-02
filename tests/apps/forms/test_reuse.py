"""Publication resolves authored components into isolated canonical form snapshots."""

from copy import deepcopy

import pytest

from apps.forms.application.reuse import ResolvedComponent, compile_instances
from apps.forms.domain.dto import FormDocuments


def component() -> ResolvedComponent:
    return ResolvedComponent(
        ref_id="component-v3",
        checksum="c" * 64,
        data_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
        render_schema={
            "root": {
                "component": "vertical",
                "node_key": "address",
                "children": [
                    {
                        "component": "text",
                        "node_key": "city",
                        "scope": "/properties/city",
                        "label": "City",
                    }
                ],
            }
        },
        dependencies=[],
    )


def form() -> FormDocuments:
    return FormDocuments(
        data_schema={
            "type": "object",
            "properties": {"billing": {"type": "object"}, "shipping": {"type": "object"}},
        },
        render_schema={
            "root": {
                "component": "vertical",
                "children": [{"component": "vertical"}, {"component": "vertical"}],
            }
        },
    )


def test_two_instances_are_isolated_and_pinned():
    source = form()
    original = deepcopy(source)
    resolved, manifest = compile_instances(
        source,
        [
            {
                "instance_key": "billing",
                "component_ref": "component-v3",
                "schema_pointer": "/properties/billing",
                "node_pointer": "/root/children/0",
            },
            {
                "instance_key": "shipping",
                "component_ref": "component-v3",
                "schema_pointer": "/properties/shipping",
                "node_pointer": "/root/children/1",
            },
        ],
        {"component-v3": component()},
    )
    assert source == original
    assert resolved.data_schema["properties"]["billing"]["required"] == ["city"]
    assert (
        resolved.render_schema["root"]["children"][0]["children"][0]["scope"]
        == "/properties/billing/properties/city"
    )
    assert (
        resolved.render_schema["root"]["children"][1]["children"][0]["scope"]
        == "/properties/shipping/properties/city"
    )
    assert (
        resolved.render_schema["root"]["children"][0]["children"][0]["node_key"] == "billing.city"
    )
    assert (
        resolved.render_schema["root"]["children"][1]["children"][0]["node_key"] == "shipping.city"
    )
    assert len(manifest) == 1 and manifest[0]["checksum"] == "c" * 64


def test_reuse_rejects_duplicate_instances_and_overlapping_bindings():
    use = {
        "instance_key": "billing",
        "component_ref": "component-v3",
        "schema_pointer": "/properties/billing",
        "node_pointer": "/root/children/0",
    }
    with pytest.raises(ValueError):
        compile_instances(form(), [use, use], {"component-v3": component()})


def test_declared_parameters_can_customize_only_declared_target():
    reusable = component()
    reusable.parameters_schema = {
        "type": "object",
        "properties": {"heading": {"type": "string", "maxLength": 40}},
        "required": ["heading"],
        "additionalProperties": False,
    }
    reusable.parameter_targets = {"heading": "/root/children/0/label"}
    use = {
        "instance_key": "billing",
        "component_ref": "component-v3",
        "schema_pointer": "/properties/billing",
        "node_pointer": "/root/children/0",
        "parameters": {"heading": "Billing city"},
    }
    documents, _ = compile_instances(form(), [use], {"component-v3": reusable})
    assert documents.render_schema["root"]["children"][0]["children"][0]["label"] == "Billing city"
    with pytest.raises(ValueError):
        compile_instances(
            form(), [{**use, "parameters": {"unknown": "script()"}}], {"component-v3": reusable}
        )


def test_instance_messages_are_namespaced_and_only_declared_overrides_apply():
    from apps.forms.application.validation import FormValidator

    reusable = component()
    reusable.render_schema["root"]["children"][0]["messages"] = {"label": {"key": "city"}}
    reusable.messages = {"en": {"city": "City"}, "fa": {"city": "شهر"}}
    reusable.overridable_messages = ["city"]
    use = {
        "instance_key": "billing",
        "component_ref": "component-v3",
        "schema_pointer": "/properties/billing",
        "node_pointer": "/root/children/0",
        "message_overrides": {"en": {"city": "Billing city"}},
    }
    documents, _ = compile_instances(form(), [use], {"component-v3": reusable})
    node = documents.render_schema["root"]["children"][0]["children"][0]
    assert node["messages"]["label"]["key"] == "component.billing.city"
    assert documents.localization is not None
    assert documents.localization.catalogs["en"]["component.billing.city"].text == "Billing city"
    assert documents.localization is not None
    assert documents.localization.catalogs["fa"]["component.billing.city"].text == "شهر"
    assert FormValidator().validate(documents, publication=True).valid
    reusable.overridable_messages = []
    with pytest.raises(ValueError):
        compile_instances(form(), [use], {"component-v3": reusable})


def test_nested_component_catalogs_get_outer_instance_namespaces():
    from apps.forms.application.validation import FormValidator

    inner = component()
    inner.render_schema["root"]["children"][0]["messages"] = {"label": {"key": "city"}}
    inner.messages = {"en": {"city": "City"}, "fa": {"city": "شهر"}}
    parent_form = FormDocuments(
        data_schema={"type": "object", "properties": {"inside": {"type": "object"}}},
        render_schema={"root": {"component": "vertical", "children": [{"component": "vertical"}]}},
    )
    compiled, _ = compile_instances(
        parent_form,
        [
            {
                "instance_key": "inside",
                "component_ref": "component-v3",
                "schema_pointer": "/properties/inside",
                "node_pointer": "/root/children/0",
            }
        ],
        {"component-v3": inner},
    )
    assert compiled.localization is not None
    outer = ResolvedComponent(
        ref_id="outer-v1",
        checksum="d" * 64,
        data_schema=compiled.data_schema,
        render_schema=compiled.render_schema,
        dependencies=[],
        localization=compiled.localization.model_dump(),
    )
    documents, _ = compile_instances(
        form(),
        [
            {
                "instance_key": "billing",
                "component_ref": "outer-v1",
                "schema_pointer": "/properties/billing",
                "node_pointer": "/root/children/0",
            },
            {
                "instance_key": "shipping",
                "component_ref": "outer-v1",
                "schema_pointer": "/properties/shipping",
                "node_pointer": "/root/children/1",
            },
        ],
        {"outer-v1": outer},
    )
    assert FormValidator().validate(documents, publication=True).valid
    assert documents.localization is not None
    assert "component.billing.component.inside.city" in documents.localization.catalogs["en"]
    assert documents.localization is not None
    assert "component.shipping.component.inside.city" in documents.localization.catalogs["fa"]


def test_reusable_component_binds_inside_nested_arrays():
    from apps.forms.application.validation import FormValidator

    data_schema = {
        "type": "object",
        "properties": {
            "lines": {
                "type": "array",
                "items": {"type": "object", "properties": {"address": {"type": "object"}}},
            }
        },
    }
    render_schema = {
        "root": {
            "component": "repeater",
            "scope": "/properties/lines",
            "children": [{"component": "vertical"}],
        }
    }
    source = FormDocuments(data_schema=data_schema, render_schema=render_schema)
    resolved, _ = compile_instances(
        source,
        [
            {
                "instance_key": "line_address",
                "component_ref": "component-v3",
                "schema_pointer": "/properties/lines/items/properties/address",
                "node_pointer": "/root/children/0",
            }
        ],
        {"component-v3": component()},
    )
    assert (
        FormValidator()
        .validate(
            resolved, {"lines": [{"address": {"city": "Tehran"}}, {"address": {"city": "Shiraz"}}]}
        )
        .valid
    )
    assert (
        resolved.render_schema["root"]["children"][0]["children"][0]["scope"]
        == "/properties/lines/items/properties/address/properties/city"
    )
