"""Bounded, renderer-neutral validation for workflow publication snapshots."""

import hashlib
import json
from collections import defaultdict, deque
from typing import Any

from apps.clients.domain.contracts import client_expression_schema
from apps.expressions.application.language import (
    ExpressionCompiler,
    ExpressionError,
    uses_client_context,
)
from apps.expressions.application.transforms import TransformSpec, transform_schemas
from apps.workflows.domain.dto import GraphIssue, GraphSnapshot, GraphValidationResult
from core.ref_id import open_ref_id
from utils.exceptions import InvalidReferenceException


class GraphValidator:
    def __init__(self, compiler: ExpressionCompiler | None = None) -> None:
        self.compiler = compiler or ExpressionCompiler()

    def validate(
        self,
        graph: GraphSnapshot,
        *,
        step_output_schemas: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> GraphValidationResult:
        issues: list[GraphIssue] = []

        def add(pointer: str, code: str, **details: Any) -> None:
            if len(issues) < 64:
                issues.append(GraphIssue(pointer=pointer, code=code, **details))

        positions: dict[str, int] = {}
        types: dict[str, str] = {}
        steps_by_key = {step.key: step for step in graph.steps}
        transforms: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for index, step in enumerate(graph.steps):
            if step.key in positions:
                add(f"/steps/{index}/key", "graph.step.duplicate")
            positions[step.key] = index
            types[step.key] = step.type_code
            if step.type_code == "HUMAN_TASK" and not step.form_ref:
                add(f"/steps/{index}/form_ref", "human.form.required")
            if step.type_code == "HUMAN_TASK" and step.field_policy is None:
                add(f"/steps/{index}/field_policy", "human.field_policy.required")
            if step.type_code != "HUMAN_TASK" and (step.form_ref or step.field_policy):
                add(f"/steps/{index}/form_ref", "graph.form.not_allowed")
            if step.flow.compensation_only and step.type_code not in {"SERVICE_TASK", "TRANSFORM"}:
                add(f"/steps/{index}/flow/compensation_only", "graph.compensation.type.invalid")
            if step.flow.compensation_step == step.key:
                add(f"/steps/{index}/flow/compensation_step", "graph.compensation.self")
            if step.type_code == "TRANSFORM":
                try:
                    spec = TransformSpec(
                        conversion=step.config["conversion_key"],
                        null_behavior=step.config.get("null_behavior", "error"),
                        default=step.config.get("default"),
                        format=step.config.get("format"),
                        projection=step.config.get("projection"),
                    )
                    transforms[step.key] = transform_schemas(spec)
                except KeyError, TypeError, ValueError:
                    add(f"/steps/{index}/config", "transform.config.invalid")
        if list(types.values()).count("START") != 1:
            add("/steps", "graph.start.count")
        if list(types.values()).count("FINISH") < 1:
            add("/steps", "graph.finish.required")

        targets_by_step: set[str] = set()
        for index, target in enumerate(graph.targets):
            if target.step not in types:
                add(f"/targets/{index}/step", "graph.step.unknown")
            else:
                targets_by_step.add(target.step)
                if types[target.step] != "HUMAN_TASK":
                    add(f"/targets/{index}/step", "human.target.not_allowed")
        for key, kind in types.items():
            if (
                kind == "HUMAN_TASK"
                and key not in targets_by_step
                and not (
                    graph.interface and any(port.assignment for port in graph.interface.inputs)
                )
            ):
                add(f"/steps/{positions[key]}", "human.target.required")

        adjacency: dict[str, set[str]] = defaultdict(set)
        defaults: set[tuple[str, str]] = set()
        choices: set[tuple[str, str, int]] = set()
        for index, edge in enumerate(graph.transitions):
            for field, key in (("source", edge.source), ("target", edge.target)):
                if key not in types:
                    add(f"/transitions/{index}/{field}", "graph.step.unknown")
            if edge.source == edge.target:
                add(f"/transitions/{index}/target", "graph.self_loop.unsupported")
            choice = (edge.source, edge.outcome, edge.priority)
            if choice in choices:
                add(f"/transitions/{index}/priority", "transition.choice.duplicate")
            choices.add(choice)
            default = (edge.source, edge.outcome)
            if edge.is_default and default in defaults:
                add(f"/transitions/{index}/is_default", "transition.default.duplicate")
            if edge.is_default:
                defaults.add(default)
            if edge.source in types and edge.target in types:
                adjacency[edge.source].add(edge.target)

        # The new client-aware profile requires a final unconditional else.
        # Legacy published graphs retain their existing conditional-default behavior.
        client_groups = {
            (edge.source, edge.outcome)
            for edge in graph.transitions
            if uses_client_context(edge.condition)
        }
        for index, edge in enumerate(graph.transitions):
            if not edge.is_default or (edge.source, edge.outcome) not in client_groups:
                continue
            if edge.condition is not None:
                add(f"/transitions/{index}/condition", "transition.default.condition")
            if any(
                other.source == edge.source
                and other.outcome == edge.outcome
                and not other.is_default
                and other.priority <= edge.priority
                for other in graph.transitions
            ):
                add(f"/transitions/{index}/priority", "transition.default.order")

        start = next((key for key, value in types.items() if value == "START"), None)
        reachable: set[str] = set()
        if start:
            queue = deque([start])
            while queue:
                current = queue.popleft()
                if current in reachable:
                    continue
                reachable.add(current)
                queue.extend(adjacency[current] - reachable)
            for key in types.keys() - reachable:
                if not steps_by_key[key].flow.compensation_only:
                    add(f"/steps/{positions[key]}", "graph.step.unreachable")

        predecessors: dict[str, set[str]] = defaultdict(set)
        for source, targets in adjacency.items():
            for target in targets:
                predecessors[target].add(source)
        dominators = {key: set(types) for key in types}
        if start:
            dominators[start] = {start}
            changed = True
            while changed:
                changed = False
                for key in types.keys() - {start}:
                    incoming = predecessors[key]
                    value = {key} | (
                        set.intersection(*(dominators[item] for item in incoming))
                        if incoming
                        else set()
                    )
                    if value != dominators[key]:
                        dominators[key] = value
                        changed = True

        referenced_compensations: set[str] = set()
        for index, step in enumerate(graph.steps):
            flow = step.flow
            outgoing = adjacency[step.key]
            incoming = predecessors[step.key]
            if flow.split == "ALL" and len(outgoing) < 2:
                add(f"/steps/{index}/flow/split", "graph.split.branches.required")
            if flow.split == "ALL" and len(outgoing) >= 2:
                joins = {
                    candidate.key
                    for candidate in graph.steps
                    if candidate.flow.join == "ALL"
                    and all(
                        self._can_reach(branch, candidate.key, adjacency) for branch in outgoing
                    )
                }
                if not joins:
                    add(f"/steps/{index}/flow/split", "graph.split.join_missing")
            if flow.join == "ALL":
                split_dominators = [
                    key
                    for key in dominators.get(step.key, set()) - {step.key}
                    if steps_by_key[key].flow.split == "ALL"
                ]
                if len(incoming) < 2 or not split_dominators:
                    add(f"/steps/{index}/flow/join", "graph.join.scope.invalid")
            if flow.compensation_step:
                target = steps_by_key.get(flow.compensation_step)
                if target is None:
                    add(
                        f"/steps/{index}/flow/compensation_step",
                        "graph.compensation.unknown",
                    )
                elif not target.flow.compensation_only:
                    add(
                        f"/steps/{index}/flow/compensation_step",
                        "graph.compensation.target.invalid",
                    )
                else:
                    referenced_compensations.add(target.key)
        for index, step in enumerate(graph.steps):
            if step.flow.compensation_only:
                if step.key in reachable:
                    add(f"/steps/{index}/flow/compensation_only", "graph.compensation.reachable")
                if step.key not in referenced_compensations:
                    add(f"/steps/{index}/flow/compensation_only", "graph.compensation.unreferenced")

        for component in self._cyclic_components(set(types), adjacency):
            if not any(steps_by_key[key].flow.max_visits is not None for key in component):
                for key in sorted(component):
                    add(f"/steps/{positions[key]}/flow/max_visits", "graph.loop.unbounded")

        for index, binding in enumerate(graph.bindings):
            if binding.step not in types:
                add(f"/bindings/{index}/step", "graph.step.unknown")
            if binding.source_kind == "STEP_OUTPUT":
                if binding.source_step not in types:
                    add(f"/bindings/{index}/source_step", "graph.step.unknown")
                elif (
                    binding.step in dominators
                    and binding.source_step not in dominators[binding.step]
                ):
                    add(f"/bindings/{index}/source_step", "binding.source.not_prior")
            source_schema = binding.source_schema
            if source_schema and binding.source_path:
                source_schema = self._schema_at(source_schema, binding.source_path)
                if source_schema is None:
                    add(f"/bindings/{index}/source_path", "binding.path.unknown")
            target_schema = binding.target_schema
            if binding.step in transforms and binding.target_port == "value":
                expected_input = transforms[binding.step][0]
                if not self._compatible(target_schema, expected_input):
                    add(
                        f"/bindings/{index}/target_schema",
                        "transform.input_schema.mismatch",
                        expected_schema=expected_input,
                        actual_schema=target_schema,
                    )
                target_schema = expected_input
            if (
                binding.source_step in transforms
                and binding.source_port == "result"
                and source_schema
                and not self._compatible(source_schema, transforms[binding.source_step][1])
            ):
                add(
                    f"/bindings/{index}/source_schema",
                    "transform.output_schema.mismatch",
                    expected_schema=transforms[binding.source_step][1],
                    actual_schema=source_schema,
                )
            if source_schema and not self._assignable(source_schema, target_schema):
                add(
                    f"/bindings/{index}/source_schema",
                    "binding.type.incompatible",
                    expected_schema=target_schema,
                    actual_schema=source_schema,
                )
            if binding.source_path and not binding.source_path.startswith("/"):
                add(f"/bindings/{index}/source_path", "binding.path.invalid")

        for index, target in enumerate(graph.targets):
            if target.condition and target.step in dominators:
                self._compile_expression(
                    target.condition,
                    f"/targets/{index}/condition",
                    self._context_schemas(
                        graph, dominators[target.step] - {target.step}, step_output_schemas
                    ),
                    add,
                    expected_schema={"type": "boolean"},
                )
        for index, edge in enumerate(graph.transitions):
            if edge.condition and edge.source in dominators:
                self._compile_expression(
                    edge.condition,
                    f"/transitions/{index}/condition",
                    self._context_schemas(
                        graph, dominators[edge.source] | {edge.source}, step_output_schemas
                    ),
                    add,
                    expected_schema={"type": "boolean"},
                )
        for index, step in enumerate(graph.steps):
            expression = step.config.get("expression") if step.type_code == "DECISION" else None
            if isinstance(expression, str) and step.key in dominators:
                self._compile_expression(
                    expression,
                    f"/steps/{index}/config/expression",
                    self._context_schemas(
                        graph, dominators[step.key] - {step.key}, step_output_schemas
                    ),
                    add,
                    expected_schema={"type": "string"},
                )

        if issues:
            return GraphValidationResult(valid=False, issues=issues)
        value = graph.model_dump(mode="json")
        if graph.interface is None:
            value.pop("interface", None)
        else:
            for field, default in (
                ("category", "general"),
                ("help_messages", {}),
                ("sample_inputs", {}),
                ("required_capabilities", []),
            ):
                if value["interface"].get(field) == default:
                    value["interface"].pop(field, None)
        for step, source_step in zip(value["steps"], graph.steps, strict=True):
            step["type_version_ref"] = self._stable_ref(step.get("type_version_ref"))
            step["form_ref"] = self._stable_ref(step.get("form_ref"))
            if source_step.subprocess is None:
                step.pop("subprocess", None)
            else:
                step["subprocess"]["workflow_version_ref"] = self._stable_ref(
                    source_step.subprocess.workflow_version_ref
                )
            flow = source_step.flow.model_dump(mode="json", exclude_defaults=True)
            if flow:
                step["flow"] = flow
            else:
                step.pop("flow", None)
        for target in value["targets"]:
            target["user_ref"] = self._stable_ref(target.get("user_ref"))
            target["work_group_ref"] = self._stable_ref(target.get("work_group_ref"))
        value["steps"].sort(key=lambda item: (item["display_order"], item["key"]))
        value["bindings"].sort(
            key=lambda item: (item["step"], item["target_port"], item["ordinal"])
        )
        value["targets"].sort(
            key=lambda item: (
                item["step"],
                item["priority"],
                item.get("user_ref") or "",
                item.get("work_group_ref") or "",
            )
        )
        value["transitions"].sort(
            key=lambda item: (
                item["source"],
                item["outcome"],
                item["priority"],
                item["target"],
            )
        )
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return GraphValidationResult(
            valid=True, checksum=hashlib.sha256(payload.encode()).hexdigest()
        )

    @staticmethod
    def _can_reach(source: str, target: str, adjacency: dict[str, set[str]]) -> bool:
        pending = [source]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in seen:
                continue
            seen.add(current)
            pending.extend(adjacency[current] - seen)
        return False

    @staticmethod
    def _cyclic_components(nodes: set[str], adjacency: dict[str, set[str]]) -> list[set[str]]:
        """Return strongly connected components that contain a cycle."""
        index = 0
        indexes: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        stacked: set[str] = set()
        result: list[set[str]] = []

        def visit(node: str) -> None:
            nonlocal index
            indexes[node] = low[node] = index
            index += 1
            stack.append(node)
            stacked.add(node)
            for target in adjacency[node]:
                if target not in indexes:
                    visit(target)
                    low[node] = min(low[node], low[target])
                elif target in stacked:
                    low[node] = min(low[node], indexes[target])
            if low[node] != indexes[node]:
                return
            component: set[str] = set()
            while stack:
                item = stack.pop()
                stacked.remove(item)
                component.add(item)
                if item == node:
                    break
            if len(component) > 1 or node in adjacency[node]:
                result.append(component)

        for node in sorted(nodes):
            if node not in indexes:
                visit(node)
        return result

    @staticmethod
    def _compatible(source: dict[str, Any], target: dict[str, Any]) -> bool:
        ignored = {"title", "description", "default", "examples"}
        return {key: value for key, value in source.items() if key not in ignored} == {
            key: value for key, value in target.items() if key not in ignored
        }

    @staticmethod
    def _assignable(source: dict[str, Any], target: dict[str, Any]) -> bool:
        if not target:
            return True
        source_type = source.get("type")
        target_type = target.get("type")
        source_types = {source_type} if isinstance(source_type, str) else set(source_type or [])
        target_types = {target_type} if isinstance(target_type, str) else set(target_type or [])
        if not source_types or not source_types <= target_types:
            return False
        target_format = target.get("format")
        return target_format is None or bool(source.get("format") == target_format)

    def _compile_expression(
        self,
        source: str,
        pointer: str,
        schemas: dict[str, dict[str, Any]],
        add: Any,
        *,
        expected_schema: dict[str, Any],
    ) -> None:
        try:
            self.compiler.compile(source, schemas, expected_schema=expected_schema)
        except ExpressionError as exc:
            add(
                pointer,
                exc.code,
                line=exc.line,
                column=exc.column,
                expected_schema=exc.expected_schema,
                actual_schema=exc.actual_schema,
            )

    @classmethod
    def _context_schemas(
        cls,
        graph: GraphSnapshot,
        accessible_steps: set[str],
        step_output_schemas: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        request = cls._object_schema()
        process = cls._object_schema(
            {
                "priority": {"type": "integer"},
                "status": {"type": "string"},
            }
        )
        current_user = cls._object_schema(
            {
                "ref_id": {"type": "string"},
                "is_superuser": {"type": "boolean"},
                "work_group_refs": {"type": "array", "items": {"type": "string"}},
            }
        )
        outputs: dict[str, dict[str, Any]] = defaultdict(dict)
        for step, schemas in (step_output_schemas or {}).items():
            if step in accessible_steps:
                outputs[step].update(schemas)
        for binding in graph.bindings:
            if not binding.source_schema:
                continue
            source = binding.source_schema
            if binding.source_path:
                source = cls._schema_at(source, binding.source_path) or source
            if binding.source_kind == "REQUEST":
                cls._add_source_property(request, binding.source_path, source)
            elif binding.source_kind == "CONTEXT":
                cls._add_source_property(process, binding.source_path, source)
            elif (
                binding.source_kind == "STEP_OUTPUT"
                and binding.source_step in accessible_steps
                and binding.source_port
            ):
                outputs[binding.source_step][binding.source_port] = source
        step_properties = {
            key: cls._object_schema({"outputs": cls._object_schema(properties)})
            for key, properties in outputs.items()
        }
        return {
            "request": request,
            "process": process,
            "current_user": current_user,
            "steps": cls._object_schema(step_properties),
            "client": client_expression_schema(),
        }

    @staticmethod
    def _object_schema(properties: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties or {},
            "additionalProperties": False,
        }

    @classmethod
    def _add_source_property(
        cls, root: dict[str, Any], path: str | None, schema: dict[str, Any]
    ) -> None:
        if not path:
            return
        parts = [
            part.replace("~1", "/").replace("~0", "~")
            for part in path.removeprefix("/").split("/")
            if part not in {"properties", "items"}
        ]
        if not parts:
            return
        current = root
        for part in parts[:-1]:
            properties = current.setdefault("properties", {})
            current = properties.setdefault(part, cls._object_schema())
        current.setdefault("properties", {})[parts[-1]] = schema

    @staticmethod
    def _schema_at(schema: dict[str, Any], path: str) -> dict[str, Any] | None:
        current: Any = schema
        for raw in path.removeprefix("/").split("/") if path != "/" else []:
            segment = raw.replace("~1", "/").replace("~0", "~")
            if not isinstance(current, dict):
                return None
            if segment in current:
                current = current[segment]
            elif current.get("type") == "object":
                current = current.get("properties", {}).get(segment)
            elif current.get("type") == "array":
                current = current.get("items")
            else:
                return None
        return current if isinstance(current, dict) else None

    @staticmethod
    def _stable_ref(value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return str(open_ref_id(value)[0])
        except InvalidReferenceException:
            return value
