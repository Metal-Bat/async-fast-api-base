"""Publication checks for pinned subprocess interfaces and calls."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.step_types.domain.entity import StepTypePortEntity
from apps.users.domain.entity import UserEntity
from apps.workflows.application.validation import GraphValidator
from apps.workflows.domain.dto import GraphSnapshot
from apps.workflows.domain.entity import (
    WorkflowDefinitionEntity,
    WorkflowStepEntity,
    WorkflowVersionEntity,
)
from apps.workflows.domain.subprocess import SubprocessCall, SubprocessInterface, SubprocessPort
from core.ref_id import open_ref_id
from utils.exceptions import InvalidReferenceException, ValidationDetailsException

if TYPE_CHECKING:
    from apps.workflows.application.service import WorkflowService

_MAX_DEPTH = 4
_MAX_DEPENDENCIES = 32


class SubprocessValidator:
    def __init__(self, session: AsyncSession, workflows: WorkflowService) -> None:
        self.session = session
        self.workflows = workflows

    async def validate(
        self, graph: GraphSnapshot, actor_id: UUID | None, parent_version_id: UUID | None
    ) -> None:
        issues: list[dict[str, str]] = []
        steps = {step.key: step for step in graph.steps}
        _, ports = await self.workflows._dependency_maps(graph)
        if graph.interface is not None:
            self._interface(graph, graph.interface, ports, issues)
        dependency_depths: dict[UUID, int] = {}
        for index, step in enumerate(graph.steps):
            pointer = f"/steps/{index}/subprocess"
            if step.type_code == "SUBPROCESS" and step.subprocess is None:
                issues.append({"pointer": pointer, "code": "subprocess.call.required"})
                continue
            if step.type_code != "SUBPROCESS" and step.subprocess is not None:
                issues.append({"pointer": pointer, "code": "subprocess.call.not_allowed"})
                continue
            if step.subprocess is None:
                continue
            if bool(step.timeout_seconds) or step.flow.model_dump(exclude_defaults=True):
                issues.append({"pointer": pointer, "code": "subprocess.lifecycle.unsupported"})
            try:
                child_id, revision = open_ref_id(step.subprocess.workflow_version_ref)
                child = await self.session.get(
                    WorkflowVersionEntity, child_id, with_for_update=True, populate_existing=True
                )
            except InvalidReferenceException:
                child = None
                revision = -1
            if child is not None and child.id == parent_version_id:
                issues.append({"pointer": pointer, "code": "subprocess.call.recursive"})
                continue
            root = (
                await self.session.get(WorkflowDefinitionEntity, child.workflow_definition_id)
                if child is not None
                else None
            )
            actor = await self.session.get(UserEntity, actor_id) if actor_id else None
            if (
                child is None
                or child.version != revision
                or child.status != "PUBLISHED"
                or child.subprocess_interface is None
                or root is None
                or root.deleted_at
                or not root.is_active
                or (actor is not None and not await self.workflows.can_access(root, actor, "start"))
            ):
                issues.append(
                    {
                        "pointer": f"{pointer}/workflow_version_ref",
                        "code": "subprocess.version.unavailable",
                    }
                )
                continue
            interface = SubprocessInterface.model_validate(child.subprocess_interface)
            self._call(graph, index, step.subprocess, interface, steps, ports, issues)
            try:
                await self._dependencies(
                    child.id,
                    {parent_version_id} if parent_version_id else set(),
                    1,
                    dependency_depths,
                )
            except ValueError as exc:
                issues.append({"pointer": pointer, "code": str(exc)})
        if issues:
            raise ValidationDetailsException(issues[:64])

    @staticmethod
    def _interface(
        graph: GraphSnapshot,
        interface: SubprocessInterface,
        ports: dict[tuple[str, str, str], StepTypePortEntity],
        issues: list[dict[str, str]],
    ) -> None:
        steps = {step.key: step for step in graph.steps}
        for index, port in enumerate((*interface.inputs, *interface.outputs)):
            try:
                Draft202012Validator.check_schema(port.value_schema)
            except SchemaError:
                issues.append(
                    {
                        "pointer": f"/interface/ports/{index}/schema",
                        "code": "subprocess.schema.invalid",
                    }
                )
            if (
                isinstance(port, SubprocessPort)
                and port.assignment
                and port.value_schema.get("type") != "string"
            ):
                issues.append(
                    {
                        "pointer": f"/interface/inputs/{index}/schema",
                        "code": "subprocess.assignment.type",
                    }
                )
        input_ports = {port.name: port for port in interface.inputs}
        if interface.sample_inputs:
            if set(interface.sample_inputs) != set(input_ports):
                issues.append(
                    {"pointer": "/interface/sample_inputs", "code": "subprocess.sample.inputs"}
                )
            for name, value in interface.sample_inputs.items():
                port = input_ports.get(name)
                if port is None:
                    continue
                try:
                    Draft202012Validator(port.value_schema).validate(value)
                except SchemaError, ValidationError:
                    issues.append(
                        {
                            "pointer": f"/interface/sample_inputs/{name}",
                            "code": "subprocess.sample.invalid",
                        }
                    )
        for index, port in enumerate(interface.outputs):
            source = ports.get((port.source_step, "OUTPUT", port.source_port))
            if source is None or not GraphValidator._compatible(
                source.value_schema, port.value_schema
            ):
                issues.append(
                    {"pointer": f"/interface/outputs/{index}", "code": "subprocess.output.invalid"}
                )
            elif any(
                not SubprocessValidator._dominates(graph, port.source_step, finish_key)
                for finish_key in interface.outcomes.values()
            ):
                issues.append(
                    {
                        "pointer": f"/interface/outputs/{index}",
                        "code": "subprocess.output.not_prior",
                    }
                )
        for outcome, finish_key in interface.outcomes.items():
            if finish_key not in steps or steps[finish_key].type_code != "FINISH":
                issues.append(
                    {
                        "pointer": f"/interface/outcomes/{outcome}",
                        "code": "subprocess.outcome.finish_required",
                    }
                )
        if len(set(interface.outcomes.values())) != len(interface.outcomes):
            issues.append(
                {"pointer": "/interface/outcomes", "code": "subprocess.outcome.duplicate_finish"}
            )

    @staticmethod
    def _call(
        graph: GraphSnapshot,
        index: int,
        call: SubprocessCall,
        interface: SubprocessInterface,
        steps: dict[str, Any],
        ports: dict[tuple[str, str, str], StepTypePortEntity],
        issues: list[dict[str, str]],
    ) -> None:
        declared = {port.name: port for port in interface.inputs}
        mapped = {item.name for item in call.inputs}
        if any(port.required and port.name not in mapped for port in interface.inputs):
            issues.append(
                {
                    "pointer": f"/steps/{index}/subprocess/inputs",
                    "code": "subprocess.input.required",
                }
            )
        if mapped - declared.keys():
            issues.append(
                {"pointer": f"/steps/{index}/subprocess/inputs", "code": "subprocess.input.unknown"}
            )
        for position, mapping in enumerate(call.inputs):
            target = declared.get(mapping.name)
            if target is None:
                continue
            source_schema = mapping.source_schema
            if mapping.source_kind == "STEP_OUTPUT":
                source = ports.get((mapping.source_step or "", "OUTPUT", mapping.source_port or ""))
                if source is None or source.value_schema != source_schema:
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/subprocess/inputs/{position}",
                            "code": "subprocess.source.invalid",
                        }
                    )
                elif not SubprocessValidator._dominates(
                    graph, mapping.source_step or "", graph.steps[index].key
                ):
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/subprocess/inputs/{position}",
                            "code": "subprocess.source.not_prior",
                        }
                    )
            if not GraphValidator._compatible(source_schema, target.value_schema):
                issues.append(
                    {
                        "pointer": f"/steps/{index}/subprocess/inputs/{position}/source_schema",
                        "code": "subprocess.input.type_mismatch",
                    }
                )
            if mapping.source_kind == "CONSTANT":
                try:
                    Draft202012Validator(target.value_schema).validate(mapping.constant_value)
                except SchemaError, ValidationError:
                    issues.append(
                        {
                            "pointer": f"/steps/{index}/subprocess/inputs/{position}/constant_value",
                            "code": "subprocess.input.constant_invalid",
                        }
                    )
        declared_outcomes = set(interface.outcomes) | {"failure"}
        if not any(
            edge.source == graph.steps[index].key and edge.outcome in interface.outcomes
            for edge in graph.transitions
        ):
            issues.append(
                {
                    "pointer": f"/steps/{index}/subprocess",
                    "code": "subprocess.success_transition.required",
                }
            )
        declared_outcomes = set(interface.outcomes) | {"failure"}
        if not any(
            edge.source == graph.steps[index].key and edge.outcome == "failure"
            for edge in graph.transitions
        ):
            issues.append(
                {
                    "pointer": f"/steps/{index}/subprocess",
                    "code": "subprocess.failure_transition.required",
                }
            )
        for position, edge in enumerate(graph.transitions):
            if edge.source == graph.steps[index].key and edge.outcome not in declared_outcomes:
                issues.append(
                    {
                        "pointer": f"/transitions/{position}/outcome",
                        "code": "subprocess.outcome.unknown",
                    }
                )

    @staticmethod
    def _dominates(graph: GraphSnapshot, source: str, target: str) -> bool:
        start = next((step.key for step in graph.steps if step.type_code == "START"), None)
        if start is None or source == target:
            return False
        adjacency: dict[str, set[str]] = {}
        for edge in graph.transitions:
            adjacency.setdefault(edge.source, set()).add(edge.target)
        pending = [start]
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            if current == source or current in seen:
                continue
            if current == target:
                return False
            seen.add(current)
            pending.extend(adjacency.get(current, ()))
        return True

    async def _dependencies(
        self, version_id: UUID, ancestors: set[UUID], depth: int, depths: dict[UUID, int]
    ) -> None:
        if version_id in ancestors:
            raise ValueError("subprocess.call.recursive")
        if depth > _MAX_DEPTH:
            raise ValueError("subprocess.call.limit")
        if version_id not in depths and len(depths) >= _MAX_DEPENDENCIES:
            raise ValueError("subprocess.call.limit")
        if depths.get(version_id, 0) >= depth:
            return
        depths[version_id] = depth
        calls = (
            await self.session.exec(
                select(WorkflowStepEntity.subprocess_call).where(
                    WorkflowStepEntity.workflow_version_id == version_id,
                    col(WorkflowStepEntity.subprocess_call).is_not(None),
                )
            )
        ).all()
        for value in calls:
            if not isinstance(value, dict):
                raise TypeError("subprocess.call.invalid")
            child_id, _ = open_ref_id(SubprocessCall.model_validate(value).workflow_version_ref)
            await self._dependencies(child_id, ancestors | {version_id}, depth + 1, depths)
