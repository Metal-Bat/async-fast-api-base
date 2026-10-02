"""Generate browsable response DTO notes from the application's OpenAPI schema.

Run with ``PYTHONPATH=src uv run python docs/tools/generate_response_dtos.py``.
The repository's synthetic test settings are used; no external service is contacted.
"""

import json
import os
import re
import runpy
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "reference" / "responses"
METHODS = {"get", "post", "put", "patch", "delete"}


def refs(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = {value["$ref"].split("/")[-1]} if "$ref" in value else set()
        for child in value.values():
            found |= refs(child)
        return found
    if isinstance(value, list):
        return set().union(*(refs(child) for child in value)) if value else set()
    return set()


def reviewed_examples(spec: dict) -> dict[str, Any]:
    """Index curated response examples by their actual OpenAPI component names."""
    examples: dict[str, Any] = {}

    def collect(value: Any, schema: dict) -> None:
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            examples.setdefault(name, value)
            schema = spec["components"]["schemas"][name]
        if isinstance(value, dict):
            for key, child in schema.get("properties", {}).items():
                if key in value:
                    collect(value[key], child)
        elif isinstance(value, list):
            for item in value:
                collect(item, schema.get("items", {}))

    fixture = json.loads((ROOT / "docs/examples/frontend-journey.json").read_text())
    for step in fixture["steps"]:
        if step["status"] >= 400:
            continue
        response = spec["paths"][step["path"]][step["method"]]["responses"][str(step["status"])]
        collect(step["response"], response["content"]["application/json"]["schema"])
    return examples


def field_type(schema: dict) -> str:
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if "anyOf" in schema or "oneOf" in schema:
        return " | ".join(field_type(x) for x in schema.get("anyOf", schema.get("oneOf", [])))
    if schema.get("type") == "array":
        return f"array[{field_type(schema.get('items', {}))}]"
    return str(schema.get("type", "object"))


def note(
    name: str, schema: dict, routes: list[str], components: dict, examples: dict | None = None
) -> str:
    lines = [f"### `{name}`", "", f"Used by: {', '.join(f'`{route}`' for route in routes)}", ""]
    description = schema.get("description")
    if description:
        lines += [description.strip(), ""]
    if schema.get("properties"):
        lines += ["| Field | Type | Required | Notes |", "| --- | --- | --- | --- |"]
        for field, spec in schema["properties"].items():
            info = spec.get("description", "")
            if not info and field.endswith("ref_id"):
                info = "Opaque reference; use the value returned by the API."
            if not info and field == "status":
                info = "Lifecycle state; consult the owning resource guide."
            if "default" in spec:
                info += f" Default: `{spec['default']}`."
            info = info.replace("|", "\\|").replace("\n", " ") or "—"
            lines.append(
                f"| `{field}` | `{field_type(spec)}` | {'Yes' if field in schema.get('required', []) else 'No'} | {info} |"
            )
        lines.append("")
    if examples is not None and name in examples:
        lines += [
            (
                "Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). "
                "Replace references and tokens with server-returned values; this is not a captured response."
            ),
            "",
            "```json",
            json.dumps(examples[name], indent=2, ensure_ascii=False),
            "```",
            "",
        ]
    else:
        lines += [
            (
                "No reviewed business example is published for this schema. "
                "Use the field contract above and the [response scenarios](../../api/response-scenarios.md); "
                "do not infer valid lifecycle values from field types alone."
            ),
            "",
        ]
    return "\n".join(lines)


def render_pages(spec: dict) -> dict[str, str]:
    """Render deterministic references without writing files or starting services."""
    examples = reviewed_examples(spec)
    pages: dict[str, str] = {}
    components = spec["components"]["schemas"]
    topics: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if method not in METHODS:
                continue
            topic = operation.get("tags", ["other"])[0]
            route = f"{method.upper()} {path}"
            for status, response in operation["responses"].items():
                if not status.startswith("2"):
                    continue
                pending = list(refs(response))
                visited: set[str] = set()
                while pending:
                    name = pending.pop()
                    if name in visited or name not in components:
                        continue
                    visited.add(name)
                    pending.extend(refs(components[name]) - visited)
                    topics[topic][name].add(route)
    index = [
        "---",
        "tags: [api, dto, index]",
        "---",
        "",
        "# Response DTO reference",
        "",
        "Generated from the application's successful OpenAPI responses. Each topic lists all directly and transitively referenced response schemas, their fields and reviewed examples where available. Unreviewed schemas have no fabricated example. See the [frontend journey](../../guides/frontend-journey.md) and [response scenarios](../../api/response-scenarios.md); live OpenAPI remains the current wire contract.",
        "",
    ]
    for topic, schemas in sorted(topics.items()):
        filename = re.sub(r"[^a-z0-9-]", "-", topic.lower()) + ".md"
        index.append(f"- [{topic}]({filename}) — {len(schemas)} schemas")
        page = [
            "---",
            f"tags: [api, dto, {topic}]",
            "---",
            "",
            f"# {topic} response DTOs",
            "",
            "These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.",
            "",
        ]
        for name in sorted(schemas):
            page.append(note(name, components[name], sorted(schemas[name]), components, examples))
        pages[filename] = "\n".join(page).rstrip() + "\n"
    pages["index.md"] = "\n".join(index).rstrip() + "\n"
    return pages


def main() -> None:
    os.chdir(ROOT)
    runpy.run_path("tests/conftest.py")
    os.environ["LOG_OUTPUTS"] = '["console"]'
    from main import app

    pages = render_pages(app.openapi())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, content in pages.items():
        (OUTPUT / filename).write_text(content)
    print(f"Wrote {len(pages)} reference pages")


if __name__ == "__main__":
    main()
