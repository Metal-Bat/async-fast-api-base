"""Bound schema scopes to canonical values without evaluating arbitrary paths."""

from collections.abc import Iterator
from typing import Any

MISSING = object()


def scope_parts(scope: str) -> list[str]:
    if not scope.startswith("/"):
        raise ValueError("Expected schema scope")
    parts = scope[1:].split("/")
    index = 0
    while index < len(parts):
        if parts[index] in {"properties", "prefixItems"} and index + 1 < len(parts):
            index += 2
        elif parts[index] == "items":
            index += 1
        else:
            raise ValueError("Unsupported schema scope")
    return parts


def schema_at(schema: dict[str, Any], scope: str) -> dict[str, Any]:
    node: Any = schema
    try:
        for part in scope_parts(scope):
            key = part.replace("~1", "/").replace("~0", "~")
            node = node[int(key)] if isinstance(node, list) else node[key]
        if not isinstance(node, dict) or "type" not in node:
            raise ValueError("Expected typed schema")
        return node
    except KeyError, IndexError, TypeError:
        raise ValueError("Unknown schema scope") from None


def values_at(schema: dict[str, Any], data: Any, scope: str) -> list[tuple[str, Any, list[int]]]:
    parts = scope_parts(scope)
    candidates: list[tuple[str, Any, list[int]]] = [("/data", data, [])]
    cursor = schema
    index = 0
    while index < len(parts):
        keyword = parts[index]
        if keyword == "properties":
            encoded = parts[index + 1]
            key = encoded.replace("~1", "/").replace("~0", "~")
            cursor = cursor["properties"][key]
            candidates = [
                (path + "/" + encoded, value.get(key, MISSING), rows)
                for path, value, rows in candidates
                if isinstance(value, dict)
            ]
            index += 2
        elif keyword == "prefixItems":
            position = int(parts[index + 1])
            cursor = cursor["prefixItems"][position]
            candidates = [
                (path + f"/{position}", value[position], rows)
                for path, value, rows in candidates
                if isinstance(value, list) and position < len(value)
            ]
            index += 2
        else:
            prefix = len(cursor.get("prefixItems", []))
            cursor = cursor["items"]
            candidates = [
                (path + f"/{i}", item, [*rows, i])
                for path, value, rows in candidates
                if isinstance(value, list)
                for i, item in enumerate(value)
                if i >= prefix
            ]
            index += 1
    return candidates


def bound_value(schema: dict[str, Any], data: Any, scope: str, row_indices: list[int]) -> Any:
    matches = [
        value
        for _, value, rows in values_at(schema, data, scope)
        if rows == row_indices[: len(rows)]
    ]
    return matches[0] if len(matches) == 1 else MISSING


def render_nodes(render: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    stack: list[tuple[str, dict[str, Any]]] = [("/root", render["root"])]
    while stack:
        path, node = stack.pop()
        yield path, node
        stack.extend(
            (path + f"/children/{i}", child) for i, child in enumerate(node.get("children", []))
        )
