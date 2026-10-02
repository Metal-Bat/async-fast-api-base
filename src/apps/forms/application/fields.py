"""Localized discovery derived from the primitive definitions and typed options."""

from copy import deepcopy
from typing import Any

from apps.forms.application.bindings import render_nodes
from apps.forms.domain.dto import RenderOptions
from apps.forms.domain.fields import FIELD_DEFINITIONS, FieldContract
from apps.forms.domain.interaction import FieldInteraction
from core.i18n import translate


def field_catalog() -> list[FieldContract]:
    option_schema = RenderOptions.model_json_schema()
    return [
        FieldContract(
            key=definition.kind,
            node_kind=definition.node_kind,
            description=translate(definition.description),
            data_schema={"type": sorted(definition.data_types)} if definition.data_types else {},
            options_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    name: deepcopy(option_schema["properties"][name])
                    for name in sorted(definition.options)
                },
            },
            defaults={"renderer": "default", "options": {}},
            children=definition.children,
        )
        for definition in sorted(FIELD_DEFINITIONS.values(), key=lambda item: item.kind)
    ]


def apply_field_capabilities(
    render: dict[str, Any], capabilities: frozenset[str]
) -> dict[str, Any]:
    """Resolve declared presentation fallback without changing canonical constraints."""
    result = deepcopy(render)
    for _, node in render_nodes(result):
        if node.get("interaction") is None:
            continue
        interaction = FieldInteraction.model_validate(node["interaction"])
        if set(interaction.required_capabilities) <= capabilities:
            continue
        if interaction.fallback_renderer is None:
            raise ValueError("Client lacks required field capabilities")
        node["renderer"] = interaction.fallback_renderer
        node["interaction"] = {
            **node["interaction"],
            "picker": "inline",
            "required_capabilities": [],
        }
        node.pop("navigation", None)
        if node.get("source", {}).get("kind") == "remote":
            source = node["source"]
            node["source"] = {
                "kind": "schema",
                "dependencies": source.get("dependencies", {}),
                "enabled_when": source.get("enabled_when"),
            }
    return result
