"""Bounded JSON Schema profile and renderer-neutral form validation."""

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from pydantic import ValidationError

from apps.expressions.application.language import ExpressionCompiler, ExpressionError
from apps.forms.application.designs import DesignVariant, validate_variants
from apps.forms.application.option_validation import (
    static_membership_issues,
    validate_source,
    validate_source_graph,
)
from apps.forms.domain.dto import (
    DATA_DIALECT,
    RENDER_DIALECT,
    FormDocuments,
    RenderDocument,
    RenderNode,
    ValidationIssue,
    ValidationResult,
)
from apps.forms.domain.fields import FIELD_DEFINITIONS
from core.ref_id import open_ref_id

_KEYWORDS = frozenset(
    {
        "$schema",
        "$defs",
        "$ref",
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "prefixItems",
        "enum",
        "const",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minProperties",
        "maxProperties",
        "format",
        "title",
        "description",
        "default",
        "readOnly",
        "writeOnly",
        "deprecated",
    }
)
_LAYOUTS = {key for key, spec in FIELD_DEFINITIONS.items() if spec.node_kind == "layout"}
_TYPES = {key: spec.data_types for key, spec in FIELD_DEFINITIONS.items() if spec.data_types}
_OPTIONS = {key: spec.options for key, spec in FIELD_DEFINITIONS.items()}
_UNSET = object()


def pointer(parts: Any) -> str:
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


class _Invalid(Exception):
    def __init__(self, path: str, code: str) -> None:
        self.issue = ValidationIssue(pointer=path, code=code)


def _bounded(value: Any, path: str) -> int:
    count = 0
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        count += 1
        if depth > 24 or count > 2048:
            raise _Invalid(path, "document.limit")
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            if len(item) > 256:
                raise _Invalid(path, "document.limit")
            stack.extend((v, depth + 1) for v in item)
    try:
        size = len(json.dumps(value, allow_nan=False).encode())
    except ValueError, TypeError, RecursionError:
        raise _Invalid(path, "document.invalid") from None
    if size > 65536:
        raise _Invalid(path, "document.limit")
    return count


def _resolve(root: dict[str, Any], scope: str) -> Any:
    if not scope.startswith("/"):
        raise KeyError(scope)
    node: Any = root
    for segment in scope[1:].split("/"):
        key = segment.replace("~1", "/").replace("~0", "~")
        node = node[int(key)] if isinstance(node, list) else node[key]
    return node


def _compile(root: dict[str, Any]) -> dict[str, Any]:
    work = 0

    def visit(node: Any, path: str, refs: tuple[str, ...] = ()) -> Any:
        nonlocal work
        work += 1
        if work > 2048:
            raise _Invalid(path, "schema.limit")
        if isinstance(node, bool):
            return node
        if not isinstance(node, dict):
            raise _Invalid(path, "schema.invalid")
        for key in node.keys() - _KEYWORDS:
            raise _Invalid(path + pointer([key]), "schema.unsupported_keyword")
        if "$schema" in node and node["$schema"] != DATA_DIALECT:
            raise _Invalid(path + "/$schema", "schema.dialect")
        if "format" in node and node["format"] not in {"date", "date-time", "email", "uuid"}:
            raise _Invalid(path + "/format", "schema.format")
        if "$ref" in node:
            ref = node["$ref"]
            if (
                not isinstance(ref, str)
                or not ref.startswith("#/$defs/")
                or ref in refs
                or len(refs) > 16
            ):
                raise _Invalid(path + "/$ref", "schema.reference")
            if node.keys() - {"$ref", "$defs", "$schema", "title", "description"}:
                raise _Invalid(path + "/$ref", "schema.reference_siblings")
            try:
                target = _resolve(root, ref[1:])
            except KeyError, IndexError, ValueError, TypeError:
                raise _Invalid(path + "/$ref", "schema.reference") from None
            return visit(target, path, (*refs, ref))
        result = node.copy()
        result.pop("$defs", None)
        for keyword in ("properties", "$defs"):
            for key, child in node.get(keyword, {}).items():
                compiled = visit(child, path + pointer([keyword, key]), refs)
                if keyword == "properties":
                    result.setdefault("properties", {})
                    result["properties"] = {**result["properties"], key: compiled}
        for keyword in ("items", "additionalProperties"):
            if keyword in node:
                result[keyword] = visit(node[keyword], path + "/" + keyword, refs)
        if "prefixItems" in node:
            result["prefixItems"] = [
                visit(child, path + pointer(["prefixItems", i]), refs)
                for i, child in enumerate(node["prefixItems"])
            ]
        return result

    # Meta-schema validation is performed only after the size/depth boundary.
    try:
        Draft202012Validator.check_schema(root)
    except SchemaError as exc:
        raise _Invalid("/data_schema" + pointer(exc.absolute_path), "schema.invalid") from None
    result = visit(root, "/data_schema")
    _bounded(result, "/data_schema")
    return result


class FormValidator:
    def validate(
        self,
        documents: FormDocuments,
        data: Any = _UNSET,
        *,
        publication: bool = False,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> ValidationResult:
        try:
            schema_nodes = _bounded(documents.data_schema, "/data_schema")
            render_nodes = _bounded(documents.render_schema, "/render_schema")
            if documents.data_dialect != DATA_DIALECT:
                raise _Invalid("/data_dialect", "schema.dialect")
            if documents.render_dialect != RENDER_DIALECT:
                raise _Invalid("/render_dialect", "render.dialect")
            schema = _compile(documents.data_schema)
            if render_nodes * _bounded(schema, "/data_schema") > 100000:
                raise _Invalid("/render_schema", "validation.limit")
            if schema.get("type") != "object":
                raise _Invalid("/data_schema/type", "schema.root_object")
            try:
                render = RenderDocument.model_validate(documents.render_schema)
            except ValidationError as exc:
                return ValidationResult(
                    valid=False,
                    issues=[
                        ValidationIssue(
                            pointer="/render_schema" + pointer(error["loc"]), code="render.invalid"
                        )
                        for error in exc.errors(include_input=False)[:32]
                    ],
                )
            self._node(render.root, schema, render.outcomes, "/render_schema/root")
            if documents.behavior_dialect is not None:
                from apps.forms.application.behavior import BehaviorError, validate_behavior

                try:
                    validate_behavior(documents)
                except BehaviorError as exc:
                    raise _Invalid("/render_schema", str(exc)) from None
            evaluated_data = None
            if data is not _UNSET and documents.behavior_dialect is not None:
                _bounded(data, "/data")
                from apps.forms.application.behavior import BehaviorError, evaluate_behavior

                if not isinstance(data, dict):
                    raise _Invalid("/data", "behavior.data_object")
                try:
                    evaluated_data = evaluate_behavior(
                        documents, data, authoritative=True, overrides=overrides
                    ).data
                except BehaviorError as exc:
                    raise _Invalid("/data", str(exc)) from None
                data = evaluated_data
            if data is not _UNSET:
                nodes = _bounded(data, "/data")
                if nodes * max(schema_nodes, _bounded(schema, "/data_schema")) > 100000:
                    raise _Invalid("/data", "validation.limit")
                issues = []
                for error in Draft202012Validator(
                    schema, format_checker=FormatChecker()
                ).iter_errors(data):
                    issues.append(
                        ValidationIssue(
                            pointer="/data"
                            + (pointer(error.absolute_path) if error.absolute_path else ""),
                            code="data." + str(error.validator),
                        )
                    )
                    if len(issues) == 32:
                        break
                if issues:
                    return ValidationResult(valid=False, issues=issues)
            _bounded(documents.page_settings, "/page_settings")
            _bounded([item.model_dump(mode="json") for item in documents.variants], "/variants")
            targets = []
            for index, item in enumerate(documents.variants):
                target_id = None
                if item.client_ref_id is not None:
                    try:
                        target_id, _ = open_ref_id(item.client_ref_id)
                    except ValueError, TypeError:
                        raise _Invalid(
                            f"/variants/{index}/client_ref_id", "variant.client"
                        ) from None
                try:
                    target = DesignVariant(
                        key=item.key,
                        priority=item.priority,
                        client_id=target_id,
                        kind=item.kind,
                        minimum_release=item.minimum_release,
                        maximum_release_exclusive=item.maximum_release_exclusive,
                        required_capabilities=frozenset(item.required_capabilities),
                        render_schema=item.render_schema,
                        page_settings=item.page_settings,
                        condition=item.condition,
                    )
                except ExpressionError as exc:
                    return ValidationResult(
                        valid=False,
                        issues=[
                            ValidationIssue(
                                pointer=f"/variants/{index}/condition",
                                code=exc.code,
                                line=exc.line,
                                column=exc.column,
                            )
                        ],
                    )
                except ValueError:
                    raise _Invalid(f"/variants/{index}", "variant.invalid") from None
                targets.append(target)
                variant_document = FormDocuments(
                    data_dialect=documents.data_dialect,
                    render_dialect=documents.render_dialect,
                    data_schema=documents.data_schema,
                    render_schema=item.render_schema,
                    behavior_dialect=documents.behavior_dialect,
                    localization=documents.localization,
                )
                variant_result = self.validate(variant_document)
                if not variant_result.valid:
                    raise _Invalid(f"/variants/{index}/render_schema", "variant.render")
            try:
                validate_variants(targets)
            except ValueError:
                raise _Invalid("/variants", "variant.overlap") from None
            from apps.forms.application.bindings import render_nodes
            from apps.forms.application.navigation import validate_navigation

            renders = [
                documents.render_schema,
                *(item.render_schema for item in documents.variants),
            ]
            protected = {
                node["scope"]
                for raw in renders
                for _, node in render_nodes(raw)
                if node.get("scope")
                and (node.get("options", {}).get("read_only") or node.get("calculation"))
            }
            for raw in renders:
                for node_path, raw_node in render_nodes(raw):
                    if raw_node.get("navigation"):
                        issue = validate_navigation(
                            raw_node, schema, "/render_schema" + node_path, protected
                        )
                        if issue:
                            raise _Invalid(*issue)
            source_graph_issue = validate_source_graph(
                [documents.render_schema, *(item.render_schema for item in documents.variants)]
            )
            if source_graph_issue:
                raise _Invalid(*source_graph_issue)
            if data is not _UNSET:
                for raw in [
                    documents.render_schema,
                    *(item.render_schema for item in documents.variants),
                ]:
                    membership_issues = static_membership_issues(raw, schema, data)
                    if membership_issues:
                        return ValidationResult(
                            valid=False,
                            issues=[
                                ValidationIssue(pointer=path, code=code)
                                for path, code in membership_issues
                            ],
                        )
                from apps.forms.application.formatting import canonical_value_issues

                for raw in [
                    documents.render_schema,
                    *(item.render_schema for item in documents.variants),
                ]:
                    format_issues = canonical_value_issues(raw, data, schema)
                    if format_issues:
                        return ValidationResult(
                            valid=False,
                            issues=[
                                ValidationIssue(pointer=path, code=code)
                                for path, code in format_issues
                            ],
                        )
            from apps.forms.application.localization import validate_localization

            errors, gaps, revisions = validate_localization(documents)
            if publication and documents.localization:
                required = set(documents.localization.required_locales)
                errors.extend(issue for issue in gaps if issue.pointer.split("/")[3] in required)
            if errors:
                return ValidationResult(
                    valid=False, issues=errors[:32], warnings=gaps[:32], source_revisions=revisions
                )
            checksum_document = documents.model_dump()
            if documents.localization is None:
                checksum_document.pop("localization")
            if documents.reuse_instances is None:
                checksum_document.pop("reuse_instances")
            if documents.behavior_dialect is None:
                checksum_document.pop("behavior_dialect")
            for variant in checksum_document["variants"]:
                if variant.get("condition") is None:
                    variant.pop("condition", None)
            if not documents.page_settings and not documents.variants:
                checksum_document.pop("page_settings")
                checksum_document.pop("variants")
            checksum = hashlib.sha256(
                json.dumps(
                    checksum_document, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ).hexdigest()
            return ValidationResult(
                valid=True,
                checksum=checksum,
                warnings=gaps[:32],
                source_revisions=revisions,
                evaluated_data=evaluated_data,
            )
        except _Invalid as exc:
            return ValidationResult(valid=False, issues=[exc.issue])

    def _scope(self, schema: dict[str, Any], scope: str | None, path: str) -> dict[str, Any]:
        try:
            parts = (scope or "").split("/")[1:]
            cursor = 0
            while cursor < len(parts):
                keyword = parts[cursor]
                if keyword in {"properties", "prefixItems"} and cursor + 1 < len(parts):
                    cursor += 2
                elif keyword == "items":
                    cursor += 1
                else:
                    raise KeyError(scope)
            target = _resolve(schema, scope or "")
            if not isinstance(target, dict) or "type" not in target:
                raise KeyError(scope)
            return target
        except KeyError, IndexError, TypeError, ValueError:
            raise _Invalid(path, "render.scope") from None

    def _node(
        self, node: RenderNode, schema: dict[str, Any], outcomes: list[str], path: str
    ) -> None:
        if node.component in _TYPES:
            target = self._scope(schema, node.scope, path + "/scope")
            types = target["type"] if isinstance(target["type"], list) else [target["type"]]
            if not set(types) - {"null"} or not set(types) - {"null"} <= _TYPES[node.component]:
                raise _Invalid(path + "/scope", "render.type")
            if (
                node.component in {"date", "datetime"}
                and target.get("format")
                != {"date": "date", "datetime": "date-time"}[node.component]
            ):
                raise _Invalid(path + "/scope", "render.format")
            if (
                node.component == "choice"
                and "enum" not in target
                and node.selector is None
                and node.source is None
            ):
                raise _Invalid(path + "/scope", "render.choices")
            if node.component == "attachment_collection" and (
                not isinstance(target.get("items"), dict) or target["items"].get("type") != "string"
            ):
                raise _Invalid(path + "/scope", "render.attachment_items")
            if node.option_messages:
                values = [option.value for option in node.option_messages]
                if (
                    node.component != "choice"
                    or any(
                        not any(
                            type(value) is type(option) and value == option
                            for option in target.get("enum", [])
                        )
                        for value in values
                    )
                    or len({(type(value), value) for value in values}) != len(values)
                ):
                    raise _Invalid(path + "/option_messages", "localization.option")
            if node.formatting and node.formatting.kind != "text":
                if set(types) - {"null"} != {"string"}:
                    raise _Invalid(path + "/formatting", "localization.format_type")
                expected = {"date": "date", "datetime": "date-time"}.get(node.formatting.kind)
                if expected is not None and target.get("format") != expected:
                    raise _Invalid(path + "/formatting", "localization.format_type")
        elif node.scope is not None:
            raise _Invalid(path + "/scope", "render.unexpected_scope")
        if node.option_messages and node.component != "choice":
            raise _Invalid(path + "/option_messages", "localization.option")
        if node.children and not FIELD_DEFINITIONS[node.component].children:
            raise _Invalid(path + "/children", "render.children")
        if node.selector is not None and (
            node.component not in {"user", "group", "choice"}
            or node.component == "user"
            and node.selector != "users"
            or node.component == "group"
            and node.selector != "work_groups"
        ):
            raise _Invalid(path + "/selector", "render.selector")
        allowed = _OPTIONS.get(node.component, {"read_only"} if node.component in _TYPES else set())
        for key in node.options.model_fields_set - allowed:
            raise _Invalid(path + "/options/" + key, "render.option")
        if (
            node.options.min_items is not None
            and node.options.max_items is not None
            and node.options.min_items > node.options.max_items
        ):
            raise _Invalid(path + "/options/max_items", "render.option")
        if node.grid and node.grid.column + node.grid.span > 13:
            raise _Invalid(path + "/grid/span", "render.grid")
        if (
            node.component == "action"
            and node.outcome not in outcomes
            or node.component != "action"
            and node.outcome is not None
        ):
            raise _Invalid(path + "/outcome", "render.outcome")
        if node.component == "calculated" and node.calculation is None:
            raise _Invalid(path + "/calculation", "render.calculation")
        if node.calculation:
            if node.component != "calculated":
                raise _Invalid(path + "/calculation", "render.calculation")
            target = self._scope(schema, node.scope, path + "/scope")
            if bool(node.calculation.expression):
                empty = {"type": "object", "properties": {}, "additionalProperties": False}
                try:
                    ExpressionCompiler().compile(
                        node.calculation.expression,
                        {
                            "request": schema,
                            "process": empty,
                            "current_user": empty,
                            "steps": empty,
                        },
                        expected_schema=target,
                    )
                except ExpressionError as exc:
                    raise _Invalid(path + "/calculation/expression", exc.code) from None
            function = node.calculation.function
            for i, scope in enumerate(node.calculation.scopes):
                if function is None:
                    raise _Invalid(path + "/calculation/function", "render.calculation")
                source = self._scope(schema, scope, path + pointer(["calculation", "scopes", i]))
                accepted = {
                    "sum": {"integer", "number"},
                    "concat": {"string"},
                    "count": {"array"},
                }[function]
                source_types = (
                    source["type"] if isinstance(source["type"], list) else [source["type"]]
                )
                if not set(source_types) <= accepted:
                    raise _Invalid(
                        path + pointer(["calculation", "scopes", i]), "render.calculation_type"
                    )
                expected = {
                    "sum": {"integer", "number"},
                    "concat": {"string"},
                    "count": {"integer", "number"},
                }[function]
                target_types = set(
                    target["type"] if isinstance(target["type"], list) else [target["type"]]
                ) - {"null"}
                if not target_types <= expected or (
                    function == "sum" and "number" in source_types and target_types == {"integer"}
                ):
                    raise _Invalid(path + "/scope", "render.calculation_type")
        for i, rule in enumerate(node.rules):
            condition = self._scope(schema, rule.scope, path + pointer(["rules", i, "scope"]))
            if rule.operator != "present" and not Draft202012Validator(
                condition, format_checker=FormatChecker()
            ).is_valid(rule.value):
                raise _Invalid(path + pointer(["rules", i, "value"]), "render.rule_value")
        if node.interaction is not None:
            interaction = node.interaction
            if interaction.input_mode is not None and node.component not in {
                "text",
                "textarea",
                "integer",
                "number",
            }:
                raise _Invalid(path + "/interaction/input_mode", "interaction.component")
            if interaction.picker != "inline" and node.component not in {
                "choice",
                "date",
                "datetime",
                "user",
                "group",
                "media",
                "text",
            }:
                raise _Invalid(path + "/interaction/picker", "interaction.component")
        if node.source is not None:
            if node.component not in {"choice", "user", "group"}:
                raise _Invalid(path + "/source", "source.component")
            issue = validate_source(node.model_dump(mode="json", exclude_none=True), schema, path)
            if issue:
                raise _Invalid(*issue)
        for i, child in enumerate(node.children):
            self._node(child, schema, outcomes, path + pointer(["children", i]))
