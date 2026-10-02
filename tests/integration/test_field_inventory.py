"""PostgreSQL evidence for exact inventory snapshots and workflow grants."""

import os
from uuid import uuid7

import pytest

from apps.designer.application.field_inventory import FieldInventoryService
from apps.designer.domain.field_inventory import FieldInventoryQuery
from apps.forms.application.library import LibraryService
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.forms.domain.library import ComponentDocument, LibraryCreate, LibraryVersionCreate
from apps.step_types.application.registry import get_registry
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
    WorkflowVersionUpdateDTO,
)
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotFoundException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_exact_draft_and_form_snapshot_denies_other_user_and_stale_revision():
    try:
        async with SessionFactory() as session:
            owner = UserEntity(username=f"inventory-{uuid7().hex}", hashed_password="hash")
            outsider = UserEntity(username=f"inventory-{uuid7().hex}", hashed_password="hash")
            session.add_all([owner, outsider])
            await session.flush()

            forms = FormService(session)
            form = await forms.create(
                FormCreateDTO(code=f"F{uuid7().hex}", name="Purchase"), owner.id
            )
            form_version = await forms.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(form.id, form.version),
                    number=1,
                    data_schema={
                        "type": "object",
                        "properties": {
                            "quantity": {"type": "integer"},
                            "note": {"type": "string"},
                        },
                    },
                    render_schema={"root": {"component": "vertical"}},
                ),
                owner,
            )
            workflows = WorkflowService(session, get_registry())
            workflow = await workflows.create(
                WorkflowCreateDTO(code=f"W{uuid7().hex}", name="Purchase"),
                owner.id,
            )
            version = await workflows.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                    number=1,
                )
            )
            query = FieldInventoryQuery(
                workflow_version_ref_id=create_ref_id(version.id, version.version),
                start_form_version_ref_id=create_ref_id(form_version.id, form_version.version),
            )
            inventory = FieldInventoryService(session)
            result = await inventory.analyze(query, owner)
            assert result.total == 2
            assert result.form_snapshots["start"]["ref_id"] == query.start_form_version_ref_id
            assert not result.complete
            assert result.summary.review_candidates == 0
            assert all(row.classification == "UNKNOWN_ANALYSIS" for row in result.fields)
            with pytest.raises(NotFoundException):
                await inventory.analyze(query, outsider)
            with pytest.raises(NotFoundException):
                await inventory.analyze(
                    query.model_copy(
                        update={
                            "workflow_version_ref_id": create_ref_id(
                                version.id, version.version + 1
                            )
                        }
                    ),
                    owner,
                )
            await workflows.update_version(
                query.workflow_version_ref_id,
                WorkflowVersionUpdateDTO(default_priority=1),
            )
            with pytest.raises(NotFoundException):
                await inventory.analyze(query, owner)
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_resolved_component_pin_is_reported_with_exact_checksum():
    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"inventory-pin-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            library = LibraryService(session)
            component_root = await library.create_definition(
                "component", LibraryCreate(code=f"C{uuid7().hex}", name="Item"), actor
            )
            component = await library.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(component_root.id, component_root.version),
                    number=1,
                    document=ComponentDocument(
                        data_schema={
                            "type": "object",
                            "properties": {
                                "quantity": {"type": "integer"},
                            },
                        },
                        render_schema={
                            "root": {
                                "component": "vertical",
                                "children": [
                                    {"component": "number", "scope": "/properties/quantity"},
                                ],
                            }
                        },
                    ).model_dump(),
                ),
                actor,
            )
            component = await library.publish(
                "component", create_ref_id(component.id, component.version), actor
            )
            form_service = FormService(session)
            form = await form_service.create(
                FormCreateDTO(code=f"F{uuid7().hex}", name="Order"), actor.id
            )
            form_version = await form_service.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(form.id, form.version),
                    number=1,
                    data_schema={
                        "type": "object",
                        "properties": {
                            "item": {"type": "object"},
                        },
                    },
                    render_schema={
                        "root": {
                            "component": "vertical",
                            "children": [
                                {"component": "vertical"},
                            ],
                        }
                    },
                    reuse_instances=[
                        {
                            "instance_key": "item",
                            "component_ref": create_ref_id(component.id, component.version),
                            "schema_pointer": "/properties/item",
                            "node_pointer": "/root/children/0",
                        }
                    ],
                ),
                actor,
            )
            workflows = WorkflowService(session, get_registry())
            workflow = await workflows.create(
                WorkflowCreateDTO(code=f"W{uuid7().hex}", name="Order"), actor.id
            )
            version = await workflows.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                    number=1,
                )
            )
            result = await FieldInventoryService(session).analyze(
                FieldInventoryQuery(
                    workflow_version_ref_id=create_ref_id(version.id, version.version),
                    start_form_version_ref_id=create_ref_id(form_version.id, form_version.version),
                ),
                actor,
            )
            assert len(result.resolved_pins) == 1
            assert result.resolved_pins[0].kind == "component"
            assert result.resolved_pins[0].checksum == component.checksum
            assert result.fields[0].path == "/properties/item/properties/quantity"
            assert result.fields[0].component_instance == "item"
            await session.rollback()
    finally:
        await engine.dispose()
