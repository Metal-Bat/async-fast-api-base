"""Build a bounded display and validation projection without hidden authoring metadata."""

from copy import deepcopy
from typing import Any

from apps.forms.application.validation import _compile
from apps.forms.domain.runtime import RuntimeFieldMetadataDTO
from apps.work_items.application.task_mutations import (
    _covers,
    _related,
    project_task_state,
    visible_scopes,
)
from apps.work_items.application.task_views import _data_path
from apps.workflows.application.validation import GraphValidator


def render_scopes(render: dict[str, Any]) -> set[str]:
    scopes = set()

    def visit(node):
        if isinstance(node, dict):
            if isinstance(node.get("scope"), str) and node["scope"].startswith("/properties/"):
                scopes.add(node["scope"])
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(render)
    return scopes


def display_render(render: dict[str, Any], policy, scopes: set[str] | None) -> dict[str, Any]:
    selected = visible_scopes(policy, scopes)
    hidden = (policy or {}).get("hidden", [])

    def visible(scope):
        path = _data_path(scope)
        return not any(_covers(path, field) for field in hidden) and (
            selected is None or any(_related(path, field) for field in selected)
        )

    def visit(value):
        if isinstance(value, list):
            return [clean for child in value if (clean := visit(child)) is not None]
        if not isinstance(value, dict):
            return deepcopy(value)
        if (
            isinstance(value.get("scope"), str)
            and value["scope"].startswith("/properties/")
            and not visible(value["scope"])
        ):
            return None
        result = {}
        for key, child in value.items():
            # Canonical server evaluation replaces client-side expressions and hidden input dependencies.
            if key in {
                "calculation",
                "conditions",
                "rules",
                "default",
                "default_value",
                "context_bindings",
                "parameters",
                "reuse_instances",
                "localization",
                "source",
                "navigation",
                "messages",
                "option_messages",
            }:
                continue
            clean = visit(child)
            if clean is not None:
                result[key] = clean
        return result

    return visit(render) or {}


def field_metadata(
    schema: dict[str, Any], scopes: set[str], writable: set[str], required: set[str], policy
) -> list[RuntimeFieldMetadataDTO]:
    compiled = _compile(schema)
    hidden = (policy or {}).get("hidden", [])

    def clean(node, path):
        if not isinstance(node, dict):
            return deepcopy(node)
        result = {
            key: deepcopy(value)
            for key, value in node.items()
            if key
            not in {
                "properties",
                "items",
                "prefixItems",
                "required",
                "$defs",
                "title",
                "description",
                "default",
            }
        }
        if any(
            len(_data_path(scope)) > len(path) and _data_path(scope)[: len(path)] == path
            for scope in hidden
        ):
            result.pop("enum", None)
            result.pop("const", None)
        if "properties" in node:
            properties = {
                key: clean(value, (*path, key))
                for key, value in node["properties"].items()
                if not any(_covers((*path, key), scope) for scope in hidden)
            }
            result["properties"] = properties
            if "required" in node:
                result["required"] = [key for key in node["required"] if key in properties]
        if "items" in node:
            result["items"] = clean(node["items"], (*path, "*"))
        if "prefixItems" in node:
            result["prefixItems"] = [clean(value, (*path, "*")) for value in node["prefixItems"]]
        return result

    result = []
    for scope in sorted(scopes):
        path = _data_path(scope)
        if any(_covers(path, field) for field in hidden):
            continue
        field = GraphValidator._schema_at(compiled, scope)
        if field is not None:
            result.append(
                RuntimeFieldMetadataDTO(
                    scope=scope,
                    validation_schema=clean(field, path),
                    writable=any(_covers(path, field) for field in writable),
                    required=scope in required,
                )
            )
    return result


def resolved_render(render, data, writable, permissions):
    """Resolve safe presentation flags on the server without disclosing bindings."""
    from apps.forms.application.behavior import BehaviorError, _matches

    result = deepcopy(render)

    def visit(node):
        if not isinstance(node, dict):
            return
        scope = node.get("scope")
        if scope and "/items" not in scope:
            state = {"visible": True, "enabled": True, "required": False, "overridable": False}
            try:
                for rule in node.get("rules", []):
                    if _matches(rule, data, {}):
                        effect = rule["effect"]
                        if effect in {"show", "hide"}:
                            state["visible"] = effect == "show"
                        elif effect in {"enable", "disable"}:
                            state["enabled"] = effect == "enable"
                        elif effect == "require":
                            state["required"] = True
            except BehaviorError:
                state["visible"] = False
                state["enabled"] = False
            permission = (node.get("calculation") or {}).get("override_permission")
            state["overridable"] = bool(
                scope in writable
                and permission
                and (permission in permissions or "*" in permissions)
            )
            node["runtime_state"] = state
        for child in node.get("children", []):
            visit(child)

    visit(result.get("root"))
    return result


def runtime_projection(
    data,
    identity,
    provenance,
    schema,
    render,
    policy,
    scopes,
    writable,
    required,
    permissions=frozenset(),
):
    state = project_task_state(data, identity, provenance, [], policy, scopes)
    visible = visible_scopes(policy, scopes)
    visible = render_scopes(render) if visible is None else visible
    state["render_schema"] = display_render(
        resolved_render(render, data, writable & visible, permissions), policy, visible
    )
    state["readable_scopes"] = sorted(visible)
    state["writable_scopes"] = sorted(writable & visible)
    state["required_scopes"] = sorted(required & visible)
    state["field_metadata"] = field_metadata(
        schema, visible, writable & visible, required & visible, policy
    )
    return state


def display_page(settings, scopes=None) -> dict[str, Any]:
    result: dict[str, Any] = {
        key: deepcopy(value)
        for key, value in (settings or {}).items()
        if key
        in {"paper", "orientation", "margins", "title", "header", "footer", "width", "height"}
        and isinstance(value, (str, int, float, bool))
    }

    declared = (settings or {}).get("pages")
    if not isinstance(declared, list) or not 1 <= len(declared) <= 32:
        return result
    pages, keys = [], set()
    for page in declared:
        if not isinstance(page, dict):
            return result
        key, title, fields = page.get("key"), page.get("title"), page.get("scopes")
        if (
            not isinstance(key, str)
            or not key
            or len(key) > 64
            or key in keys
            or not isinstance(title, str)
            or len(title) > 256
            or not isinstance(fields, list)
            or len(fields) > 256
        ):
            return result
        fields = [
            scope for scope in fields if isinstance(scope, str) and scope in (scopes or set())
        ]
        keys.add(key)
        if fields:
            pages.append({"key": key, "title": title, "scopes": fields})
    if pages:
        result["pages"] = pages
    return result
