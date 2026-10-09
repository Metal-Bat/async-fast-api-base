"""PostgreSQL publication and pinning of reusable workflow interfaces."""

import os
from uuid import uuid7

import pytest
from sqlmodel import col, select

from apps.designer.application.field_inventory import FieldInventoryService
from apps.designer.application.service import DesignerService
from apps.designer.domain.dto import DesignerQuery
from apps.designer.domain.field_inventory import FieldInventoryQuery
from apps.step_types.application.registry import builtin_registry
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphSnapshot,
    GraphStep,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from apps.workflows.domain.subprocess import SubprocessCall, SubprocessInterface
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import ValidationDetailsException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


async def _refs(session):
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


def _graph(refs, *, interface=None, child_ref=None):
    steps = [GraphStep(key="start", type_code="START", type_version_ref=refs["START"])]
    transitions = []
    if child_ref:
        steps.append(
            GraphStep(
                key="call",
                type_code="SUBPROCESS",
                type_version_ref=refs["SUBPROCESS"],
                subprocess=SubprocessCall(workflow_version_ref=child_ref),
            )
        )
        transitions.append(GraphTransition(source="start", target="call", outcome="next"))
        transitions.append(GraphTransition(source="call", target="finish", outcome="failure"))
        last = "call"
        outcome = "approved"
    else:
        last = "start"
        outcome = "next"
    steps.append(GraphStep(key="finish", type_code="FINISH", type_version_ref=refs["FINISH"]))
    transitions.append(GraphTransition(source=last, target="finish", outcome=outcome))
    return GraphSnapshot(steps=steps, transitions=transitions, interface=interface)


@pytest.mark.anyio
async def test_published_subprocess_is_pinned_and_retirement_does_not_change_parent() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"subprocess-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        refs = await _refs(session)
        service = WorkflowService(session, builtin_registry())
        child_root = await service.create(
            WorkflowCreateDTO(code=f"Child{uuid7().hex}", name="ManagerApproval"), actor.id
        )
        child = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(child_root.id, child_root.version), number=1
            )
        )
        child = await service.replace_graph(
            create_ref_id(child.id, child.version),
            _graph(refs, interface=SubprocessInterface(outcomes={"approved": "finish"})),
            actor.id,
        )
        child = await service.publish(create_ref_id(child.id, child.version), actor.id)
        child_ref = create_ref_id(child.id, child.version)
        catalog = await DesignerService(session).catalog(
            DesignerQuery(search="ManagerApproval"), actor
        )
        assert len(catalog.items) == 1
        assert catalog.items[0].category == "subprocess"
        metadata = catalog.items[0].model_dump(mode="json")["metadata"]
        assert metadata["runtime_available"] is True
        assert metadata["interface"]["outcomes"] == {"approved": "finish"}
        parent_root = await service.create(
            WorkflowCreateDTO(code=f"Parent{uuid7().hex}", name="PurchaseRequest"), actor.id
        )
        parent = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version), number=1
            )
        )
        missing_success = _graph(refs, child_ref=child_ref)
        missing_success.transitions = [
            edge for edge in missing_success.transitions if edge.outcome != "approved"
        ]
        with pytest.raises(ValidationDetailsException) as missing_route:
            await service.replace_graph(
                create_ref_id(parent.id, parent.version), missing_success, actor.id
            )
        assert any(
            issue["code"] == "subprocess.success_transition.required"
            for issue in missing_route.value.issues
        )
        parent = await service.replace_graph(
            create_ref_id(parent.id, parent.version), _graph(refs, child_ref=child_ref), actor.id
        )
        parent = await service.publish(create_ref_id(parent.id, parent.version), actor.id)
        pinned_checksum = parent.graph_checksum
        inventory = await FieldInventoryService(session).analyze(
            FieldInventoryQuery(workflow_version_ref_id=create_ref_id(parent.id, parent.version)),
            actor,
        )
        assert inventory.complete
        assert any(
            pin.kind == "subprocess"
            and pin.ref_id == child_ref
            and pin.checksum == child.graph_checksum
            for pin in inventory.resolved_pins
        )
        await service.retire(create_ref_id(child.id, child.version))
        snapshot = await service.snapshot(parent.id)
        call = next(step for step in snapshot.steps if step.key == "call").subprocess
        assert call is not None
        assert call.workflow_version_ref == child_ref
        assert parent.graph_checksum == pinned_checksum
        await session.commit()
    await engine.dispose()


@pytest.mark.anyio
async def test_unpublished_or_self_referencing_child_is_rejected() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"subprocess-invalid-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        refs = await _refs(session)
        service = WorkflowService(session, builtin_registry())
        root = await service.create(
            WorkflowCreateDTO(code=f"Self{uuid7().hex}", name="DocumentReview"), actor.id
        )
        version = await service.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        with pytest.raises(ValidationDetailsException) as error:
            await service.replace_graph(
                create_ref_id(version.id, version.version),
                _graph(refs, child_ref=create_ref_id(version.id, version.version)),
                actor.id,
            )
        assert any(issue["code"] == "subprocess.call.recursive" for issue in error.value.issues)
        other_root = await service.create(
            WorkflowCreateDTO(code=f"Draft{uuid7().hex}", name="DraftChild"), actor.id
        )
        other = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(other_root.id, other_root.version), number=1
            )
        )
        with pytest.raises(ValidationDetailsException) as unavailable:
            await service.replace_graph(
                create_ref_id(version.id, version.version),
                _graph(refs, child_ref=create_ref_id(other.id, other.version)),
                actor.id,
            )
        assert any(
            issue["code"] == "subprocess.version.unavailable" for issue in unavailable.value.issues
        )
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_call_rejects_type_mismatch_and_inaccessible_published_version() -> None:
    from apps.workflows.domain.subprocess import (
        SubprocessInputMapping,
        SubprocessOutput,
        SubprocessPort,
    )

    async with SessionFactory() as session:
        owner = UserEntity(username=f"sub-owner-{uuid7().hex}", hashed_password="hash")
        caller = UserEntity(username=f"sub-caller-{uuid7().hex}", hashed_password="hash")
        session.add_all([owner, caller])
        await session.flush()
        refs = await _refs(session)
        service = WorkflowService(session, builtin_registry())
        child_root = await service.create(
            WorkflowCreateDTO(code=f"Child{uuid7().hex}", name="DocumentReview"), owner.id
        )
        child = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(child_root.id, child_root.version), number=1
            )
        )
        invalid_output = _graph(
            refs,
            interface=SubprocessInterface(
                outputs=[
                    SubprocessOutput(
                        name="decision",
                        value_schema={"type": "string"},
                        source_step="start",
                        source_port="missing",
                    )
                ],
                outcomes={"approved": "finish"},
            ),
        )
        with pytest.raises(ValidationDetailsException) as output_error:
            await service.replace_graph(
                create_ref_id(child.id, child.version), invalid_output, owner.id
            )
        assert any(
            issue["code"] == "subprocess.output.invalid" for issue in output_error.value.issues
        )
        child = await service.replace_graph(
            create_ref_id(child.id, child.version),
            _graph(
                refs,
                interface=SubprocessInterface(
                    inputs=[SubprocessPort(name="amount", value_schema={"type": "integer"})],
                    outcomes={"approved": "finish"},
                ),
            ),
            owner.id,
        )
        child = await service.publish(create_ref_id(child.id, child.version), owner.id)
        parent_root = await service.create(
            WorkflowCreateDTO(code=f"Parent{uuid7().hex}", name="PurchaseRequest"), caller.id
        )
        parent = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version), number=1
            )
        )
        parent_ref = create_ref_id(parent.id, parent.version)
        child_ref = create_ref_id(child.id, child.version)
        wrong = _graph(refs, child_ref=child_ref)
        wrong.steps[1].subprocess.inputs = [
            SubprocessInputMapping(
                name="amount",
                source_kind="CONSTANT",
                source_schema={"type": "string"},
                constant_value="ten",
            )
        ]
        with pytest.raises(ValidationDetailsException) as denied:
            await service.replace_graph(parent_ref, wrong, caller.id)
        assert any(
            issue["code"] == "subprocess.version.unavailable" for issue in denied.value.issues
        )

        from apps.workflows.domain.dto import WorkflowGrantDTO

        await service.add_grant(
            create_ref_id(child_root.id, child_root.version),
            WorkflowGrantDTO(user_ref_id=create_ref_id(caller.id, caller.version), can_start=True),
            owner.id,
        )
        with pytest.raises(ValidationDetailsException) as mismatch:
            await service.replace_graph(parent_ref, wrong, caller.id)
        assert any(
            issue["code"] == "subprocess.input.type_mismatch" for issue in mismatch.value.issues
        )
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_nested_published_calls_validate_transitive_dependencies() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"sub-nested-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        refs = await _refs(session)
        service = WorkflowService(session, builtin_registry())
        child_ref = None
        for label in (
            "DocumentReview",
            "ManagerApproval",
            "FinanceReview",
            "PurchaseRequest",
            "LegalReview",
        ):
            root = await service.create(
                WorkflowCreateDTO(code=f"Nested{uuid7().hex}", name=label), actor.id
            )
            version = await service.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(root.id, root.version), number=1
                )
            )
            graph = _graph(
                refs,
                interface=SubprocessInterface(outcomes={"approved": "finish"}),
                child_ref=child_ref,
            )
            version = await service.replace_graph(
                create_ref_id(version.id, version.version), graph, actor.id
            )
            version = await service.publish(create_ref_id(version.id, version.version), actor.id)
            child_ref = create_ref_id(version.id, version.version)
        root = await service.create(
            WorkflowCreateDTO(code=f"TooDeep{uuid7().hex}", name="TooDeep"), actor.id
        )
        version = await service.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        with pytest.raises(ValidationDetailsException) as depth_error:
            await service.replace_graph(
                create_ref_id(version.id, version.version),
                _graph(refs, child_ref=child_ref),
                actor.id,
            )
        assert any(issue["code"] == "subprocess.call.limit" for issue in depth_error.value.issues)
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_publication_and_child_retirement_serialize_without_stale_new_pin() -> None:
    from anyio import create_task_group

    async with SessionFactory() as session:
        actor = UserEntity(username=f"sub-race-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        refs = await _refs(session)
        service = WorkflowService(session, builtin_registry())
        child_root = await service.create(
            WorkflowCreateDTO(code=f"RaceChild{uuid7().hex}", name="DocumentReview"), actor.id
        )
        child = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(child_root.id, child_root.version), number=1
            )
        )
        child = await service.replace_graph(
            create_ref_id(child.id, child.version),
            _graph(refs, interface=SubprocessInterface(outcomes={"approved": "finish"})),
            actor.id,
        )
        child = await service.publish(create_ref_id(child.id, child.version), actor.id)
        child_ref = create_ref_id(child.id, child.version)
        parent_root = await service.create(
            WorkflowCreateDTO(code=f"RaceParent{uuid7().hex}", name="PurchaseRequest"), actor.id
        )
        parent = await service.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version), number=1
            )
        )
        parent = await service.replace_graph(
            create_ref_id(parent.id, parent.version), _graph(refs, child_ref=child_ref), actor.id
        )
        parent_ref = create_ref_id(parent.id, parent.version)
        parent_id = parent.id
        child_id = child.id
        actor_id = actor.id
        await session.commit()

    outcomes = {}

    async def publish_parent():
        async with SessionFactory() as session:
            try:
                await WorkflowService(session, builtin_registry()).publish(parent_ref, actor_id)
                await session.commit()
                outcomes["publish"] = "published"
            except ValidationDetailsException:
                await session.rollback()
                outcomes["publish"] = "rejected"

    async def retire_child():
        async with SessionFactory() as session:
            await WorkflowService(session, builtin_registry()).retire(child_ref)
            await session.commit()
            outcomes["retire"] = "retired"

    async with create_task_group() as group:
        group.start_soon(publish_parent)
        group.start_soon(retire_child)

    async with SessionFactory() as session:
        from apps.workflows.domain.entity import WorkflowVersionEntity

        parent = await session.get(WorkflowVersionEntity, parent_id)
        child = await session.get(WorkflowVersionEntity, child_id)
        assert outcomes["retire"] == "retired"
        assert child is not None
        assert parent is not None
        assert child.status == "RETIRED"
        assert (parent.status == "PUBLISHED") == (outcomes["publish"] == "published")
        if parent.status == "PUBLISHED":
            snapshot = await WorkflowService(session, builtin_registry()).snapshot(parent_id)
            call = next(step for step in snapshot.steps if step.key == "call").subprocess
            assert call is not None
            assert call.workflow_version_ref == child_ref
    await engine.dispose()
