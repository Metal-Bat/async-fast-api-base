"""Versioned object-field projection; no storage, runtime lookup or side effects."""

import json
import re
from copy import deepcopy
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from core.base_dto import BaseDTO

DIALECT = "bpms.binding.object/1"
MAX_FIELDS = 64
MAX_BYTES = 262144


def pointer_parts(path: str) -> tuple[str, ...]:
    if (
        len(path.encode("utf-8")) > 1024
        or not path.startswith("/")
        or re.search(r"~(?:[^01]|$)", path)
    ):
        raise ValueError("binding.projection.path.invalid")
    parts = tuple(segment.replace("~1", "/").replace("~0", "~") for segment in path[1:].split("/"))
    if len(parts) > 12 or any(part in {"__proto__", "constructor", "prototype"} for part in parts):
        raise ValueError("binding.projection.path.invalid")
    return parts


class ObjectFieldProjection(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: Literal["bpms.binding.object/1"]
    path: str = Field(
        min_length=1,
        max_length=1024,
        description="RFC 6901 destination within declared object properties; no array containers, overlap or prototype keys. Explicit null is preserved and validated.",
    )

    @field_validator("path")
    @classmethod
    def valid_path(cls, value: str) -> str:
        pointer_parts(value)
        return value


class ProjectionError(ValueError):
    """Safe structural code only; never echo a sample or runtime value."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def projection_schema(
    schema: dict[str, Any], projection: ObjectFieldProjection
) -> dict[str, Any] | None:
    current = schema
    for segment in pointer_parts(projection.path):
        kinds = current.get("type")
        if kinds != "object" and not (isinstance(kinds, list) and "object" in kinds):
            return None
        properties = current.get("properties")
        child = properties.get(segment) if isinstance(properties, dict) else None
        if not isinstance(child, dict):
            return None
        current = child
    return current


def projection_conflicts(projections: list[ObjectFieldProjection]) -> bool:
    parts = [pointer_parts(item.path) for item in projections]
    return any(
        left[: min(len(left), len(right))] == right[: min(len(left), len(right))]
        for index, left in enumerate(parts)
        for right in parts[index + 1 :]
    )


def project_object_fields(fields: list[tuple[ObjectFieldProjection, Any]]) -> dict[str, Any]:
    if not fields or len(fields) > MAX_FIELDS:
        raise ProjectionError("binding.projection.count.invalid")
    if projection_conflicts([item for item, _ in fields]):
        raise ProjectionError("binding.projection.overlap")
    result: dict[str, Any] = {}
    for projection, value in fields:
        parts = pointer_parts(projection.path)
        current = result
        for segment in parts[:-1]:
            current = current.setdefault(segment, {})
        current[parts[-1]] = deepcopy(value)
    try:
        size = len(
            json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
        )
    except TypeError, ValueError:
        raise ProjectionError("binding.projection.value.invalid") from None
    if size > MAX_BYTES:
        raise ProjectionError("binding.projection.size.exceeded")
    return result


def required_projection_paths(
    schema: dict[str, Any], projections: list[ObjectFieldProjection]
) -> list[str]:
    """Find required declared structure not covered by an assigned property or its descendants."""
    assigned = [pointer_parts(item.path) for item in projections]
    missing: list[str] = []

    def visit(current: dict[str, Any], prefix: tuple[str, ...]) -> None:
        if any(prefix[: len(path)] == path for path in assigned):
            return
        properties = current.get("properties", {})
        required = current.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list) or len(prefix) > 12:
            return
        for name in required:
            path = (*prefix, str(name))
            if not any(item[: len(path)] == path for item in assigned):
                missing.append(
                    "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)
                )
            elif isinstance(properties.get(name), dict):
                visit(properties[name], path)

    visit(schema, ())
    return missing[:64]


def projection_from_facts(
    version: int | None, path: str | None, schema: dict[str, Any] | None
) -> ObjectFieldProjection | None:
    """Explicit private-fact mapping; unsupported/corrupt facts cannot become legacy bindings."""
    if version is None and path is None and schema is None:
        return None
    if version != 1 or path is None or schema is None:
        raise ProjectionError("binding.projection.stored_contract.invalid")
    return ObjectFieldProjection(dialect=DIALECT, path=path)
