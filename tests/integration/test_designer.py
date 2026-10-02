"""PostgreSQL authorization and reachability checks for designer support."""

import os
from uuid import uuid7

import pytest
from sqlmodel import col, select

from apps.designer.application.service import DesignerService
from apps.designer.domain.dto import CompletionQuery, DesignerQuery
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import RequestTypeCreateDTO
from apps.step_types.application.registry import builtin_registry
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphBinding,
    GraphSnapshot,
    GraphStep,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotFoundException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_private_selectors_and_completion_hide_forward_steps() -> None:
    async with SessionFactory() as session:
        owner = UserEntity(username=f"designer-{uuid7().hex}", hashed_password="hash")
        outsider = UserEntity(username=f"outsider-{uuid7().hex}", hashed_password="hash")
        session.add_all([owner, outsider])
        await session.flush()

        forms = FormService(session)
        form = await forms.create(
            FormCreateDTO(code=f"DF{uuid7().hex}", name="Designer form"), owner.id
        )
        form_version = await forms.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(form.id, form.version),
                number=1,
                data_schema={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "integer"},
                        "customer": {
                            "type": "object",
                            "properties": {"name": {"type": ["string", "null"]}},
                        },
                    },
                    "required": ["amount"],
                },
                render_schema={
                    "dialect": "bpms.render/1",
                    "root": {"component": "vertical", "children": []},
                },
            )
        )
        await forms.publish(create_ref_id(form_version.id, form_version.version), owner.id)

        type_rows = (
            await session.exec(
                select(StepTypeEntity.code, StepTypeVersionEntity)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
                )
                .where(StepTypeVersionEntity.status == "PUBLISHED")
            )
        ).all()
        refs = {
            (code, version.number): create_ref_id(version.id, version.version)
            for code, version in type_rows
        }
        workflows = WorkflowService(session, builtin_registry())
        workflow = await workflows.create(
            WorkflowCreateDTO(code=f"DW{uuid7().hex}", name="Private designer workflow"),
            owner.id,
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(workflow.id, workflow.version), number=1
            )
        )
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                GraphStep(
                    key="before",
                    type_code="TRANSFORM",
                    type_version_ref=refs[("TRANSFORM", 2)],
                    config={"conversion_key": "integer"},
                ),
                GraphStep(
                    key="current",
                    type_code="TRANSFORM",
                    type_version_ref=refs[("TRANSFORM", 2)],
                    config={"conversion_key": "string"},
                ),
                GraphStep(
                    key="future",
                    type_code="TRANSFORM",
                    type_version_ref=refs[("TRANSFORM", 2)],
                    config={"conversion_key": "string"},
                ),
                GraphStep(
                    key="finish",
                    type_code="FINISH",
                    type_version_ref=refs[("FINISH", 1)],
                ),
            ],
            bindings=[
                GraphBinding(
                    step="before",
                    target_port="value",
                    target_schema={"type": ["string", "integer"]},
                    source_kind="REQUEST",
                    source_path="/properties/amount",
                    source_schema={
                        "type": "object",
                        "properties": {"amount": {"type": "integer"}},
                    },
                ),
                GraphBinding(
                    step="current",
                    target_port="value",
                    target_schema={},
                    source_kind="STEP_OUTPUT",
                    source_step="before",
                    source_port="result",
                    source_schema={"type": "integer"},
                ),
                GraphBinding(
                    step="future",
                    target_port="value",
                    target_schema={},
                    source_kind="STEP_OUTPUT",
                    source_step="current",
                    source_port="result",
                    source_schema={"type": "string"},
                ),
            ],
            transitions=[
                GraphTransition(source="start", target="before", outcome="next", is_default=True),
                GraphTransition(source="before", target="current", outcome="next", is_default=True),
                GraphTransition(source="current", target="future", outcome="next", is_default=True),
                GraphTransition(source="future", target="finish", outcome="next", is_default=True),
            ],
        )
        validation = await workflows.validate_graph(graph, owner.id)
        assert validation.valid, validation.issues
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph, owner.id)
        published = await workflows.publish(create_ref_id(version.id, version.version), owner.id)
        request_type = await RequestService(session).create_type(
            RequestTypeCreateDTO(
                code=f"DR{uuid7().hex}",
                name="Private request type",
                workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )

        designer = DesignerService(session)
        owner_workflows = await designer.selector("workflows", DesignerQuery(), owner)
        outsider_workflows = await designer.selector("workflows", DesignerQuery(), outsider)
        assert [item.value for item in owner_workflows.items] == ["Private designer workflow"]
        assert outsider_workflows.items == []
        assert (await designer.selector("request_types", DesignerQuery(), outsider)).items == []

        completion = await designer.completion(
            CompletionQuery(
                workflow_version_ref_id=create_ref_id(published.id, published.version),
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                current_step_key="current",
                size=100,
            ),
            owner,
        )
        paths = {item.path: item for item in completion.items}
        assert paths["client.release"].nullable is True
        assert paths["client.release"].type_schema["format"] == "client-release"
        assert paths["client.renderer_capabilities"].cardinality == "LIST"
        assert paths["client.trusted"].source == "client"
        assert paths["request.amount"].nullable is False
        assert paths["request.customer.name"].nullable is True
        assert "steps.before.outputs.result" in paths
        assert paths["steps.before.outputs.result"].type_schema == {"type": "integer"}
        assert "steps.current.outputs.result" not in paths
        assert "steps.future.outputs.result" not in paths

        with pytest.raises(NotFoundException, match="Workflow version not found"):
            await designer.completion(
                CompletionQuery(
                    workflow_version_ref_id=create_ref_id(published.id, published.version),
                    request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                    current_step_key="current",
                ),
                outsider,
            )
        await session.rollback()
    await engine.dispose()
