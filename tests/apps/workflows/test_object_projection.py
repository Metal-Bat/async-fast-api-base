"""Object fields keep types, nulls, arrays, order and source isolation without effects."""

from typing import Any

import pytest

from apps.workflows.application.object_projection import (
    InputField,
    compose_input_fields,
    projected_binding_issues,
)
from apps.workflows.domain.dto import GraphBinding
from apps.workflows.domain.object_projection import (
    ObjectFieldProjection,
    ProjectionError,
    project_object_fields,
    projection_schema,
)


def projection(path):
    return ObjectFieldProjection(dialect="bpms.binding.object/1", path=path)


SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "customer": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "note": {"type": ["string", "null"]}},
            "required": ["name", "note"],
            "additionalProperties": False,
        },
        "count": {"type": "integer"},
        "flag": {"type": "boolean"},
        "items": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["customer", "count", "flag", "items"],
}


def fields():
    return [
        InputField(projection(path), SCHEMA, index, value)
        for index, (path, value) in enumerate(
            [
                ("/customer/name", "Example"),
                ("/customer/note", None),
                ("/count", 0),
                ("/flag", False),
                ("/items", [1, 2]),
            ]
        )
    ]


def test_nested_object_preserves_null_zero_false_arrays_and_source_values():
    values = fields()
    result = compose_input_fields(
        list(reversed(values)), {"type": "object", "not": {"type": "null"}}
    )
    assert result == {
        "customer": {"name": "Example", "note": None},
        "count": 0,
        "flag": False,
        "items": [1, 2],
    }
    result["items"].append(3)
    assert values[-1].value == [1, 2]


@pytest.mark.parametrize("paths", [["/customer", "/customer/name"], ["/count", "/count"]])
def test_conflicts_never_depend_on_order(paths):
    for order in (paths, list(reversed(paths))):
        with pytest.raises(ProjectionError, match="overlap"):
            project_object_fields(
                [(projection(path), "private-sample-never-echo") for path in order]
            )


def test_schema_projection_uses_data_properties_rather_than_schema_keyword_paths():
    assert projection_schema(SCHEMA, projection("/customer/name")) == {"type": "string"}
    assert projection_schema(SCHEMA, projection("/properties/customer/name")) is None
    assert projection_schema(SCHEMA, projection("/items/0")) is None


@pytest.mark.parametrize("change", ["missing", "boolean_number", "gap", "shape", "remote_schema"])
def test_invalid_values_and_instructions_fail_with_safe_codes(change):
    values = fields()
    if change == "missing":
        values = values[1:]
    if change == "boolean_number":
        values[2] = InputField(values[2].projection, SCHEMA, 2, False)
    if change == "gap":
        values[0] = InputField(values[0].projection, SCHEMA, 10, "private-sample-never-echo")
    if change == "shape":
        values[0] = InputField(values[0].projection, {**SCHEMA, "required": []}, 0, "Example")
    if change == "remote_schema":
        invalid = {
            **SCHEMA,
            "properties": {
                **SCHEMA["properties"],
                "external": {"$ref": "http://127.0.0.1/private"},
            },
        }
        values = [InputField(item.projection, invalid, item.ordinal, item.value) for item in values]
    with pytest.raises(ProjectionError) as error:
        compose_input_fields(values)
    assert str(error.value).startswith("binding.projection.")
    assert "private-sample" not in str(error.value)


def test_group_rejects_missing_required_fields_mixed_whole_bindings_and_undeclared_sources():
    bindings = [
        GraphBinding(
            step="review",
            target_port="data",
            target_schema=SCHEMA,
            ordinal=index,
            source_kind="CONSTANT",
            constant_value=value,
            target_projection=projection(path),
        )
        for index, (path, value) in enumerate(
            [
                ("/customer/name", "Example"),
                ("/count", 0),
                ("/flag", False),
                ("/items", []),
            ]
        )
    ]
    assert "binding.projection.required.missing" in {
        issue.code for issue in projected_binding_issues(bindings)
    }
    whole = bindings[0].model_copy(update={"target_projection": None})
    assert "binding.projection.whole_port.mixed" in {
        issue.code for issue in projected_binding_issues([whole, *bindings[1:]])
    }
    request = bindings[0].model_copy(
        update={"source_kind": "REQUEST", "source_path": "/name", "source_schema": None}
    )
    assert "binding.projection.source_schema.required" in {
        issue.code for issue in projected_binding_issues([request])
    }


def test_runtime_registered_contract_still_rejects_an_author_declaration_that_would_weaken_it():
    with pytest.raises(ProjectionError, match="registered_value.invalid"):
        compose_input_fields(fields(), {"type": "object", "maxProperties": 1})
