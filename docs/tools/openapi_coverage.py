"""Build a source-linked coverage inventory from the generated OpenAPI schema."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRoute

HTTP_METHODS = frozenset({"delete", "get", "patch", "post", "put"})
SCHEMA_PREFIX = "#/components/schemas/"


def _references(value: Any) -> set[str]:
    """Find schema references in an OpenAPI fragment."""
    if isinstance(value, list):
        refs: set[str] = set()
        for item in value:
            refs.update(_references(item))
        return refs
    if not isinstance(value, dict):
        return set()
    refs: set[str] = set()
    reference = value.get("$ref")
    if isinstance(reference, str) and reference.startswith(SCHEMA_PREFIX):
        refs.add(reference.removeprefix(SCHEMA_PREFIX))
    for child in value.values():
        refs.update(_references(child))
    return refs


def _fields(schema: dict[str, Any], *, path: str = "") -> list[dict[str, Any]]:
    """List every inline property, array item and union branch without expanding refs."""
    rows: list[dict[str, Any]] = []
    required = set(schema.get("required", []))
    for name, field in schema.get("properties", {}).items():
        field_path = f"{path}/properties/{name}"
        rows.append(
            {
                "path": field_path,
                "required": name in required,
                "description": field.get("description"),
                "type": field.get("type"),
                "format": field.get("format"),
                "default": field.get("default"),
                "enum": field.get("enum"),
                "ref": field.get("$ref"),
            }
        )
        rows.extend(_fields(field, path=field_path))
    for name in ("items", "additionalProperties"):
        child = schema.get(name)
        if isinstance(child, dict):
            rows.extend(_fields(child, path=f"{path}/{name}"))
    for name in ("allOf", "anyOf", "oneOf", "prefixItems"):
        for index, child in enumerate(schema.get(name, [])):
            if isinstance(child, dict):
                rows.extend(_fields(child, path=f"{path}/{name}/{index}"))
    return rows


def _route_sources(app: FastAPI) -> dict[tuple[str, str], str]:
    """Resolve direct and included routes in FastAPI's current router layout."""
    sources: dict[tuple[str, str], str] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            contexts = [route]
        elif (effective_contexts := getattr(route, "effective_route_contexts", None)) is not None:
            contexts = list(effective_contexts())
        else:
            continue
        for context in contexts:
            for method in context.methods or set():
                endpoint = context.endpoint
                module = getattr(endpoint, "__module__", "unknown")
                name = getattr(endpoint, "__name__", type(endpoint).__name__)
                sources[(context.path, method.lower())] = f"{module}.{name}"
    return sources


def build_inventory(schema: dict[str, Any], app: FastAPI) -> dict[str, Any]:
    """Report coverage of operations and schemas reachable from public paths."""
    sources = _route_sources(app)
    components = schema.get("components", {}).get("schemas", {})
    operations: list[dict[str, Any]] = []
    reachable: set[str] = set()
    by_topic: dict[str, dict[str, int]] = defaultdict(
        lambda: {"operations": 0, "missing_descriptions": 0}
    )
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            topic = operation["tags"][0]
            described = bool(operation.get("description"))
            by_topic[topic]["operations"] += 1
            by_topic[topic]["missing_descriptions"] += not described
            reachable.update(_references(operation))
            operations.append(
                {
                    "topic": topic,
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation["operationId"],
                    "source": sources.get((path, method)),
                    "summary": operation.get("summary"),
                    "description": operation.get("description"),
                    "security": operation.get("security", schema.get("security", [])),
                    "parameters": [
                        {
                            "name": item.get("name"),
                            "in": item.get("in"),
                            "required": item.get("required", False),
                        }
                        for item in operation.get("parameters", [])
                    ],
                    "request_media": sorted(operation.get("requestBody", {}).get("content", {})),
                    "responses": sorted(operation.get("responses", {})),
                    "schema_refs": sorted(_references(operation)),
                }
            )
    pending = list(reachable)
    while pending:
        name = pending.pop()
        for reference in _references(components[name]) - reachable:
            reachable.add(reference)
            pending.append(reference)
    schema_rows = {
        name: {
            "description": components[name].get("description"),
            "fields": _fields(components[name]),
        }
        for name in sorted(reachable)
    }
    topic_order = [tag["name"] for tag in schema.get("tags", [])]
    operations.sort(key=lambda row: (topic_order.index(row["topic"]), row["path"], row["method"]))
    fields = [field for item in schema_rows.values() for field in item["fields"]]
    return {
        "openapi": schema["openapi"],
        "summary": {
            "operations": len(operations),
            "schemas": len(schema_rows),
            "fields": len(fields),
            "missing_operation_descriptions": sum(not item["description"] for item in operations),
            "missing_schema_descriptions": sum(
                not item["description"] for item in schema_rows.values()
            ),
            "missing_field_descriptions": sum(not item["description"] for item in fields),
        },
        "by_topic": {name: by_topic[name] for name in topic_order},
        "operations": operations,
        "schemas": schema_rows,
    }


def write_inventory(schema: dict[str, Any], app: FastAPI, destination: Path) -> None:
    """Write the deterministic, reviewable inventory to a JSON file."""
    destination.write_text(
        json.dumps(build_inventory(schema, app), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
