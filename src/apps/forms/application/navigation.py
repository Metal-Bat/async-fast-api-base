"""Validate and preview atomic host-navigation mappings on canonical data copies."""

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from apps.expressions.application.language import ExpressionCompiler
from apps.forms.application.bindings import (
    MISSING,
    bound_value,
    render_nodes,
    schema_at,
    scope_parts,
)
from apps.forms.application.option_validation import digest
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.interaction import NavigationContract, NavigationPlan
from core.settings import settings


def validate_navigation(
    node: dict[str, Any], schema: dict[str, Any], path: str, protected: set[str]
) -> tuple[str, str] | None:
    navigation = NavigationContract.model_validate(node["navigation"])
    base = path + "/navigation"
    if (
        navigation.route not in settings.FORM_NAVIGATION_ROUTES
        or not navigation.route.startswith("/")
        or navigation.route.startswith("//")
        or any(char in navigation.route for char in ("?", "#", "\\", ":"))
    ):
        return base + "/route", "navigation.host_policy"
    if node["component"] not in {"text", "choice", "user", "group"}:
        return base, "navigation.component"
    from apps.forms.application.validation import _bounded, _compile, _Invalid

    try:
        argument_schema = _compile(navigation.argument_schema)
        result_schema = _compile(navigation.result_schema)
        for contract in (argument_schema, result_schema):
            _bounded(contract, base)
            _compile(contract)
            if contract.get("type") != "object":
                return base, "navigation.schema"
        expected_names = argument_schema.get("properties", {})
        if (
            navigation.arguments.keys() - expected_names.keys()
            or set(argument_schema.get("required", [])) - navigation.arguments.keys()
        ):
            return base + "/arguments", "navigation.argument"
        for name, scope in navigation.arguments.items():
            if "items" in scope_parts(scope) or not ExpressionCompiler.compatible(
                schema_at(schema, scope), expected_names[name]
            ):
                return base + "/arguments", "navigation.argument"
        targets = list(navigation.result_mappings)
        for target_scope, result_scope in navigation.result_mappings.items():
            target = schema_at(schema, target_scope)
            result = schema_at(result_schema, result_scope)
            if "items" in scope_parts(target_scope) or "prefixItems" in scope_parts(target_scope):
                return base + "/result_mappings", "navigation.collection_unsupported"
            if _has_read_only(target) or any(
                target_scope == scope
                or target_scope.startswith(scope + "/")
                or scope.startswith(target_scope + "/")
                for scope in protected
            ):
                return base + "/result_mappings", "navigation.write_protected"
            # A read-only ancestor also protects its entire subtree.
            parts = scope_parts(target_scope)
            for index in range(2, len(parts), 2):
                if schema_at(schema, "/" + "/".join(parts[:index])).get("readOnly"):
                    return base + "/result_mappings", "navigation.write_protected"
            if any(
                other != target_scope
                and (other.startswith(target_scope + "/") or target_scope.startswith(other + "/"))
                for other in targets
            ):
                return base + "/result_mappings", "navigation.overlap"
            if not ExpressionCompiler.compatible(result, target):
                return base + "/result_mappings", "navigation.result_type"
    except ValueError, KeyError, _Invalid:
        return base, "navigation.schema"
    return None


def _has_read_only(schema: dict[str, Any]) -> bool:
    return (
        schema.get("readOnly") is True
        or any(_has_read_only(child) for child in schema.get("properties", {}).values())
        or (isinstance(schema.get("items"), dict) and _has_read_only(schema["items"]))
        or any(_has_read_only(child) for child in schema.get("prefixItems", []))
    )


def _contract(
    documents: FormDocuments, pointer: str, render: dict[str, Any] | None = None
) -> NavigationContract:
    node = next(
        (node for path, node in render_nodes(render or documents.render_schema) if path == pointer),
        None,
    )
    if node is None or not node.get("navigation"):
        raise ValueError("Navigation node not found")
    return NavigationContract.model_validate(node["navigation"])


def navigation_plan(
    documents: FormDocuments,
    pointer: str,
    data: dict[str, Any],
    *,
    render: dict[str, Any] | None = None,
) -> NavigationPlan:
    from apps.forms.application.validation import _bounded, _compile, _Invalid

    try:
        _bounded(data, "/data")
        schema = _compile(documents.data_schema)
    except _Invalid:
        raise ValueError("Invalid navigation data") from None
    navigation = _contract(documents, pointer, render)
    if navigation.route not in settings.FORM_NAVIGATION_ROUTES:
        raise ValueError("Navigation route is no longer approved")
    arguments = {
        name: bound_value(schema, data, scope, []) for name, scope in navigation.arguments.items()
    }
    arguments = {name: value for name, value in arguments.items() if value is not MISSING}
    if not Draft202012Validator(
        navigation.argument_schema, format_checker=FormatChecker()
    ).is_valid(arguments):
        raise ValueError("Invalid navigation arguments")
    return NavigationPlan(
        route=navigation.route,
        arguments=arguments,
        data_revision=digest(data),
        result_schema=navigation.result_schema,
    )


def apply_navigation_result(
    documents: FormDocuments,
    pointer: str,
    data: dict[str, Any],
    result: dict[str, Any] | None,
    expected_data_revision: str,
    *,
    cancelled: bool = False,
    render: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if cancelled:
        return deepcopy(data)
    if digest(data) != expected_data_revision:
        raise ValueError("Navigation result is stale")
    from apps.forms.application.validation import _bounded, _compile, _Invalid

    navigation = _contract(documents, pointer, render)
    from apps.forms.application.validation import FormValidator

    if not FormValidator().validate(documents).valid:
        raise ValueError("Invalid navigation configuration")
    try:
        _bounded(result, "/result")
        schema = _compile(documents.data_schema)
        result_schema = _compile(navigation.result_schema)
    except _Invalid:
        raise ValueError("Invalid navigation result") from None
    if not Draft202012Validator(navigation.result_schema, format_checker=FormatChecker()).is_valid(
        result
    ):
        raise ValueError("Invalid navigation result")
    proposal = deepcopy(data)
    for target_scope, source_scope in navigation.result_mappings.items():
        value = bound_value(result_schema, result, source_scope, [])
        target = schema_at(schema, target_scope)
        if value is MISSING or not Draft202012Validator(
            target, format_checker=FormatChecker()
        ).is_valid(value):
            raise ValueError("Invalid mapped navigation value")
        cursor = proposal
        parts = scope_parts(target_scope)[1::2]
        keys = [part.replace("~1", "/").replace("~0", "~") for part in parts]
        for key in keys[:-1]:
            if key not in cursor:
                cursor[key] = {}
            if not isinstance(cursor[key], dict):
                raise TypeError("Navigation target parent is not an object")
            cursor = cursor[key]
        cursor[keys[-1]] = value
    return proposal
