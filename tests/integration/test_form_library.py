"""Reusable form definitions publish exact immutable versions and resolve two instances."""

import os
from uuid import uuid7

import pytest

from apps.forms.application.library import LibraryService
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.forms.domain.library import (
    ComponentDocument,
    ComponentUse,
    LibraryCreate,
    LibraryVersionCreate,
)
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_published_component_resolves_two_pinned_form_instances():
    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"library-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            service = LibraryService(session)
            root = await service.create_definition(
                "component", LibraryCreate(code=f"ADDR{uuid7().hex}", name="Address"), actor
            )
            document = ComponentDocument(
                data_schema={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
                render_schema={
                    "root": {
                        "component": "vertical",
                        "node_key": "address",
                        "children": [
                            {"component": "text", "node_key": "city", "scope": "/properties/city"}
                        ],
                    }
                },
            )
            version = await service.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    document=document.model_dump(),
                ),
                actor,
            )
            published = await service.publish(
                "component", create_ref_id(version.id, version.version), actor
            )
            assert published.status == "PUBLISHED" and bool(published.checksum)
            source = FormDocuments(
                data_schema={
                    "type": "object",
                    "properties": {"billing": {"type": "object"}, "shipping": {"type": "object"}},
                },
                render_schema={
                    "root": {
                        "component": "vertical",
                        "children": [{"component": "vertical"}, {"component": "vertical"}],
                    }
                },
            )
            uses = [
                {
                    "instance_key": "billing",
                    "component_ref": create_ref_id(published.id, published.version),
                    "schema_pointer": "/properties/billing",
                    "node_pointer": "/root/children/0",
                },
                {
                    "instance_key": "shipping",
                    "component_ref": create_ref_id(published.id, published.version),
                    "schema_pointer": "/properties/shipping",
                    "node_pointer": "/root/children/1",
                },
            ]
            stale_use = dict(
                uses[0], component_ref=create_ref_id(published.id, published.version - 1)
            )
            with pytest.raises(VersionConflictException):
                await service.resolve_form(source, [stale_use], actor)
            resolved, manifest = await service.resolve_form(source, uses, actor)
            assert resolved.data_schema["properties"]["billing"]["required"] == ["city"]
            assert (
                resolved.render_schema["root"]["children"][1]["children"][0]["scope"]
                == "/properties/shipping/properties/city"
            )
            assert len(manifest) == 1 and manifest[0]["checksum"] == published.checksum
            copied = await service.copy_template(
                source, ComponentUse.model_validate(uses[0]), actor
            )
            assert copied.reuse_instances is None
            assert copied.data_schema["properties"]["billing"]["required"] == ["city"]
            assert copied.render_schema["root"]["children"][1] == {"component": "vertical"}
            form_service = FormService(session)
            form_root = await form_service.create(
                FormCreateDTO(code=f"REUSE{uuid7().hex}", name="Addresses"), actor.id
            )
            draft = await form_service.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(form_root.id, form_root.version),
                    number=1,
                    **source.model_dump(exclude_none=True),
                    reuse_instances=uses,
                ),
                actor,
            )
            form_version = await form_service.publish(
                create_ref_id(draft.id, draft.version), actor.id
            )
            assert (
                form_version.render_schema["root"]["children"][0]["children"][0]["scope"]
                == "/properties/billing/properties/city"
            )
            assert form_version.reuse_manifest is not None
            assert form_version.reuse_manifest[0]["checksum"] == published.checksum
            await service.retire("component", create_ref_id(published.id, published.version), actor)
            with pytest.raises(VersionConflictException):
                await service.resolve_form(source, uses, actor)
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_component_grant_is_required_and_revocation_closes_new_use():
    from apps.forms.domain.library import LibraryGrantCreate
    from utils.exceptions import NotFoundException

    try:
        async with SessionFactory() as session:
            owner = UserEntity(username=f"owner-{uuid7().hex}", hashed_password="hash")
            consumer = UserEntity(username=f"consumer-{uuid7().hex}", hashed_password="hash")
            session.add_all([owner, consumer])
            await session.flush()
            service = LibraryService(session)
            root = await service.create_definition(
                "component", LibraryCreate(code=f"GRANT{uuid7().hex}", name="Private"), owner
            )
            row = await service.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    document=ComponentDocument(
                        data_schema={"type": "object", "properties": {}},
                        render_schema={"root": {"component": "vertical"}},
                    ).model_dump(),
                ),
                owner,
            )
            row = await service.publish("component", create_ref_id(row.id, row.version), owner)
            with pytest.raises(NotFoundException):
                await service.version("component", create_ref_id(row.id, row.version), consumer)
            grant = await service.grant(
                "component",
                create_ref_id(root.id, root.version),
                LibraryGrantCreate(user_ref_id=create_ref_id(consumer.id, consumer.version)),
                owner,
            )
            assert await service.version("component", create_ref_id(row.id, row.version), consumer)
            await service.revoke_grant(create_ref_id(grant.id, grant.version), owner)
            with pytest.raises(NotFoundException):
                await service.version("component", create_ref_id(row.id, row.version), consumer)
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_nested_type_dependency_stays_pinned_when_new_type_version_is_published():
    from apps.forms.domain.library import TypeDocument

    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"typed-library-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            service = LibraryService(session)
            type_root = await service.create_definition(
                "data_type", LibraryCreate(code=f"CITY{uuid7().hex}", name="City"), actor
            )
            type_doc = TypeDocument(data_schema={"type": "string", "minLength": 2})
            first = await service.create_version(
                "data_type",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(type_root.id, type_root.version),
                    number=1,
                    document=type_doc.model_dump(),
                ),
                actor,
            )
            first = await service.publish(
                "data_type", create_ref_id(first.id, first.version), actor
            )
            component_root = await service.create_definition(
                "component", LibraryCreate(code=f"TYPED{uuid7().hex}", name="Typed address"), actor
            )
            doc = ComponentDocument(
                data_schema={"type": "object", "properties": {"city": {"type": "string"}}},
                render_schema={"root": {"component": "text", "scope": "/properties/city"}},
                types=[
                    {
                        "schema_pointer": "/properties/city",
                        "version_ref": create_ref_id(first.id, first.version),
                    }
                ],
            )
            version = await service.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(component_root.id, component_root.version),
                    number=1,
                    document=doc.model_dump(),
                ),
                actor,
            )
            version = await service.publish(
                "component", create_ref_id(version.id, version.version), actor
            )
            original_checksum = version.checksum
            assert version.resolved is not None
            assert version.resolved["data_schema"]["properties"]["city"]["minLength"] == 2
            second = await service.create_version(
                "data_type",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(type_root.id, type_root.version),
                    number=2,
                    document=TypeDocument(
                        data_schema={"type": "string", "minLength": 5}
                    ).model_dump(),
                ),
                actor,
            )
            await service.publish("data_type", create_ref_id(second.id, second.version), actor)
            await session.refresh(version)
            assert version.checksum == original_checksum
            assert version.dependencies[0]["checksum"] == first.checksum
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_published_component_snapshot_is_database_immutable():
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"immutable-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            service = LibraryService(session)
            root = await service.create_definition(
                "component", LibraryCreate(code=f"IMM{uuid7().hex}", name="Immutable"), actor
            )
            row = await service.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    document=ComponentDocument(
                        data_schema={"type": "object"},
                        render_schema={"root": {"component": "vertical"}},
                    ).model_dump(),
                ),
                actor,
            )
            published = await service.publish(
                "component", create_ref_id(row.id, row.version), actor
            )
            await session.commit()
            identifier = published.id
        async with SessionFactory() as session:
            with pytest.raises(DBAPIError, match="immutable"):
                await (await session.connection()).execute(
                    text(
                        'UPDATE "FORM_COMPONENT_VERSION" SET "DOCUMENT" = :value WHERE "ID" = :id'
                    ),
                    {"value": "{}", "id": identifier},
                )
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_bilingual_component_publication_pins_instance_catalogs():
    try:
        async with SessionFactory() as session:
            actor = UserEntity(
                username=f"localized-component-{uuid7().hex}", hashed_password="hash"
            )
            session.add(actor)
            await session.flush()
            service = LibraryService(session)
            root = await service.create_definition(
                "component", LibraryCreate(code=f"LOCAL{uuid7().hex}", name="Localized"), actor
            )
            document = ComponentDocument(
                data_schema={"type": "object", "properties": {"city": {"type": "string"}}},
                render_schema={
                    "root": {
                        "component": "text",
                        "scope": "/properties/city",
                        "messages": {"label": {"key": "city"}},
                    }
                },
                messages={"en": {"city": "City"}, "fa": {"city": "شهر"}},
            )
            version = await service.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    document=document.model_dump(),
                ),
                actor,
            )
            version = await service.publish(
                "component", create_ref_id(version.id, version.version), actor
            )
            source = FormDocuments(
                data_schema={"type": "object", "properties": {"billing": {"type": "object"}}},
                render_schema={
                    "root": {"component": "vertical", "children": [{"component": "vertical"}]}
                },
            )
            resolved, _ = await service.resolve_form(
                source,
                [
                    {
                        "instance_key": "billing",
                        "component_ref": create_ref_id(version.id, version.version),
                        "schema_pointer": "/properties/billing",
                        "node_pointer": "/root/children/0",
                    }
                ],
                actor,
            )
            assert resolved.localization is not None
            assert resolved.localization.catalogs["fa"]["component.billing.city"].text == "شهر"
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_draft_upgrade_preview_reports_schema_incompatibility_without_writing():
    from apps.forms.domain.library import ComponentUpgradePreviewRequest

    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"upgrade-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            library = LibraryService(session)
            root = await library.create_definition(
                "component", LibraryCreate(code=f"UP{uuid7().hex}", name="Upgradable"), actor
            )
            ref = create_ref_id(root.id, root.version)
            base = ComponentDocument(
                data_schema={"type": "object", "properties": {"city": {"type": "string"}}},
                render_schema={"root": {"component": "text", "scope": "/properties/city"}},
            )
            first = await library.create_version(
                "component",
                LibraryVersionCreate(root_ref_id=ref, number=1, document=base.model_dump()),
                actor,
            )
            first = await library.publish(
                "component", create_ref_id(first.id, first.version), actor
            )
            forms = FormService(session)
            form_root = await forms.create(
                FormCreateDTO(code=f"USE{uuid7().hex}", name="Use"), actor.id
            )
            authored = FormVersionCreateDTO(
                form_ref_id=create_ref_id(form_root.id, form_root.version),
                number=1,
                data_schema={"type": "object", "properties": {"address": {"type": "object"}}},
                render_schema={
                    "root": {"component": "vertical", "children": [{"component": "vertical"}]}
                },
                reuse_instances=[
                    {
                        "instance_key": "address",
                        "component_ref": create_ref_id(first.id, first.version),
                        "schema_pointer": "/properties/address",
                        "node_pointer": "/root/children/0",
                    }
                ],
            )
            draft = await forms.create_version(authored, actor)
            changed = base.model_copy(deep=True)
            changed.data_schema["required"] = ["city"]
            second = await library.create_version(
                "component",
                LibraryVersionCreate(root_ref_id=ref, number=2, document=changed.model_dump()),
                actor,
            )
            second = await library.publish(
                "component", create_ref_id(second.id, second.version), actor
            )
            old_checksum = draft.checksum
            preview = await library.preview_form_upgrade(
                create_ref_id(draft.id, draft.version),
                ComponentUpgradePreviewRequest(
                    replacements={"address": create_ref_id(second.id, second.version)}
                ),
                actor,
            )
            assert not preview.compatible and preview.issues[0].code == "reuse.incompatible_schema"
            assert preview.manifest[0]["checksum"] == second.checksum
            assert draft.reuse_instances is not None
            assert draft.checksum == old_checksum and draft.reuse_instances[0][
                "component_ref"
            ] == create_ref_id(first.id, first.version)
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_publication_has_one_winner_and_immutable_snapshot():
    import asyncio

    async with SessionFactory() as session:
        actor = UserEntity(username=f"race-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        service = LibraryService(session)
        root = await service.create_definition(
            "data_type", LibraryCreate(code=f"RACE{uuid7().hex}", name="Race"), actor
        )
        version = await service.create_version(
            "data_type",
            LibraryVersionCreate(
                root_ref_id=create_ref_id(root.id, root.version),
                number=1,
                document={"dialect": "bpms.data-type/1", "data_schema": {"type": "string"}},
            ),
            actor,
        )
        original = create_ref_id(version.id, version.version)
        actor_id = actor.id
        await session.commit()

    async def publish_once():
        async with SessionFactory() as session:
            actor = await session.get(UserEntity, actor_id)
            assert actor is not None
            row = await LibraryService(session).publish("data_type", original, actor)
            await session.commit()
            return row.checksum

    results = await asyncio.gather(publish_once(), publish_once(), return_exceptions=True)
    assert len([item for item in results if isinstance(item, str)]) == 1
    assert len([item for item in results if isinstance(item, VersionConflictException)]) == 1
    async with SessionFactory() as session:
        from apps.forms.domain.library_entity import DataTypeVersionEntity

        row = await session.get(DataTypeVersionEntity, version.id)
        assert (
            row is not None
            and row.status == "PUBLISHED"
            and row.checksum == next(item for item in results if isinstance(item, str))
        )
    await engine.dispose()


@pytest.mark.anyio
async def test_work_group_grant_tracks_current_membership():
    from apps.forms.domain.library import LibraryGrantCreate
    from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
    from utils.date_utils import get_datetime_utc

    try:
        async with SessionFactory() as session:
            owner = UserEntity(username=f"owner-{uuid7().hex}", hashed_password="hash")
            member = UserEntity(username=f"member-{uuid7().hex}", hashed_password="hash")
            group = WorkGroupEntity(code=f"GROUP{uuid7().hex}", name="Shared")
            session.add_all([owner, member, group])
            await session.flush()
            membership = WorkGroupMemberEntity(work_group_id=group.id, user_id=member.id)
            session.add(membership)
            await session.flush()
            service = LibraryService(session)
            root = await service.create_definition(
                "data_type", LibraryCreate(code=f"GT{uuid7().hex}", name="Granted"), owner
            )
            await service.grant(
                "data_type",
                create_ref_id(root.id, root.version),
                LibraryGrantCreate(work_group_ref_id=create_ref_id(group.id, group.version)),
                owner,
            )
            assert (
                await service.definition("data_type", create_ref_id(root.id, root.version), member)
            ).id == root.id
            membership.is_active = False
            membership.left_at = get_datetime_utc()
            await session.flush()
            with pytest.raises(NotFoundException):
                await service.definition("data_type", create_ref_id(root.id, root.version), member)
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_nested_published_component_pins_transitive_version():
    from apps.forms.domain.library import ComponentUse

    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"nested-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            service = LibraryService(session)
            inner_root = await service.create_definition(
                "component", LibraryCreate(code=f"INNER{uuid7().hex}", name="Inner"), actor
            )
            inner = await service.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(inner_root.id, inner_root.version),
                    number=1,
                    document=ComponentDocument(
                        data_schema={"type": "object", "properties": {"city": {"type": "string"}}},
                        render_schema={"root": {"component": "text", "scope": "/properties/city"}},
                    ).model_dump(),
                ),
                actor,
            )
            inner = await service.publish(
                "component", create_ref_id(inner.id, inner.version), actor
            )
            outer_root = await service.create_definition(
                "component", LibraryCreate(code=f"OUTER{uuid7().hex}", name="Outer"), actor
            )
            outer_doc = ComponentDocument(
                data_schema={"type": "object", "properties": {"inside": {"type": "object"}}},
                render_schema={
                    "root": {"component": "vertical", "children": [{"component": "vertical"}]}
                },
                components=[
                    ComponentUse(
                        instance_key="inside",
                        component_ref=create_ref_id(inner.id, inner.version),
                        schema_pointer="/properties/inside",
                        node_pointer="/root/children/0",
                    )
                ],
            )
            outer = await service.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(outer_root.id, outer_root.version),
                    number=1,
                    document=outer_doc.model_dump(),
                ),
                actor,
            )
            outer = await service.publish(
                "component", create_ref_id(outer.id, outer.version), actor
            )
            source = FormDocuments(
                data_schema={"type": "object", "properties": {"billing": {"type": "object"}}},
                render_schema={
                    "root": {"component": "vertical", "children": [{"component": "vertical"}]}
                },
            )
            resolved, manifest = await service.resolve_form(
                source,
                [
                    {
                        "instance_key": "billing",
                        "component_ref": create_ref_id(outer.id, outer.version),
                        "schema_pointer": "/properties/billing",
                        "node_pointer": "/root/children/0",
                    }
                ],
                actor,
            )
            assert (
                resolved.render_schema["root"]["children"][0]["children"][0]["scope"]
                == "/properties/billing/properties/inside/properties/city"
            )
            assert {item["checksum"] for item in manifest} == {inner.checksum, outer.checksum}
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_component_publication_rejects_undeclared_customization_interface():
    try:
        async with SessionFactory() as session:
            actor = UserEntity(username=f"interface-{uuid7().hex}", hashed_password="hash")
            session.add(actor)
            await session.flush()
            service = LibraryService(session)
            root = await service.create_definition(
                "component", LibraryCreate(code=f"IF{uuid7().hex}", name="Interface"), actor
            )
            doc = ComponentDocument(
                data_schema={"type": "object"},
                render_schema={"root": {"component": "vertical"}},
                overridable_messages=["missing"],
            )
            row = await service.create_version(
                "component",
                LibraryVersionCreate(
                    root_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    document=doc.model_dump(),
                ),
                actor,
            )
            with pytest.raises(ValidationDetailsException):
                await service.publish("component", create_ref_id(row.id, row.version), actor)
            assert row.status == "DRAFT" and row.checksum is None
            await session.rollback()
    finally:
        await engine.dispose()
