"""PostgreSQL integration coverage for workflow publication and immutability."""

import os
from uuid import uuid7

import pytest
from anyio import create_task_group
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.step_types.application.registry import builtin_registry
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphBinding,
    GraphSnapshot,
    GraphStep,
    GraphTarget,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowGrantDTO,
    WorkflowVersionCreateDTO,
)
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import ValidationDetailsException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


async def _step_refs(session: AsyncSession) -> dict[str, str]:
    rows = (
        await session.exec(
            select(StepTypeEntity, StepTypeVersionEntity)
            .join(
                StepTypeVersionEntity,
                col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
            )
            .where(StepTypeVersionEntity.status == "PUBLISHED")
        )
    ).all()
    return {root.code: create_ref_id(version.id, version.version) for root, version in rows}


@pytest.mark.anyio
async def test_workflow_publish_pins_dependencies_grants_access_and_freezes_graph() -> None:
    async with SessionFactory() as session:
        owner = UserEntity(username=f"workflow-owner-{uuid7().hex}", hashed_password="hash")
        grantee = UserEntity(username=f"workflow-user-{uuid7().hex}", hashed_password="hash")
        session.add_all([owner, grantee])
        await session.flush()

        forms = FormService(session)
        form = await forms.create(FormCreateDTO(code=f"WF{uuid7().hex}", name="Review"), owner.id)
        form_version = await forms.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(form.id, form.version),
                number=1,
                data_schema={
                    "type": "object",
                    "properties": {"comment": {"type": "string"}},
                    "required": ["comment"],
                },
                render_schema={
                    "dialect": "bpms.render/1",
                    "root": {
                        "component": "vertical",
                        "children": [
                            {
                                "component": "text",
                                "scope": "/properties/comment",
                                "label": "Comment",
                            }
                        ],
                    },
                    "outcomes": ["approve"],
                },
            )
        )
        form_version = await forms.publish(
            create_ref_id(form_version.id, form_version.version), owner.id
        )
        form_ref = create_ref_id(form_version.id, form_version.version)

        service = WorkflowService(session, builtin_registry())
        workflow = await service.create(
            WorkflowCreateDTO(code=f"W{uuid7().hex}", name="Review"), owner.id
        )
        assert await service.can_access(workflow, owner, "start")
        assert not await service.can_access(workflow, grantee, "view")
        await service.add_grant(
            create_ref_id(workflow.id, workflow.version),
            WorkflowGrantDTO(
                user_ref_id=create_ref_id(grantee.id, grantee.version), can_start=True
            ),
            owner.id,
        )
        assert await service.can_access(workflow, grantee, "view")
        assert await service.can_access(workflow, grantee, "start")

        version = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(workflow.id, workflow.version), number=1
            )
        )
        refs = await _step_refs(session)
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs["START"]),
                GraphStep(
                    key="review",
                    type_code="HUMAN_TASK",
                    type_version_ref=refs["HUMAN_TASK"],
                    form_ref=form_ref,
                    field_policy={
                        "read": ["/properties/comment"],
                        "write": ["/properties/comment"],
                        "required": ["/properties/comment"],
                        "hidden": [],
                    },
                    display_order=1,
                ),
                GraphStep(
                    key="finish",
                    type_code="FINISH",
                    type_version_ref=refs["FINISH"],
                    display_order=2,
                ),
            ],
            targets=[
                GraphTarget(step="review", user_ref=create_ref_id(grantee.id, grantee.version))
            ],
            transitions=[
                GraphTransition(source="start", target="review", outcome="next", is_default=True),
                GraphTransition(
                    source="review", target="finish", outcome="approve", is_default=True
                ),
            ],
        )
        version = await service.replace_graph(create_ref_id(version.id, version.version), graph)
        published = await service.publish(create_ref_id(version.id, version.version), owner.id)
        assert published.status == "PUBLISHED"
        assert published.graph_checksum == service.validator.validate(graph).checksum
        with pytest.raises(VersionConflictException):
            await service.replace_graph(create_ref_id(published.id, published.version), graph)
        await session.commit()
        version_id = published.id

    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text(
                    'UPDATE "WORKFLOW_STEP" SET "STEP_KEY" = \'changed\' '
                    'WHERE "WORKFLOW_VERSION_ID" = :version_id'
                ),
                {"version_id": version_id},
            )
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_workflow_publication_accepts_explicit_typed_transform_chain() -> None:
    async with SessionFactory() as session:
        owner = UserEntity(username=f"transform-owner-{uuid7().hex}", hashed_password="hash")
        session.add(owner)
        await session.flush()
        refs = await _step_refs(session)
        transform_root = (
            await session.exec(select(StepTypeEntity).where(StepTypeEntity.code == "TRANSFORM"))
        ).one()
        transform_v2 = (
            await session.exec(
                select(StepTypeVersionEntity).where(
                    StepTypeVersionEntity.step_type_id == transform_root.id,
                    StepTypeVersionEntity.number == 2,
                )
            )
        ).one()
        transform_ref = create_ref_id(transform_v2.id, transform_v2.version)

        service = WorkflowService(session, builtin_registry())
        workflow = await service.create(
            WorkflowCreateDTO(code=f"T{uuid7().hex}", name="Typed transform"), owner.id
        )
        version = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(workflow.id, workflow.version), number=1
            )
        )
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs["START"]),
                GraphStep(
                    key="parse",
                    type_code="TRANSFORM",
                    type_version_ref=transform_ref,
                    config={"conversion_key": "integer"},
                ),
                GraphStep(
                    key="render",
                    type_code="TRANSFORM",
                    type_version_ref=transform_ref,
                    config={"conversion_key": "string"},
                ),
                GraphStep(key="finish", type_code="FINISH", type_version_ref=refs["FINISH"]),
            ],
            bindings=[
                GraphBinding(
                    step="parse",
                    target_port="value",
                    target_schema={"type": ["string", "integer"]},
                    source_kind="REQUEST",
                    source_path="/properties/amount",
                    source_schema={
                        "type": "object",
                        "properties": {"amount": {"type": "string"}},
                    },
                ),
                GraphBinding(
                    step="render",
                    target_port="value",
                    target_schema={},
                    source_kind="STEP_OUTPUT",
                    source_step="parse",
                    source_port="result",
                    source_schema={"type": "integer"},
                ),
            ],
            transitions=[
                GraphTransition(source="start", target="parse", outcome="next", is_default=True),
                GraphTransition(source="parse", target="render", outcome="next", is_default=True),
                GraphTransition(source="render", target="finish", outcome="next", is_default=True),
            ],
        )
        await service.replace_graph(create_ref_id(version.id, version.version), graph)
        try:
            published = await service.publish(create_ref_id(version.id, version.version), owner.id)
        except ValidationDetailsException as exc:
            pytest.fail(f"Unexpected transform publication issues: {exc.issues}")
        assert published.status == "PUBLISHED"
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_workflow_publication_has_one_winner() -> None:
    async with SessionFactory() as session:
        owner = UserEntity(username=f"workflow-race-{uuid7().hex}", hashed_password="hash")
        session.add(owner)
        await session.flush()
        service = WorkflowService(session, builtin_registry())
        root = await service.create(
            WorkflowCreateDTO(code=f"R{uuid7().hex}", name="Concurrent"), owner.id
        )
        version = await service.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        refs = await _step_refs(session)
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs["START"]),
                GraphStep(
                    key="finish",
                    type_code="FINISH",
                    type_version_ref=refs["FINISH"],
                    display_order=1,
                ),
            ],
            transitions=[
                GraphTransition(source="start", target="finish", outcome="done", is_default=True)
            ],
        )
        version = await service.replace_graph(create_ref_id(version.id, version.version), graph)
        ref = create_ref_id(version.id, version.version)
        actor_id = owner.id
        await session.commit()

    results: list[str] = []

    async def publish() -> None:
        async with SessionFactory() as session:
            try:
                await WorkflowService(session, builtin_registry()).publish(ref, actor_id)
                await session.commit()
                results.append("published")
            except VersionConflictException:
                await session.rollback()
                results.append("conflict")

    async with create_task_group() as tasks:
        tasks.start_soon(publish)
        tasks.start_soon(publish)
    assert sorted(results) == ["conflict", "published"]
    await engine.dispose()
