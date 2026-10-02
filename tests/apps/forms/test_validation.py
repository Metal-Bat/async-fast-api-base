from copy import deepcopy
from typing import Any
from unittest.mock import Mock

import pytest

from apps.forms.application.service import FormService
from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import FormDocuments, ValidationResult


def documents() -> FormDocuments:
    return FormDocuments(
        data_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        render_schema={
            "dialect": "bpms.render/1",
            "root": {
                "component": "vertical",
                "children": [
                    {"component": "text", "scope": "/properties/name", "label": "Name"},
                    {"component": "integer", "scope": "/properties/age"},
                ],
            },
            "outcomes": ["approve"],
        },
    )


def test_valid_form_has_stable_checksum_and_safe_preview() -> None:
    validator = FormValidator()
    doc = documents()
    result = validator.validate(doc)
    assert result.valid and result.checksum is not None and len(result.checksum) == 64
    assert validator.validate(doc.model_copy(deep=True)).checksum == result.checksum
    assert validator.validate(doc, {"name": "Ada", "age": 4}).valid
    error = validator.validate(doc, {"age": "4"})
    assert not error.valid
    assert any(issue.pointer == "/data/age" for issue in error.issues)


def test_form_service_rejects_valid_result_without_checksum() -> None:
    service = FormService(Mock())
    service.validator = Mock()
    service.validator.validate.return_value = ValidationResult(valid=True, checksum=None)

    with pytest.raises(RuntimeError, match="checksum"):
        service._validate(documents())


@pytest.mark.parametrize(
    ("change", "pointer"),
    [
        ({"component": "javascript"}, "/render_schema/root/children/0/component"),
        ({"scope": "/properties/missing"}, "/render_schema/root/children/0/scope"),
        ({"component": "integer"}, "/render_schema/root/children/0/scope"),
        ({"renderer": "https://attacker/renderer"}, "/render_schema/root/children/0/renderer"),
        ({"options": {"onclick": "alert(1)"}}, "/render_schema/root/children/0/options/onclick"),
        ({"selector": "https://attacker/options"}, "/render_schema/root/children/0/selector"),
        (
            {"calculation": {"function": "eval", "scopes": []}},
            "/render_schema/root/children/0/calculation/function",
        ),
    ],
)
def test_invalid_render_reports_precise_pointer(change: dict[str, Any], pointer: str) -> None:
    doc = documents()
    doc.render_schema["root"]["children"][0].update(change)
    result = FormValidator().validate(doc)
    assert not result.valid
    assert pointer in {issue.pointer for issue in result.issues}


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "https://attacker/schema"},
        {"$defs": {"loop": {"$ref": "#/$defs/loop"}}, "$ref": "#/$defs/loop"},
        {"type": "string", "pattern": "(a+)+$"},
        {"type": "invalid"},
        {"allOf": [{"type": "string"}]},
    ],
)
def test_unsafe_or_invalid_data_schemas_are_rejected(schema: dict[str, Any]) -> None:
    doc = documents()
    doc.data_schema = schema
    assert not FormValidator().validate(doc).valid


def test_local_references_and_resource_limits() -> None:
    doc = documents()
    doc.data_schema["$defs"] = {"name": {"type": "string"}}
    doc.data_schema["properties"]["name"] = {"$ref": "#/$defs/name"}
    assert FormValidator().validate(doc).valid
    large = deepcopy(doc)
    large.data_schema["description"] = "x" * 70000
    assert FormValidator().validate(large).issues[0].code == "document.limit"
    nested = {"type": "string"}
    for _ in range(30):
        nested = {"type": "array", "items": nested}
    doc.data_schema = nested
    assert not FormValidator().validate(doc).valid


def test_datetime_format_and_scope_schema_location_are_enforced() -> None:
    doc = documents()
    doc.data_schema["properties"]["name"] = {"type": "string", "format": "date-time"}
    assert not FormValidator().validate(doc, {"name": "not-a-date"}).valid
    doc = documents()
    doc.data_schema["default"] = {"type": "string"}
    doc.render_schema["root"]["children"][0]["scope"] = "/default"
    assert not FormValidator().validate(doc).valid


def test_attachment_collection_contract_is_complete_and_bounded() -> None:
    doc = documents()
    doc.data_schema["properties"]["attachments"] = {
        "type": "array",
        "items": {"type": "string"},
    }
    doc.render_schema["root"]["children"].append(
        {
            "component": "attachment_collection",
            "scope": "/properties/attachments",
            "options": {
                "min_items": 1,
                "max_items": 5,
                "allowed_kinds": ["file", "image"],
                "allowed_mime_types": ["image/webp", "application/pdf"],
                "max_item_bytes": 5_000_000,
                "max_total_bytes": 15_000_000,
                "caption_required": True,
                "allow_duplicates": False,
                "preview": True,
                "camera": True,
                "allow_reorder": True,
                "allow_replace": True,
                "allow_remove": True,
            },
        }
    )
    assert FormValidator().validate(doc).valid

    doc.render_schema["root"]["children"][-1]["options"]["max_total_bytes"] = 1
    result = FormValidator().validate(doc)
    assert not result.valid


def test_calculated_values_and_rules_require_compatible_registered_inputs() -> None:
    doc = documents()
    doc.render_schema["root"]["children"][1] = {
        "component": "calculated",
        "scope": "/properties/age",
    }
    assert not FormValidator().validate(doc).valid
    doc.render_schema["root"]["children"][1]["calculation"] = {
        "function": "sum",
        "scopes": ["/properties/name"],
    }
    assert not FormValidator().validate(doc).valid
    doc.render_schema["root"]["children"][1]["calculation"]["scopes"] = ["/properties/age"]
    assert FormValidator().validate(doc).valid
    doc.render_schema["root"]["children"][0]["rules"] = [
        {"scope": "/properties/age", "operator": "eq", "value": "not-an-integer", "effect": "hide"}
    ]
    assert not FormValidator().validate(doc).valid


def test_calculated_expression_is_compiled_against_form_schema() -> None:
    doc = documents()
    doc.render_schema["root"]["children"][1] = {
        "component": "calculated",
        "scope": "/properties/age",
        "calculation": {"expression": "request.age + 1"},
    }
    assert FormValidator().validate(doc).valid

    doc.render_schema["root"]["children"][1]["calculation"]["expression"] = "request.missing + 1"
    result = FormValidator().validate(doc)
    assert result.issues[0].pointer.endswith("/calculation/expression")
    assert result.issues[0].code == "expression.path.unknown"

    doc.render_schema["root"]["children"][1]["calculation"]["expression"] = "request.name"
    assert FormValidator().validate(doc).issues[0].code == "expression.result.incompatible"
