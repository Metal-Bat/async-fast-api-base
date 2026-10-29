"""Read authorized authoring context and explicit samples; never load execution inputs."""

from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.step_types.application.registry import get_registry
from apps.users.domain.entity import UserEntity
from apps.workflows.application.object_projection import (
    InputField,
    compiled_type_schema,
    compose_input_fields,
)
from apps.workflows.application.service import WorkflowService
from apps.workflows.application.validation import project_binding_schema
from apps.workflows.domain.dto import GraphIssue
from apps.workflows.domain.entity import WorkflowDefinitionEntity
from apps.workflows.domain.object_preview import (
    BindingPreviewDTO,
    BindingPreviewField,
    BindingPreviewInput,
)
from apps.workflows.domain.object_projection import ProjectionError
from core.ref_id import create_ref_id, open_ref_id
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException


def value_type(
    value: Any,
) -> Literal["null", "boolean", "integer", "number", "string", "array", "object"]:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


async def preview_object_fields(
    session: AsyncSession, reference: str, data: BindingPreviewInput, actor: UserEntity
) -> BindingPreviewDTO:
    workflows = WorkflowService(session, get_registry())
    version = await workflows.get_version(reference)
    root = await session.get(WorkflowDefinitionEntity, version.workflow_definition_id)
    if (
        root is None
        or root.deleted_at is not None
        or not root.is_active
        or not await workflows.can_access(root, actor, "view")
    ):
        raise NotFoundException("Workflow not found")
    if version.version != open_ref_id(reference)[1]:
        raise VersionConflictException("Workflow version is stale")
    reply = BindingPreviewDTO(
        workflow_version_ref=create_ref_id(version.id, version.version),
        candidate_checksum=None,
        target_step=data.target_step,
        target_port=data.target_port,
        sample_state="INVALID",
    )
    try:
        validation, outputs = await workflows.analyze_graph(
            data.graph, actor.id, parent_version_id=version.id
        )
    except ValidationDetailsException as error:
        reply.issues = [
            GraphIssue(pointer=issue["pointer"], code=issue["code"]) for issue in error.issues[:64]
        ]
        return reply
    reply.candidate_checksum = validation.checksum
    if not validation.valid:
        reply.issues = [
            GraphIssue(pointer=issue.pointer, code=issue.code) for issue in validation.issues[:64]
        ]
        return reply
    bindings = [
        item
        for item in data.graph.bindings
        if item.step == data.target_step and item.target_port == data.target_port
    ]
    if not bindings or any(item.target_projection is None for item in bindings):
        reply.issues = [GraphIssue(pointer="/bindings", code="binding.preview.projection.required")]
        return reply
    samples = {item.ordinal: item.value for item in data.samples}
    supplied = {item.ordinal for item in bindings if item.source_kind != "CONSTANT"}
    if samples.keys() - supplied:
        reply.issues = [GraphIssue(pointer="/samples", code="binding.preview.sample.unknown")]
        return reply
    fields = []
    for binding in sorted(bindings, key=lambda item: item.ordinal):
        if binding.target_projection is None:
            continue
        if binding.source_kind == "CONSTANT":
            value = binding.constant_value
            origin = "VISIBLE_CONSTANT"
        elif binding.ordinal not in samples:
            reply.sample_state = "MISSING"
            reply.issues.append(
                GraphIssue(
                    pointer=f"/samples/{binding.ordinal}", code="binding.preview.sample.missing"
                )
            )
            continue
        else:
            value = samples[binding.ordinal]
            origin = "AUTHOR"
            schema = outputs.get(binding.source_step or "", {}).get(
                binding.source_port or "", binding.source_schema
            )
            if schema is not None and bool(binding.source_path):
                schema = project_binding_schema(schema, binding.source_path)
            try:
                if schema is None or not Draft202012Validator(
                    compiled_type_schema(schema), format_checker=FormatChecker()
                ).is_valid(value):
                    raise ProjectionError("binding.preview.sample.invalid")
            except ProjectionError:
                reply.issues.append(
                    GraphIssue(
                        pointer=f"/samples/{binding.ordinal}", code="binding.preview.sample.invalid"
                    )
                )
                continue
        fields.append(
            InputField(binding.target_projection, binding.target_schema, binding.ordinal, value)
        )
        reply.fields.append(
            BindingPreviewField(
                path=binding.target_projection.path,
                source_kind=binding.source_kind,
                sample_origin=origin,
                value_type=value_type(value),
            )
        )
    if reply.issues:
        if any(issue.code != "binding.preview.sample.missing" for issue in reply.issues):
            reply.sample_state = "INVALID"
        return reply
    try:
        versions, ports = await workflows._dependency_maps(data.graph)
        target = ports.get((data.target_step, "INPUT", data.target_port))
        if target is None:
            raise ProjectionError("binding.target_port.unknown")
        registered = target.value_schema
        step = next(item for item in data.graph.steps if item.key == data.target_step)
        pin = versions[step.type_version_ref or ""]
        contract = get_registry().transform_contract(
            pin.handler_key, pin.handler_version, step.config
        )
        if contract is not None and data.target_port == "value":
            registered = contract[0]
        compose_input_fields(fields, registered)
    except ProjectionError as error:
        reply.issues = [GraphIssue(pointer="/bindings", code=error.code)]
        return reply
    reply.sample_state = "VALID"
    return reply
