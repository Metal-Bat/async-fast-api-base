"""Shared pure input projection seam for workflow validation, preview and process execution."""

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from apps.forms.application.validation import compile_data_schema
from apps.forms.domain.document_limits import InvalidDocument, bounded_document
from apps.workflows.domain.dto import GraphBinding, GraphIssue
from apps.workflows.domain.object_projection import (
    MAX_FIELDS,
    ObjectFieldProjection,
    ProjectionError,
    project_object_fields,
    projection_conflicts,
    projection_schema,
    required_projection_paths,
)


@dataclass(frozen=True)
class InputField:
    projection: ObjectFieldProjection
    schema: dict[str, Any]
    ordinal: int
    value: Any


def _port_annotations(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize only non-validating reference annotations and redundant non-null port metadata."""
    result = deepcopy(schema)
    kinds = result.get("type")
    if result.get("not") == {"type": "null"} and (
        isinstance(kinds, str)
        and kinds != "null"
        or isinstance(kinds, list)
        and "null" not in kinds
    ):
        result.pop("not")
    result.pop("x-reference-kind", None)
    for key in ("properties", "$defs"):
        children = result.get(key)
        if isinstance(children, dict):
            result[key] = {
                name: _port_annotations(child) if isinstance(child, dict) else child
                for name, child in children.items()
            }
    for key in ("items", "additionalProperties"):
        if isinstance(result.get(key), dict):
            result[key] = _port_annotations(result[key])
    if isinstance(result.get("prefixItems"), list):
        result["prefixItems"] = [
            _port_annotations(child) if isinstance(child, dict) else child
            for child in result["prefixItems"]
        ]
    return result


def compiled_type_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Use the existing bounded local-reference schema profile, without ambient resolution."""
    try:
        bounded_document(schema, "/target_schema")
        return compile_data_schema(_port_annotations(schema))
    except InvalidDocument:
        raise ProjectionError("binding.projection.schema.invalid") from None


def compiled_object_schema(schema: dict[str, Any]) -> dict[str, Any]:
    compiled = compiled_type_schema(schema)
    if compiled.get("type") != "object" or not isinstance(compiled.get("properties"), dict):
        raise ProjectionError("binding.projection.root_object.required")
    return compiled


def compose_input_fields(
    fields: list[InputField], registered_schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not fields or len(fields) > MAX_FIELDS:
        raise ProjectionError("binding.projection.count.invalid")
    ordered = sorted(fields, key=lambda item: item.ordinal)
    if [item.ordinal for item in ordered] != list(range(len(ordered))):
        raise ProjectionError("binding.projection.ordinal.invalid")
    schema = ordered[0].schema
    if any(item.schema != schema for item in ordered):
        raise ProjectionError("binding.projection.schema.mismatch")
    compiled = compiled_object_schema(schema)
    result = project_object_fields([(item.projection, item.value) for item in ordered])
    if not Draft202012Validator(compiled, format_checker=FormatChecker()).is_valid(result):
        raise ProjectionError("binding.projection.value.invalid")
    if registered_schema is not None and not Draft202012Validator(
        registered_schema, format_checker=FormatChecker()
    ).is_valid(result):
        raise ProjectionError("binding.projection.registered_value.invalid")
    return result


def accepts_object_declaration(declared: dict[str, Any], registered: dict[str, Any]) -> bool:
    """Only refine an object-accepting generic port; fixed property contracts remain exact."""
    compiled_object_schema(declared)
    if registered.get("properties"):
        return declared == registered
    kinds = registered.get("type")
    generic_nonnull = registered == {"not": {"type": "null"}}
    if (
        registered
        and not generic_nonnull
        and kinds != "object"
        and not (isinstance(kinds, list) and "object" in kinds)
    ):
        return False
    return registered.get("additionalProperties") is not False


def projected_binding_issues(bindings: list[GraphBinding]) -> list[GraphIssue]:
    """Protocol checks independent of private port authorization and registered adapters."""
    groups: dict[tuple[str, str], list[tuple[int, GraphBinding]]] = defaultdict(list)
    for index, binding in enumerate(bindings):
        groups[(binding.step, binding.target_port)].append((index, binding))
    issues: list[GraphIssue] = []
    for rows in groups.values():
        projected = [
            (index, binding) for index, binding in rows if binding.target_projection is not None
        ]
        if not projected:
            continue
        first, binding = projected[0]
        pointer = f"/bindings/{first}"

        def add(code: str, location: str = pointer) -> None:
            issues.append(GraphIssue(pointer=location, code=code))

        if len(projected) != len(rows):
            add("binding.projection.whole_port.mixed")
        if len(rows) > MAX_FIELDS:
            add("binding.projection.count.invalid")
        if sorted(binding.ordinal for _, binding in rows) != list(range(len(rows))):
            add("binding.projection.ordinal.invalid")
        if any(other.target_schema != binding.target_schema for _, other in rows):
            add("binding.projection.schema.mismatch")
        try:
            compiled = compiled_object_schema(binding.target_schema)
        except ProjectionError as error:
            add(error.code)
            continue
        projections = [
            item.target_projection for _, item in projected if item.target_projection is not None
        ]
        if projection_conflicts(projections):
            add("binding.projection.overlap")
        if required_projection_paths(compiled, projections):
            add("binding.projection.required.missing")
        for index, item in projected:
            if item.target_projection is None:
                continue
            if projection_schema(compiled, item.target_projection) is None:
                issues.append(
                    GraphIssue(
                        pointer=f"/bindings/{index}/target_projection/path",
                        code="binding.projection.path.unknown",
                    )
                )
            if item.source_kind in {"REQUEST", "CONTEXT"} and item.source_schema is None:
                issues.append(
                    GraphIssue(
                        pointer=f"/bindings/{index}/source_schema",
                        code="binding.projection.source_schema.required",
                    )
                )
    return issues[:64]


def valid_binding_target(binding: GraphBinding, registered: dict[str, Any]) -> bool:
    if binding.target_projection is None:
        return binding.target_schema == registered
    try:
        return accepts_object_declaration(binding.target_schema, registered)
    except ProjectionError:
        return False


def validate_projected_constant(binding: GraphBinding) -> None:
    if binding.target_projection is None:
        raise ProjectionError("binding.projection.required")
    schema = projection_schema(
        compiled_object_schema(binding.target_schema), binding.target_projection
    )
    if schema is None or not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(
        binding.constant_value
    ):
        raise ProjectionError("binding.constant.invalid")
