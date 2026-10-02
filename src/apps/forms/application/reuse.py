"""Compile exact authored component versions into canonical form documents."""

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ConfigDict, Field

from apps.forms.application.bindings import render_nodes, schema_at, scope_parts
from apps.forms.application.localization import source_revision
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.localization import CatalogMessage, FormLocalization
from core.base_dto import BaseDTO


class ResolvedComponent(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    ref_id: str
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_schema: dict[str, Any]
    render_schema: dict[str, Any]
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    parameters_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "additionalProperties": False}
    )
    parameter_targets: dict[str, str] = Field(default_factory=dict)
    messages: dict[str, dict[str, str]] = Field(default_factory=dict)
    localization: dict[str, Any] | None = None
    overridable_messages: list[str] = Field(default_factory=list)


def _child(container: dict[str, Any], pointer: str) -> tuple[Any, Any]:
    if not pointer.startswith("/"):
        raise ValueError("Invalid reuse pointer")
    parts = pointer[1:].split("/")
    node: Any = container
    for part in parts[:-1]:
        key = part.replace("~1", "/").replace("~0", "~")
        node = node[int(key)] if isinstance(node, list) else node[key]
    end = parts[-1].replace("~1", "/").replace("~0", "~")
    if isinstance(node, list):
        position = int(end)
        if position < 0 or position >= len(node):
            raise ValueError("Invalid reuse pointer")
        return node, position
    if isinstance(node, dict):
        return node, end
    raise ValueError("Invalid reuse pointer")


def _apply_parameters(
    render: dict[str, Any], component: ResolvedComponent, values: dict[str, Any]
) -> None:
    if not Draft202012Validator(component.parameters_schema).is_valid(values):
        raise ValueError("Invalid component parameters")
    for name, pointer in component.parameter_targets.items():
        if name not in component.parameters_schema.get("properties", {}):
            raise ValueError("Parameter target is undeclared")
        if not pointer.startswith("/root/") or not (
            pointer.endswith(("/label", "/options/placeholder"))
        ):
            raise ValueError("Parameter target is not customizable")
        if name not in values:
            continue
        parent, key = _child(render, pointer)
        if key not in parent:
            raise ValueError("Parameter target does not exist")
        parent[key] = values[name]


def _merge_messages(
    result: dict[str, Any],
    node: dict[str, Any],
    component: ResolvedComponent,
    instance: dict[str, Any],
) -> None:
    declared: dict[str, dict[str, Any]] = deepcopy(component.messages)
    if component.localization:
        for locale, entries in component.localization.get("catalogs", {}).items():
            destination = declared.setdefault(locale, {})
            if set(destination) & set(entries):
                raise ValueError("Nested message key conflicts with component key")
            destination.update(entries)
    overrides = instance.get("message_overrides", {})
    if any(
        name not in component.overridable_messages
        for messages in overrides.values()
        for name in messages
    ):
        raise ValueError("Message override is not declared")
    if set(overrides) - set(declared):
        raise ValueError("Message override locale is undeclared")
    if not declared:
        if overrides:
            raise ValueError("Component has no overridable messages")
        return
    if "en" not in declared:
        raise ValueError("Component needs an English source catalog")
    catalog: dict[str, Any] = deepcopy(result.get("localization")) or {
        "dialect": "bpms.messages/1",
        "default_locale": "en",
        "supported_locales": sorted(declared),
        "required_locales": sorted(declared),
        "catalogs": {},
    }
    catalog["supported_locales"] = sorted(set(catalog["supported_locales"]) | set(declared))
    catalog["required_locales"] = sorted(set(catalog["required_locales"]) | set(declared))
    prefix = f"component.{instance['instance_key']}."
    for locale, entries in declared.items():
        destination = catalog.setdefault("catalogs", {}).setdefault(locale, {})
        for key, text in entries.items():
            replacement = overrides.get(locale, {}).get(key, text)
            message = CatalogMessage.model_validate(
                replacement if isinstance(replacement, dict) else {"text": replacement}
            )
            if locale != catalog["default_locale"]:
                original = overrides.get(catalog["default_locale"], {}).get(
                    key, declared[catalog["default_locale"]][key]
                )
                source = CatalogMessage.model_validate(
                    original if isinstance(original, dict) else {"text": original}
                )
                message.source_revision = source_revision(source)
            namespaced = prefix + key
            if namespaced in destination:
                raise ValueError("Duplicate component message key")
            destination[namespaced] = message.model_dump()
    for _, child in render_nodes({"root": node}):
        for ref in child.get("messages", {}).values():
            ref["key"] = prefix + ref["key"]
        if child.get("localization_key"):
            child["localization_key"] = prefix + child["localization_key"]
        for item in child.get("option_messages", []):
            item["message"]["key"] = prefix + item["message"]["key"]
        for item in child.get("source", {}).get("items", []):
            if item.get("message"):
                item["message"]["key"] = prefix + item["message"]["key"]
    result["localization"] = FormLocalization.model_validate(catalog).model_dump()


def _prefix_node(node: dict[str, Any], schema_pointer: str, instance_key: str) -> None:
    for _, child in render_nodes({"root": node}):
        key = child.get("node_key")
        if key:
            child["node_key"] = f"{instance_key}.{key}"
        if child.get("scope"):
            child["scope"] = schema_pointer + child["scope"]
        for rule in child.get("rules", []):
            rule["scope"] = schema_pointer + rule["scope"]
        calculation = child.get("calculation")
        if calculation:
            calculation["scopes"] = [
                schema_pointer + scope for scope in calculation.get("scopes", [])
            ]
        source = child.get("source")
        if source:
            source["dependencies"] = {
                name: schema_pointer + scope
                for name, scope in source.get("dependencies", {}).items()
            }
        navigation = child.get("navigation")
        if navigation:
            navigation["arguments"] = {
                name: schema_pointer + scope
                for name, scope in navigation.get("arguments", {}).items()
            }
            navigation["result_mappings"] = {
                schema_pointer + scope: result
                for scope, result in navigation.get("result_mappings", {}).items()
            }


def compile_instances(
    documents: FormDocuments,
    instances: list[dict[str, Any]],
    components: dict[str, ResolvedComponent],
) -> tuple[FormDocuments, list[dict[str, Any]]]:
    """Replace only declared placeholders; return a new pinned document and manifest."""
    if len(instances) > 100:
        raise ValueError("Too many component instances")
    result = deepcopy(documents.model_dump())
    seen_keys: set[str] = set()
    seen_schema: set[str] = set()
    seen_nodes: set[str] = set()
    manifest: dict[str, dict[str, Any]] = {}
    for instance in instances:
        key = instance["instance_key"]
        schema_pointer = instance["schema_pointer"]
        node_pointer = instance["node_pointer"]
        ref = instance["component_ref"]
        if (
            not key
            or len(key) > 64
            or key in seen_keys
            or schema_pointer in seen_schema
            or node_pointer in seen_nodes
        ):
            raise ValueError("Ambiguous component instance")
        if len(scope_parts(schema_pointer)) > 16:
            raise ValueError("Unsupported component binding")
        component = components.get(ref)
        if component is None:
            raise ValueError("Component version is unavailable")
        target = schema_at(result["data_schema"], schema_pointer)
        if target.get("type") != "object":
            raise ValueError("Component binding requires an object")
        if component.data_schema.get("type") != "object":
            raise ValueError("Component data root must be an object")
        schema_parent, schema_key = _child(result["data_schema"], schema_pointer)
        render_parent, render_key = _child(result["render_schema"], node_pointer)
        if render_parent[render_key] != {"component": "vertical"}:
            raise ValueError("Component node must be an empty vertical placeholder")
        schema_parent[schema_key] = deepcopy(component.data_schema)
        rendered_document = deepcopy(component.render_schema)
        _apply_parameters(rendered_document, component, instance.get("parameters", {}))
        rendered = rendered_document["root"]
        _prefix_node(rendered, schema_pointer, key)
        _merge_messages(result, rendered, component, instance)
        render_parent[render_key] = rendered
        seen_keys.add(key)
        seen_schema.add(schema_pointer)
        seen_nodes.add(node_pointer)
        manifest[ref] = {"ref_id": ref, "checksum": component.checksum}
        for dependency in component.dependencies:
            manifest[dependency["ref_id"]] = dependency
    return FormDocuments.model_validate(result), [manifest[ref] for ref in sorted(manifest)]
