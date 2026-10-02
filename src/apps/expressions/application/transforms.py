"""Registered, explicit conversions for workflow TRANSFORM steps."""

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from time import perf_counter_ns
from typing import Any, Literal

from pydantic import ConfigDict, Field, JsonValue, model_validator

from apps.expressions.application.language import EvaluationRecord, _summary
from core.base_dto import BaseDTO

type Conversion = Literal[
    "string", "integer", "decimal", "boolean", "date", "date_time", "array", "object"
]
type NullBehavior = Literal["error", "preserve", "default"]

_INTEGER = re.compile(r"^-?(0|[1-9][0-9]{0,18})$")
_DECIMAL = re.compile(r"^-?(0|[1-9][0-9]{0,18})(\.[0-9]{1,18})?$")
_MAX_COLLECTION = 256
_MAX_STRING = 4096
_DATE_FORMAT = re.compile(r"^(?:[^%]|%(?:Y|m|d))*$")
_DATETIME_FORMAT = re.compile(r"^(?:[^%]|%(?:Y|m|d|H|M|S|f|z))*$")


class TransformSpec(BaseDTO):
    model_config = ConfigDict(extra="forbid", strict=True)

    conversion: Conversion
    null_behavior: NullBehavior = "error"
    default: JsonValue | None = None
    format: str | None = Field(default=None, max_length=128)
    projection: dict[str, str] | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_options(self) -> TransformSpec:
        if self.null_behavior == "default" and self.default is None:
            raise ValueError("default is required for default null behavior")
        if self.projection is not None and self.conversion != "object":
            raise ValueError("projection is only valid for object conversion")
        if self.conversion == "object" and not self.projection:
            raise ValueError("object conversion requires a projection")
        if self.format is not None and self.conversion not in {"string", "date", "date_time"}:
            raise ValueError("format is not supported by this conversion")
        if self.format and self.conversion == "date" and not _DATE_FORMAT.fullmatch(self.format):
            raise ValueError("date format contains a locale-dependent or unsupported directive")
        if (
            self.format
            and self.conversion == "date_time"
            and not _DATETIME_FORMAT.fullmatch(self.format)
        ):
            raise ValueError("date-time format contains an unsupported directive")
        return self


@dataclass(frozen=True, slots=True)
class TransformOutcome:
    value: Any
    record: EvaluationRecord


class TransformError(ValueError):
    def __init__(self, code: str, record: EvaluationRecord) -> None:
        super().__init__(code)
        self.code = code
        self.record = record


class _TransformLimit(ValueError):
    pass


class TransformEngine:
    def apply(self, spec: TransformSpec, value: Any) -> TransformOutcome:
        started = perf_counter_ns()
        summary = {"value": _summary(value)}
        try:
            if value is None:
                if spec.null_behavior == "preserve":
                    result = None
                elif spec.null_behavior == "default":
                    result = spec.default
                else:
                    raise ValueError("null")
            else:
                result = self._convert(spec, value)
            self._bounded(result)
        except (
            ValueError,
            TypeError,
            KeyError,
            InvalidOperation,
            OverflowError,
            json.JSONDecodeError,
        ) as exc:
            code = (
                "transform.limit"
                if isinstance(exc, _TransformLimit)
                or isinstance(value, str)
                and len(value) > _MAX_STRING
                or isinstance(value, (list, dict))
                and len(value) > _MAX_COLLECTION
                else f"transform.{spec.conversion}.invalid"
            )
            record = EvaluationRecord(summary, None, perf_counter_ns() - started, code)
            raise TransformError(code, record) from None
        return TransformOutcome(
            result, EvaluationRecord(summary, _summary(result), perf_counter_ns() - started)
        )

    def _convert(self, spec: TransformSpec, value: Any) -> Any:
        if spec.conversion == "string":
            if isinstance(value, (dict, list)):
                rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            elif isinstance(value, bool):
                rendered = "true" if value else "false"
            else:
                rendered = str(value)
            if spec.format is not None:
                if spec.format.count("{}") != 1 or "{" in spec.format.replace("{}", ""):
                    raise ValueError("unsafe format")
                rendered = spec.format.replace("{}", rendered)
            return rendered
        if spec.conversion == "integer":
            if isinstance(value, bool):
                raise ValueError("boolean is not integer input")
            if isinstance(value, int) and -(2**63) <= value < 2**63:
                return value
            if isinstance(value, str) and _INTEGER.fullmatch(value):
                result = int(value)
                if -(2**63) <= result < 2**63:
                    return result
            raise ValueError("invalid integer")
        if spec.conversion == "decimal":
            if isinstance(value, bool):
                raise ValueError("boolean is not decimal input")
            source = str(value)
            if not _DECIMAL.fullmatch(source):
                raise ValueError("invalid decimal")
            return Decimal(source)
        if spec.conversion == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str) and value in {"true", "false"}:
                return value == "true"
            raise ValueError("invalid boolean")
        if spec.conversion == "date":
            parsed = date.fromisoformat(value) if isinstance(value, str) else value
            if not isinstance(parsed, date) or isinstance(parsed, datetime):
                raise ValueError("invalid date")
            return parsed.strftime(spec.format) if spec.format else parsed.isoformat()
        if spec.conversion == "date_time":
            parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
            if not isinstance(parsed, datetime) or parsed.tzinfo is None:
                raise ValueError("timezone is required")
            parsed = parsed.astimezone(UTC)
            return (
                parsed.strftime(spec.format)
                if spec.format
                else parsed.isoformat().replace("+00:00", "Z")
            )
        if spec.conversion == "array":
            result = json.loads(value) if isinstance(value, str) else value
            if not isinstance(result, list):
                raise ValueError("not an array")
            return result
        if not isinstance(value, dict) or spec.projection is None:
            raise ValueError("not an object")
        return {key: self._pointer(value, pointer) for key, pointer in spec.projection.items()}

    @staticmethod
    def _pointer(value: dict[str, Any], pointer: str) -> Any:
        if not pointer.startswith("/") or len(pointer) > 512:
            raise ValueError("invalid pointer")
        current: Any = value
        for raw in pointer[1:].split("/"):
            key = raw.replace("~1", "/").replace("~0", "~")
            current = current[int(key)] if isinstance(current, list) else current[key]
        return current

    @staticmethod
    def _bounded(value: Any) -> None:
        stack = [(value, 0)]
        count = 0
        while stack:
            item, depth = stack.pop()
            count += 1
            if count > 1024 or depth > 16:
                raise _TransformLimit("limit")
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("non-finite")
            if isinstance(item, str) and len(item) > _MAX_STRING:
                raise _TransformLimit("limit")
            if isinstance(item, (list, tuple)):
                if len(item) > _MAX_COLLECTION:
                    raise _TransformLimit("limit")
                stack.extend((child, depth + 1) for child in item)
            elif isinstance(item, dict):
                if len(item) > _MAX_COLLECTION:
                    raise _TransformLimit("limit")
                stack.extend((child, depth + 1) for child in item.values())


def transform_schemas(spec: TransformSpec) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the declared input and output JSON Schemas for a transform configuration."""
    schemas: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
        "string": ({}, {"type": "string"}),
        "integer": ({"type": ["string", "integer"]}, {"type": "integer"}),
        "decimal": ({"type": ["string", "integer", "number"]}, {"type": "number"}),
        "boolean": ({"type": ["string", "boolean"]}, {"type": "boolean"}),
        "date": ({"type": "string"}, {"type": "string", "format": "date"}),
        "date_time": (
            {"type": "string", "format": "date-time"},
            {"type": "string", "format": "date-time"},
        ),
        "array": ({"type": ["string", "array"]}, {"type": "array"}),
        "object": (
            {"type": "object"},
            {
                "type": "object",
                "properties": {key: {} for key in (spec.projection or {})},
                "additionalProperties": False,
            },
        ),
    }
    input_schema, output_schema = schemas[spec.conversion]
    if spec.null_behavior == "preserve":
        output_types = (
            [output_schema["type"]]
            if isinstance(output_schema.get("type"), str)
            else output_schema.get("type", [])
        )
        output_schema = {**output_schema, "type": [*output_types, "null"]}
    return input_schema, output_schema
