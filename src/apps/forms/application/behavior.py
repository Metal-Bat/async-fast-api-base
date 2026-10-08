"""Deterministic evaluation of form defaults, calculations, and visibility."""

import ast
import hashlib
import json
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.expressions.application.language import (
    EvaluationError,
    ExpressionCompiler,
    ExpressionContext,
    ExpressionError,
)
from apps.forms.application.bindings import render_nodes
from apps.forms.domain.dto import FormDocuments

_MISSING = object()


class BehaviorError(ValueError):
    pass


class BehaviorResult:
    def __init__(self, data: dict[str, Any], cleared: list[str], required: list[str]):
        self.data = data
        self.cleared = cleared
        self.required = required


def _locations(
    data: dict[str, Any], scope: str, fixed: dict[str, int] | None = None
) -> list[tuple[str, dict[str, int]]]:
    tokens = scope.split("/")[1:]
    if not scope.startswith("/") or not tokens:
        raise BehaviorError("behavior.scope")
    positions: list[tuple[Any, str, dict[str, int]]] = [(data, "", {})]
    index = 0
    prefix = ""
    while index < len(tokens):
        keyword = tokens[index]
        if keyword == "properties" and index + 1 < len(tokens):
            raw = tokens[index + 1]
            key = raw.replace("~1", "/").replace("~0", "~")
            prefix += "/properties/" + raw
            positions = [
                (
                    node.get(key, _MISSING) if isinstance(node, dict) else _MISSING,
                    path + "/" + raw,
                    context,
                )
                for node, path, context in positions
            ]
            index += 2
        elif keyword == "items":
            prefix += "/items"
            expanded = []
            for node, path, context in positions:
                if not isinstance(node, list):
                    continue
                chosen = (fixed or {}).get(prefix)
                indices = [chosen] if chosen is not None else range(len(node))
                for item_index in indices:
                    if 0 <= item_index < len(node):
                        expanded.append(
                            (
                                node[item_index],
                                path + f"/{item_index}",
                                {**context, prefix: item_index},
                            )
                        )
            positions = expanded
            index += 1
        else:
            raise BehaviorError("behavior.scope")
    return [(path, context) for _, path, context in positions]


def _get_concrete(data: dict[str, Any], path: str) -> Any:
    node: Any = data
    for raw in path.split("/")[1:]:
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            node = node.get(key, _MISSING)
        elif isinstance(node, list) and key.isdecimal() and int(key) < len(node):
            node = node[int(key)]
        else:
            return _MISSING
    return node


def _put_concrete(data: dict[str, Any], path: str, value: Any) -> None:
    tokens = path.split("/")[1:]
    node: Any = data
    for raw in tokens[:-1]:
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            node = node.setdefault(key, {})
        elif isinstance(node, list) and key.isdecimal() and int(key) < len(node):
            node = node[int(key)]
        else:
            raise BehaviorError("behavior.scope")
    last = tokens[-1].replace("~1", "/").replace("~0", "~")
    if not isinstance(node, dict):
        raise BehaviorError("behavior.scope")
    if value is _MISSING:
        node.pop(last, None)
    else:
        node[last] = value


def _get(data: dict[str, Any], scope: str) -> Any:
    locations = _locations(data, scope)
    return _get_concrete(data, locations[0][0]) if len(locations) == 1 else _MISSING


def _put(data: dict[str, Any], scope: str, value: Any) -> None:
    locations = _locations(data, scope)
    if len(locations) != 1:
        raise BehaviorError("behavior.scope")
    _put_concrete(data, locations[0][0], value)


def _source_value(data: dict[str, Any], scope: str, context: dict[str, int]) -> Any:
    locations = _locations(data, scope, context)
    if len(locations) != 1:
        raise BehaviorError("behavior.ambiguous_scope")
    return _get_concrete(data, locations[0][0])


def _initial(current: dict[str, Any], supplied: dict[str, Any]) -> None:
    for key, value in supplied.items():
        if key not in current:
            current[key] = deepcopy(value)
        elif isinstance(current[key], dict) and isinstance(value, dict):
            _initial(current[key], value)


def _defaults(schema: dict[str, Any], data: Any) -> None:
    if isinstance(data, list) and isinstance(schema.get("items"), dict):
        for item in data:
            _defaults(schema["items"], item)
    if not isinstance(data, dict):
        return
    for key, child in schema.get("properties", {}).items():
        if key not in data and "default" in child:
            data[key] = deepcopy(child["default"])
        if key in data and isinstance(data[key], (dict, list)):
            _defaults(child, data[key])


def _expression_scopes(expression: str) -> list[str]:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise BehaviorError("behavior.expression") from exc
    scopes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            parts = []
            child = node
            while isinstance(child, ast.Attribute):
                parts.append(child.attr)
                child = child.value
            if isinstance(child, ast.Name) and child.id == "request":
                scopes.add("/properties/" + "/properties/".join(reversed(parts)))
    return sorted(scopes)


def _graph(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calculated = {
        node["scope"]: node for node in nodes if node.get("calculation") and node.get("scope")
    }
    if len(calculated) != sum(
        bool(node.get("calculation") and node.get("scope")) for node in nodes
    ):
        raise BehaviorError("behavior.duplicate_target")
    ordered: list[dict[str, Any]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(scope: str) -> None:
        if scope in visiting:
            raise BehaviorError("behavior.cycle")
        if scope in visited:
            return
        visiting.add(scope)
        calculation = calculated[scope]["calculation"]
        sources = calculation.get("scopes", [])
        if calculation.get("expression"):
            sources = _expression_scopes(calculation["expression"])
        for source in sources:
            if source in calculated:
                visit(source)
        visiting.remove(scope)
        visited.add(scope)
        ordered.append(calculated[scope])

    for scope in calculated:
        visit(scope)
    return ordered


def _matches(rule: dict[str, Any], data: dict[str, Any], context: dict[str, int]) -> bool:
    value = _source_value(data, rule["scope"], context)
    if rule["operator"] == "present":
        return value is not _MISSING and value is not None
    if value is _MISSING:
        return False
    return bool(
        (value == rule.get("value")) if rule["operator"] == "eq" else (value != rule.get("value"))
    )


def calculation_input_checksum(calculation: dict[str, Any], data: dict[str, Any]) -> str:
    scopes = calculation.get("scopes", [])
    if calculation.get("expression"):
        scopes = _expression_scopes(calculation["expression"])
    values = [_get(data, scope) for scope in scopes]
    if any(value is _MISSING for value in values):
        raise BehaviorError("behavior.override_stale")
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def evaluate_behavior(
    documents: FormDocuments,
    data: dict[str, Any],
    *,
    initial: dict[str, Any] | None = None,
    initialize: bool = False,
    authoritative: bool = False,
    overrides: dict[str, dict[str, Any]] | None = None,
    enforce_required: bool = True,
) -> BehaviorResult:
    """Return a copy; authoritative mode rejects submitted derived values that disagree."""
    from apps.forms.application.validation import _bounded, _Invalid

    try:
        _bounded(data, "/data")
    except _Invalid as exc:
        raise BehaviorError(exc.issue.code) from None
    current = deepcopy(data)
    if initialize:
        _initial(current, initial or {})
        _defaults(documents.data_schema, current)
    nodes = [node for _, node in render_nodes(documents.render_schema)]
    if len(nodes) > 1000:
        raise BehaviorError("behavior.limit")
    declared_overrides = {
        node["scope"]
        for node in nodes
        if node.get("scope") and (node.get("calculation") or {}).get("override_permission")
    }
    if set(overrides or {}) - declared_overrides:
        raise BehaviorError("behavior.override_invalid")
    for node in _graph(nodes):
        calculation = node["calculation"]
        for concrete, context in _locations(current, node["scope"]):
            sources = calculation.get("scopes", [])
            if calculation.get("expression"):
                sources = _expression_scopes(calculation["expression"])
            values = [_source_value(current, scope, context) for scope in sources]
            if any(value is _MISSING for value in values):
                value = _MISSING
            elif calculation.get("function") == "sum":
                try:
                    total = sum((Decimal(str(item)) for item in values), Decimal(0))
                except InvalidOperation as exc:
                    raise BehaviorError("behavior.numeric") from exc
                value = int(total) if total == total.to_integral_value() else float(total)
            elif calculation.get("function") == "concat":
                if any(not isinstance(item, str) for item in values):
                    raise BehaviorError("behavior.calculation_type")
                value = "".join(values)
            elif calculation.get("function") == "count":
                value = sum(len(item) for item in values)
            elif calculation.get("expression"):
                if context:
                    raise BehaviorError("behavior.expression_repeated")
                empty = {"type": "object", "properties": {}, "additionalProperties": False}
                try:
                    compiled = ExpressionCompiler().compile(
                        calculation["expression"],
                        {
                            "request": documents.data_schema,
                            "process": empty,
                            "current_user": empty,
                            "steps": empty,
                        },
                    )
                    value = compiled.evaluate(
                        ExpressionContext(request=current, process={}, current_user={}, steps={})
                    ).value
                except (ExpressionError, EvaluationError) as exc:
                    raise BehaviorError("behavior.expression") from exc
            else:
                raise BehaviorError("behavior.unsupported_calculation")
            existing = _get_concrete(current, concrete)
            override_key = node["scope"] if not context else concrete
            override = (overrides or {}).get(override_key)
            if override is not None:
                if (
                    not calculation.get("override_permission")
                    or not override.get("reason")
                    or not override.get("actor_ref_id")
                    or not override.get("recorded_at")
                ):
                    raise BehaviorError("behavior.override_invalid")
                if context or override.get("input_checksum") != calculation_input_checksum(
                    calculation, current
                ):
                    raise BehaviorError("behavior.override_stale")
                if existing is _MISSING or existing != override.get("value"):
                    raise BehaviorError("behavior.override_tampered")
                continue
            if authoritative and existing is not _MISSING and existing != value:
                raise BehaviorError("behavior.derived_tampered")
            _put_concrete(current, concrete, value)
    cleared: list[str] = []
    required: list[str] = []
    for node in nodes:
        scope = node.get("scope")
        if not scope:
            continue
        for concrete, context in _locations(current, scope):
            for rule in node.get("rules", []):
                if not _matches(rule, current, context):
                    continue
                if rule["effect"] == "hide":
                    if authoritative and _get_concrete(current, concrete) is not _MISSING:
                        raise BehaviorError("behavior.hidden_tampered")
                    _put_concrete(current, concrete, _MISSING)
                    cleared.append(concrete)
                elif rule["effect"] == "require":
                    required.append(concrete)
    if enforce_required:
        for concrete in required:
            if _get_concrete(current, concrete) in (_MISSING, None, ""):
                raise BehaviorError("behavior.required")
    try:
        _bounded(current, "/data")
    except _Invalid as exc:
        raise BehaviorError(exc.issue.code) from None
    return BehaviorResult(current, cleared, required)


def _item_contexts(scope: str) -> set[str]:
    if not scope:
        return set()
    parts = scope.split("/")[1:]
    contexts: set[str] = set()
    index = 0
    while index < len(parts):
        if parts[index] == "properties":
            index += 2
        elif parts[index] == "items":
            contexts.add("/" + "/".join(parts[: index + 1]))
            index += 1
        else:
            raise BehaviorError("behavior.scope")
    return contexts


def validate_behavior(documents: FormDocuments) -> None:
    if documents.behavior_dialect is None:
        return
    nodes = [node for _, node in render_nodes(documents.render_schema)]
    if len(nodes) > 1000:
        raise BehaviorError("behavior.limit")
    _graph(nodes)
    for node in nodes:
        target = node.get("scope", "")
        target_contexts = _item_contexts(target)
        calculation = node.get("calculation")
        if calculation:
            if calculation.get("expression") and target_contexts:
                raise BehaviorError("behavior.expression_repeated")
            sources = (
                _expression_scopes(calculation["expression"])
                if calculation.get("expression")
                else calculation.get("scopes", [])
            )
            if any(not _item_contexts(source) <= target_contexts for source in sources):
                raise BehaviorError("behavior.ambiguous_scope")
        if any(
            not _item_contexts(rule["scope"]) <= target_contexts for rule in node.get("rules", [])
        ):
            raise BehaviorError("behavior.ambiguous_scope")


def apply_manual_override(
    documents: FormDocuments,
    data: dict[str, Any],
    provenance: dict[str, dict[str, Any]] | None,
    command: Any,
    *,
    actor_ref_id: str,
    permissions: set[str],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    from jsonschema import Draft202012Validator

    from apps.forms.application.bindings import schema_at
    from utils.date_utils import get_datetime_utc

    if documents.behavior_dialect is None:
        raise BehaviorError("behavior.dialect")
    match = [
        node
        for _, node in render_nodes(documents.render_schema)
        if node.get("scope") == command.scope and node.get("calculation")
    ]
    if len(match) != 1:
        raise BehaviorError("behavior.override_target")
    calculation = match[0]["calculation"]
    if "/items/" in command.scope:
        raise BehaviorError("behavior.override_target")
    permission = calculation.get("override_permission")
    if not permission or ("*" not in permissions and permission not in permissions):
        raise BehaviorError("behavior.override_permission")
    result_data = deepcopy(data)
    result_provenance = deepcopy(provenance or {})
    if command.operation == "reset":
        result_provenance.pop(command.scope, None)
        _put(result_data, command.scope, _MISSING)
    else:
        if not command.reason or len(command.reason.strip()) < 8:
            raise BehaviorError("behavior.override_reason")
        target = schema_at(documents.data_schema, command.scope)
        if not Draft202012Validator(target).is_valid(command.value):
            raise BehaviorError("behavior.override_value")
        result_provenance[command.scope] = {
            "actor_ref_id": actor_ref_id,
            "reason": command.reason.strip(),
            "value": deepcopy(command.value),
            "input_checksum": calculation_input_checksum(calculation, result_data),
            "recorded_at": get_datetime_utc().isoformat(),
        }
        _put(result_data, command.scope, deepcopy(command.value))
    evaluated = evaluate_behavior(
        documents,
        result_data,
        authoritative=True,
        overrides=result_provenance,
        enforce_required=False,
    )
    return evaluated.data, result_provenance


def pinned_behavior_documents(
    documents: FormDocuments, design_snapshot: dict[str, Any] | None
) -> FormDocuments:
    """Use the authenticated variant key with its unlocalized pinned authoring render."""
    if documents.behavior_dialect is None:
        return documents
    key = (design_snapshot or {}).get("variant_key", "shared")
    if key == "shared":
        render = documents.render_schema
    else:
        match = next((item for item in documents.variants if item.key == key), None)
        if match is None:
            raise BehaviorError("behavior.variant")
        render = match.render_schema
    return documents.model_copy(
        deep=True,
        update={"render_schema": deepcopy(render), "variants": []},
    )
