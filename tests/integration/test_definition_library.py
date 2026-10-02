"""PostgreSQL evidence for reusable-definition discovery and draft decisions."""

import os
from uuid import uuid7

import pytest

from apps.designer.application.draft_library import DraftLibraryService
from apps.designer.application.library import DefinitionLibraryService
from apps.designer.domain.library import (
    BulkUpgradeRequest,
    LibrarySearch,
    TemplateCreate,
    UpgradeTarget,
)
from apps.forms.application.library import LibraryService
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.forms.domain.library import (
    ComponentDocument,
    LibraryCreate,
    LibraryGrantCreate,
    LibraryVersionCreate,
    TypeDocument,
)
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotFoundException, ValidationDetailsException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_library_search_paginates_grants_and_nested_dependency_usage():
    try:
        async with SessionFactory() as session:
            owner = UserEntity(username=f"lib-owner-{uuid7().hex}", hashed_password="hash")
            viewer = UserEntity(username=f"lib-viewer-{uuid7().hex}", hashed_password="hash")
            session.add_all([owner, viewer])
            await session.flush()
            library = LibraryService(session)
            type_root = await library.create_definition(
                "data_type", LibraryCreate(code=f"LIBTYPE{uuid7().hex}", name="City"), owner
            )
            type_version = await library.create_version(
                "data_type",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(type_root.id, type_root.version),
                    number=1,
                    document=TypeDocument(
                        data_schema={"type": "string", "minLength": 2},
                        category="address",
                        sample_input="Tehran",
                    ).model_dump(),
                ),
                owner,
            )
            type_version = await library.publish(
                "data_type", create_ref_id(type_version.id, type_version.version), owner
            )
            type_ref = create_ref_id(type_version.id, type_version.version)
            address_root = await library.create_definition(
                "data_type",
                LibraryCreate(code=f"ADDRTYPE{uuid7().hex}", name="Address data"),
                owner,
            )
            address_type = await library.create_version(
                "data_type",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(address_root.id, address_root.version),
                    number=1,
                    document=TypeDocument(
                        data_schema={"type": "object", "properties": {"city": {"type": "string"}}},
                        uses=[{"schema_pointer": "/properties/city", "version_ref": type_ref}],
                        category="address",
                    ).model_dump(),
                ),
                owner,
            )
            address_type = await library.publish(
                "data_type", create_ref_id(address_type.id, address_type.version), owner
            )
            address_ref = create_ref_id(address_type.id, address_type.version)
            root = await library.create_definition(
                "component", LibraryCreate(code=f"LIBCOMP{uuid7().hex}", name="Address"), owner
            )
            component = await library.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    document=ComponentDocument(
                        data_schema={
                            "type": "object",
                            "properties": {"address": {"type": "object"}},
                        },
                        render_schema={
                            "root": {
                                "component": "text",
                                "scope": "/properties/address/properties/city",
                            }
                        },
                        types=[
                            {"schema_pointer": "/properties/address", "version_ref": address_ref}
                        ],
                        category="address",
                    ).model_dump(),
                ),
                owner,
            )
            component = await library.publish(
                "component", create_ref_id(component.id, component.version), owner
            )
            component_ref = create_ref_id(component.id, component.version)
            discovery = DefinitionLibraryService(session)
            assert (await discovery.search(LibrarySearch(kind="component"), viewer)).total == 0
            with pytest.raises(NotFoundException):
                await discovery.dependencies("component", component_ref, viewer)
            for kind, target in (
                ("data_type", type_root),
                ("data_type", address_root),
                ("component", root),
            ):
                await library.grant(
                    kind,
                    create_ref_id(target.id, target.version),
                    LibraryGrantCreate(user_ref_id=create_ref_id(viewer.id, viewer.version)),
                    owner,
                )
            page = await discovery.search(
                LibrarySearch(kind="component", category="address", size=1), viewer
            )
            assert page.total == 1 and len(page.items) == 1
            assert page.items[0].ref_id == component_ref
            assert page.items[0].category == "address"
            assert (
                await discovery.search(LibrarySearch(kind="component", page=2, size=1), viewer)
            ).items == []
            dependencies = await discovery.dependencies("component", component_ref, viewer)
            assert {(item.ref_id, item.depth) for item in dependencies} == {
                (address_ref, 1),
                (type_ref, 2),
            }
            usages = await discovery.where_used(
                "data_type", type_ref, LibrarySearch(size=100), viewer
            )
            assert usages.total >= 2
            assert any(item.ref_id == component_ref and not item.direct for item in usages.items)
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_template_is_independent_and_incompatible_bulk_apply_is_rejected():
    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"template-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            library = LibraryService(session)
            root = await library.create_definition(
                "component", LibraryCreate(code=f"ADDR{uuid7().hex}", name="Address"), actor
            )
            first = await library.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    document=ComponentDocument(
                        data_schema={
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                        },
                        render_schema={"root": {"component": "vertical"}},
                    ).model_dump(),
                ),
                actor,
            )
            first = await library.publish(
                "component", create_ref_id(first.id, first.version), actor
            )
            first_ref = create_ref_id(first.id, first.version)
            forms = FormService(session)
            form = await forms.create(
                FormCreateDTO(code=f"FORM{uuid7().hex}", name="Purchase"), actor.id
            )
            documents = FormDocuments(
                data_schema={
                    "type": "object",
                    "properties": {"billing": {"type": "object"}},
                },
                render_schema={
                    "root": {"component": "vertical", "children": [{"component": "vertical"}]}
                },
                reuse_instances=[
                    {
                        "instance_key": "billing",
                        "component_ref": first_ref,
                        "schema_pointer": "/properties/billing",
                        "node_pointer": "/root/children/0",
                    }
                ],
            )
            source = await forms.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(form.id, form.version),
                    number=1,
                    **documents.model_dump(),
                ),
                actor,
            )
            source = await forms.publish(create_ref_id(source.id, source.version), actor.id)
            drafts = DraftLibraryService(session)
            reference = await drafts.create_template(
                TemplateCreate(
                    kind="form",
                    source_ref_id=create_ref_id(source.id, source.version),
                    code=f"REF{uuid7().hex}",
                    name="Reference",
                    mode="REFERENCE",
                ),
                actor,
            )
            copied = await drafts.create_template(
                TemplateCreate(
                    kind="form",
                    source_ref_id=create_ref_id(source.id, source.version),
                    code=f"COPY{uuid7().hex}",
                    name="Copy",
                    mode="COPY",
                ),
                actor,
            )
            ref_row = await forms.get_version(reference.version_ref_id)
            copy_row = await forms.get_version(copied.version_ref_id)
            assert ref_row.id != source.id and copy_row.id != source.id
            assert (
                ref_row.reuse_instances and ref_row.reuse_instances[0]["component_ref"] == first_ref
            )
            assert copy_row.reuse_instances is None
            assert ref_row.template_source is not None
            assert ref_row.template_source["source_checksum"] == source.checksum
            incompatible = await library.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=2,
                    document=ComponentDocument(
                        data_schema={
                            "type": "object",
                            "properties": {"city": {"type": "integer"}},
                        },
                        render_schema={"root": {"component": "vertical"}},
                    ).model_dump(),
                ),
                actor,
            )
            incompatible = await library.publish(
                "component", create_ref_id(incompatible.id, incompatible.version), actor
            )
            request = BulkUpgradeRequest(
                targets=[
                    UpgradeTarget(
                        kind="form",
                        version_ref_id=reference.version_ref_id,
                        replacements={
                            "billing": create_ref_id(incompatible.id, incompatible.version)
                        },
                    )
                ]
            )
            report = await drafts.preview(request, actor)
            assert not report.compatible
            assert report.impacts[0].affected_bindings == ["/reuse_instances/billing"]
            with pytest.raises(ValidationDetailsException):
                await drafts.apply(request, actor)
            await session.refresh(ref_row)
            assert ref_row.reuse_instances[0]["component_ref"] == first_ref
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_workflow_template_keeps_call_pin_and_rejects_incompatible_upgrade():
    from sqlmodel import col, select

    from apps.step_types.application.registry import builtin_registry
    from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
    from apps.workflows.application.service import WorkflowService
    from apps.workflows.domain.dto import (
        GraphSnapshot,
        GraphStep,
        GraphTransition,
        WorkflowCreateDTO,
        WorkflowVersionCreateDTO,
    )
    from apps.workflows.domain.subprocess import SubprocessCall, SubprocessInterface

    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"workflow-template-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
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
            refs = {root.code: create_ref_id(version.id, version.version) for root, version in rows}
            workflow = WorkflowService(session, builtin_registry())

            async def child(number: int, outcome: str, capabilities: list[str] | None = None):
                root = await workflow.create(
                    WorkflowCreateDTO(code=f"CHILD{uuid7().hex}", name=f"Child {number}"),
                    actor.id,
                )
                version = await workflow.create_version(
                    WorkflowVersionCreateDTO(
                        workflow_ref_id=create_ref_id(root.id, root.version), number=1
                    )
                )
                graph = GraphSnapshot(
                    steps=[
                        GraphStep(key="start", type_code="START", type_version_ref=refs["START"]),
                        GraphStep(
                            key="finish", type_code="FINISH", type_version_ref=refs["FINISH"]
                        ),
                    ],
                    transitions=[GraphTransition(source="start", target="finish", outcome="next")],
                    interface=SubprocessInterface(
                        outcomes={outcome: "finish"},
                        category="approval",
                        help_messages={"en": "Approves a request"},
                        required_capabilities=capabilities or [],
                    ),
                )
                await workflow.replace_graph(
                    create_ref_id(version.id, version.version), graph, actor.id
                )
                await workflow.publish(create_ref_id(version.id, version.version), actor.id)
                return create_ref_id(version.id, version.version)

            approved_ref = await child(1, "approved")
            incompatible_ref = await child(2, "declined")
            compatible_ref = await child(3, "approved")
            capability_ref = await child(4, "approved", ["camera"])
            parent_root = await workflow.create(
                WorkflowCreateDTO(code=f"PARENT{uuid7().hex}", name="Parent"), actor.id
            )
            parent = await workflow.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(parent_root.id, parent_root.version), number=1
                )
            )
            graph = GraphSnapshot(
                steps=[
                    GraphStep(key="start", type_code="START", type_version_ref=refs["START"]),
                    GraphStep(
                        key="call",
                        type_code="SUBPROCESS",
                        type_version_ref=refs["SUBPROCESS"],
                        subprocess=SubprocessCall(workflow_version_ref=approved_ref),
                    ),
                    GraphStep(key="finish", type_code="FINISH", type_version_ref=refs["FINISH"]),
                ],
                transitions=[
                    GraphTransition(source="start", target="call", outcome="next"),
                    GraphTransition(source="call", target="finish", outcome="approved"),
                    GraphTransition(source="call", target="finish", outcome="failure"),
                ],
            )
            await workflow.replace_graph(create_ref_id(parent.id, parent.version), graph, actor.id)
            await workflow.publish(create_ref_id(parent.id, parent.version), actor.id)
            drafts = DraftLibraryService(session)
            template = await drafts.create_template(
                TemplateCreate(
                    kind="workflow",
                    source_ref_id=create_ref_id(parent.id, parent.version),
                    code=f"PARENT_COPY{uuid7().hex}",
                    name="Parent copy",
                    mode="REFERENCE",
                ),
                actor,
            )
            copied = await workflow.get_version(template.version_ref_id)
            assert copied.template_source is not None
            assert copied.template_source["source_ref_id"] == create_ref_id(
                parent.id, parent.version
            )
            current = await workflow.snapshot(copied.id)
            call = next(step for step in current.steps if step.key == "call").subprocess
            assert call is not None and call.workflow_version_ref == approved_ref
            discovery = DefinitionLibraryService(session)
            cards = await discovery.search(
                LibrarySearch(kind="subprocess", search="Child 1", category="approval"), actor
            )
            assert any(card.ref_id == approved_ref for card in cards.items)
            bad = BulkUpgradeRequest(
                targets=[
                    UpgradeTarget(
                        kind="workflow",
                        version_ref_id=template.version_ref_id,
                        replacements={"call": incompatible_ref},
                    )
                ]
            )
            report = await drafts.preview(bad, actor)
            assert not report.compatible
            with pytest.raises(ValidationDetailsException):
                await drafts.apply(bad, actor)
            call = next(
                step for step in (await workflow.snapshot(copied.id)).steps if step.key == "call"
            ).subprocess
            assert call is not None and call.workflow_version_ref == approved_ref
            capability_request = BulkUpgradeRequest(
                targets=[
                    UpgradeTarget(
                        kind="workflow",
                        version_ref_id=template.version_ref_id,
                        replacements={"call": capability_ref},
                    )
                ]
            )
            capability_report = await drafts.preview(capability_request, actor)
            assert not capability_report.compatible
            assert capability_report.impacts[0].capability_changes == ["camera"]
            assert any(
                issue["code"] == "library.capability_added"
                for issue in capability_report.impacts[0].issues
            )
            good = BulkUpgradeRequest(
                targets=[
                    UpgradeTarget(
                        kind="workflow",
                        version_ref_id=template.version_ref_id,
                        replacements={"call": compatible_ref},
                    )
                ]
            )
            assert (await drafts.preview(good, actor)).compatible
            assert (await drafts.apply(good, actor)).compatible
            call = next(
                step for step in (await workflow.snapshot(copied.id)).steps if step.key == "call"
            ).subprocess
            assert call is not None and call.workflow_version_ref == compatible_ref
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_form_explanation_reports_translation_gap_without_input_values():
    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"explanation-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            forms = FormService(session)
            root = await forms.create(
                FormCreateDTO(code=f"EXPLAIN{uuid7().hex}", name="Explanation"), actor.id
            )
            version = await forms.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    data_schema={"type": "object", "properties": {"city": {"type": "string"}}},
                    render_schema={
                        "root": {
                            "component": "text",
                            "scope": "/properties/city",
                            "messages": {"label": {"key": "city"}},
                            "rules": [
                                {
                                    "scope": "/properties/city",
                                    "operator": "present",
                                    "effect": "require",
                                }
                            ],
                        }
                    },
                    localization={
                        "default_locale": "en",
                        "supported_locales": ["en", "fa"],
                        "required_locales": ["en", "fa"],
                        "catalogs": {"en": {"city": {"text": "City"}}},
                    },
                ),
                actor,
            )
            explanation = await DefinitionLibraryService(session).explanation(
                create_ref_id(version.id, version.version)
            )
            assert any(
                issue["code"] == "localization.missing" and "/fa/city" in issue["pointer"]
                for issue in explanation.localization_issues
            )
            assert explanation.rules[0].effect == "require"
            assert explanation.rules[0].source_scope == "/properties/city"
            assert "Tehran" not in explanation.model_dump_json()
            await session.rollback()
    finally:
        await engine.dispose()
