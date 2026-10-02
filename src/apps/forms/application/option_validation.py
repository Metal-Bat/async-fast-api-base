"""Pure configuration and pinned-membership validation for option sources."""

import hashlib
import json
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from pydantic import TypeAdapter

from apps.expressions.application.language import (
    EvaluationError,
    ExpressionCompiler,
    ExpressionContext,
    ExpressionError,
)
from apps.forms.application.bindings import MISSING, bound_value, render_nodes, schema_at, values_at
from apps.forms.domain.options import (
    CustomSource,
    DomainSource,
    OptionSource,
    RemoteSource,
    Scalar,
    SchemaSource,
)
from core.settings import settings

_SOURCE: TypeAdapter[OptionSource] = TypeAdapter(OptionSource)
_SCALAR: TypeAdapter[Scalar] = TypeAdapter(Scalar)


def encode_choice_key(value: Any) -> str:
    scalar = _SCALAR.validate_python(value)
    return "json:" + json.dumps(scalar, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def decode_choice_key(value: str) -> Scalar:
    if not value.startswith("json:") or len(value) > 4096:
        raise ValueError("Invalid json-scalar/1 key")
    result = _SCALAR.validate_python(json.loads(value[5:]))
    if encode_choice_key(result) != value:
        raise ValueError("Noncanonical json-scalar/1 key")
    return result


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def effective_source(node: dict[str, Any]) -> OptionSource | None:
    if node.get("source") is not None:
        return _SOURCE.validate_python(node["source"])
    selector = node.get("selector") or {"user": "users", "group": "work_groups"}.get(
        node["component"]
    )
    if selector in {"users", "work_groups"}:
        return DomainSource.model_validate({"selector": selector})
    if node["component"] == "choice":
        return SchemaSource()
    return None


def is_multiple(target: dict[str, Any]) -> bool:
    types = target.get("type", [])
    return (
        types == "array" if isinstance(types, str) else isinstance(types, list) and "array" in types
    )


def choice_schema(target: dict[str, Any]) -> dict[str, Any]:
    return target.get("items", {}) if is_multiple(target) else target


def schema_keys(target: dict[str, Any]) -> list[Any]:
    target = choice_schema(target)
    return target.get("enum", [target["const"]] if "const" in target else [])


def source_parameters(
    source: OptionSource, schema: dict[str, Any], data: Any, rows: list[int]
) -> dict[str, Any] | None:
    parameters = {
        name: bound_value(schema, data, scope, rows) for name, scope in source.dependencies.items()
    }
    if any(value is MISSING or value is None for value in parameters.values()):
        return None
    if any(
        not Draft202012Validator(schema_at(schema, source.dependencies[name])).is_valid(value)
        for name, value in parameters.items()
    ):
        return None
    if source.enabled_when:
        try:
            expression = ExpressionCompiler().compile(
                source.enabled_when, {"request": schema}, expected_schema={"type": "boolean"}
            )
            enabled = expression.evaluate(
                ExpressionContext(request=data, process={}, current_user={}, steps={})
            ).value
        except ExpressionError, EvaluationError:
            return None
        if enabled is not True:
            return None
    return parameters


def custom_choices(source: CustomSource, parameters: dict[str, Any]):
    return [
        item
        for item in source.items
        if all(
            name in parameters and encode_choice_key(parameters[name]) == encode_choice_key(value)
            for name, value in item.matches.items()
        )
    ]


def validate_source(
    node: dict[str, Any], schema: dict[str, Any], path: str
) -> tuple[str, str] | None:
    source = effective_source(node)
    if source is None:
        return None
    target = schema_at(schema, node["scope"])
    item_schema = choice_schema(target)
    base = path + "/source"
    key_types = item_schema.get("type", [])
    key_types = {key_types} if isinstance(key_types, str) else set(key_types)
    if not key_types - {"null"} or not key_types - {"null"} <= {
        "string",
        "integer",
        "number",
        "boolean",
    }:
        return base, "source.scalar_required"
    if node.get("source") is not None and node.get("selector") is not None:
        return base, "source.ambiguous"
    if node["component"] not in {"choice", "user", "group"}:
        return base, "source.component"
    try:
        for scope in source.dependencies.values():
            dependency = schema_at(schema, scope)
            types = dependency.get("type", [])
            types = {types} if isinstance(types, str) else set(types)
            if not types - {"null"} or not types - {"null"} <= {
                "string",
                "integer",
                "number",
                "boolean",
            }:
                return base + "/dependencies", "source.dependency"
            repeated_parent = scope.rsplit("/items", 1)[0] + "/items"
            if (
                "/items" in scope
                and not node["scope"].startswith(repeated_parent + "/")
                and node["scope"] != repeated_parent
            ):
                return base + "/dependencies", "source.dependency"
        if source.enabled_when:
            ExpressionCompiler().compile(
                source.enabled_when, {"request": schema}, expected_schema={"type": "boolean"}
            )
    except ValueError, KeyError, ExpressionError:
        return base + "/dependencies", "source.dependency"
    if isinstance(source, (SchemaSource, RemoteSource)):
        keys = schema_keys(target)
        if not keys:
            return base, "source.enum_required"
        try:
            for key in keys:
                if key is not None:
                    encode_choice_key(key)
        except ValueError:
            return base, "source.scalar_required"
    if isinstance(source, CustomSource):
        keys = [encode_choice_key(item.key) for item in source.items]
        if len(set(keys)) != len(keys):
            return base + "/items", "source.duplicate_key"
        for item in source.items:
            if not Draft202012Validator(item_schema).is_valid(item.key):
                return base + "/items", "source.key_type"
            if item.matches.keys() - source.dependencies.keys():
                return base + "/items", "source.dependency"
            for name, value in item.matches.items():
                if not Draft202012Validator(schema_at(schema, source.dependencies[name])).is_valid(
                    value
                ):
                    return base + "/items", "source.dependency_type"
    if isinstance(source, DomainSource):
        types = item_schema.get("type", [])
        if (set(types) - {"null"} if isinstance(types, list) else {types}) != {"string"}:
            return base, "source.key_type"
        if source.dependencies.keys() - ({"group_ref"} if source.selector == "users" else set()):
            return base + "/dependencies", "source.dependency"
        if "group_ref" in source.dependencies:
            dependency_type = schema_at(schema, source.dependencies["group_ref"]).get("type", [])
            if (
                set(dependency_type) - {"null"}
                if isinstance(dependency_type, list)
                else {dependency_type}
            ) != {"string"}:
                return base + "/dependencies", "source.dependency_type"
        if (
            node["component"] in {"user", "group"}
            and source.selector != {"user": "users", "group": "work_groups"}[node["component"]]
        ):
            return base, "source.component"
    if isinstance(source, RemoteSource):
        url = urlsplit(source.url)
        if (
            source.url not in settings.FORM_CLIENT_OPTION_URLS
            or url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            return base + "/url", "source.host_policy"
        names = [
            source.search_parameter,
            source.page_parameter,
            source.size_parameter,
            source.selected_parameter,
            *source.dependencies,
        ]
        if len(set(names)) != len(names) or any(
            not pointer.startswith("/")
            for pointer in (source.items_pointer, source.key_pointer, source.value_pointer)
        ):
            return base, "source.mapping"
    return None


def validate_source_graph(renders: list[dict[str, Any]]) -> tuple[str, str] | None:
    explicit_scopes = {
        node["scope"]
        for render in renders
        for _, node in render_nodes(render)
        if node.get("source") is not None
    }
    definitions: dict[str, str] = {}
    graph: dict[str, set[str]] = {}
    for render in renders:
        for path, node in render_nodes(render):
            if node.get("scope") not in explicit_scopes:
                continue
            source = effective_source(node)
            if source is None:
                continue
            scope = node["scope"]
            revision = digest(source.model_dump())
            if scope in definitions and definitions[scope] != revision:
                return path + "/source", "source.variant_conflict"
            definitions[scope] = revision
            graph[scope] = set(source.dependencies.values())
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(scope: str) -> bool:
        if scope in visiting:
            return False
        if scope in visited:
            return True
        visiting.add(scope)
        if not all(visit(child) for child in graph.get(scope, set())):
            return False
        visiting.remove(scope)
        visited.add(scope)
        return True

    if not all(visit(scope) for scope in graph):
        return "/source/dependencies", "source.cycle"
    return None


def static_membership_issues(
    render: dict[str, Any], schema: dict[str, Any], data: Any
) -> list[tuple[str, str]]:
    issues = []
    for _, node in render_nodes(render):
        if node.get("source") is None:
            continue
        source = effective_source(node)
        if source is None or isinstance(source, DomainSource):
            continue
        target = schema_at(schema, node["scope"])
        for path, value, rows in values_at(schema, data, node["scope"]):
            if value is MISSING or value is None:
                continue
            parameters = source_parameters(source, schema, data, rows)
            keys = (
                []
                if parameters is None
                else [item.key for item in custom_choices(source, parameters)]
                if isinstance(source, CustomSource)
                else schema_keys(target)
            )
            allowed = {encode_choice_key(key) for key in keys if key is not None}
            values = value if is_multiple(target) else [value]
            if any(item is None or encode_choice_key(item) not in allowed for item in values):
                issues.append((path, "source.membership"))
                if len(issues) == 32:
                    return issues
    return issues
