"""PostgreSQL catalog lifecycle, constraints, and immutability."""

import asyncio
import os
from typing import override
from uuid import uuid7

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlmodel import select

from apps.step_types.application.invocation import StepResult
from apps.step_types.application.registry import (
    EmptyConfig,
    StepDefinition,
    build_registry,
    builtin_registry,
    step_definition,
)
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.dto import StepTypeQuery
from apps.step_types.domain.entity import StepTypeEntity, StepTypePortEntity, StepTypeVersionEntity
from core.deps import SessionFactory, engine
from core.i18n import use_language
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_seed_catalog_and_disabled_historical_resolution() -> None:
    async with SessionFactory() as session:
        service = StepTypeService(session, builtin_registry())
        catalog = await service.catalog()
        assert all(item.ref_id and item.number >= 1 for item in catalog)
        assert any(item.code == "TRANSFORM" and item.number == 2 for item in catalog)
        assert {item.code for item in catalog} >= {
            item.code for item in builtin_registry().catalog()
        }
        root = (
            await session.exec(select(StepTypeEntity).where(StepTypeEntity.code == "START"))
        ).one()
        version = (
            await session.exec(
                select(StepTypeVersionEntity).where(StepTypeVersionEntity.step_type_id == root.id)
            )
        ).one()
        root.is_enabled = False
        await session.flush()
        assert await service.resolve_version(version.id, for_new_use=False)
        with pytest.raises(VersionConflictException):
            await service.resolve_version(version.id, for_new_use=True)
        assert "START" not in {item.code for item in await service.catalog()}
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_trusted_class_reconciliation_is_idempotent_and_requires_publication() -> None:
    unique_code = f"EXT_{uuid7().hex}"

    @step_definition
    class Example(StepDefinition):
        code = unique_code
        name = "Example"
        handler_key = unique_code.casefold()
        handler_version = "1"
        category = "ACTION"
        execution_mode = "SYNC"
        config_model = EmptyConfig

        @classmethod
        @override
        async def execute(cls, context, config):
            return StepResult(outputs={})

    registry = build_registry(classes=(Example,))
    async with SessionFactory() as session, session.begin():
        service = StepTypeService(session, registry)
        first = await service.reconcile()
        second = await service.reconcile()
        assert first == second
        example_versions = [row for row in first if row.handler_key == unique_code.casefold()]
        assert len(example_versions) == 1
        assert example_versions[0].status == "DRAFT"
        assert all(item.code != unique_code for item in await service.catalog())
    async with SessionFactory() as session, session.begin():
        service = StepTypeService(session, registry)
        rows = await service.reconcile()
        example = next(row for row in rows if row.handler_key == unique_code.casefold())
        assert example.id == example_versions[0].id
        await service.publish(create_ref_id(example.id, example.version))
        assert unique_code in {item.code for item in await service.catalog()}
        with use_language("fa"):
            localized = await service.detail(create_ref_id(example.id, example.version))
        assert localized.is_available
        historical = await StepTypeService(session, builtin_registry()).catalog()
        assert next(item for item in historical if item.code == unique_code).is_available is False

    @step_definition
    class Changed(StepDefinition):
        code = unique_code
        name = "Example"
        handler_key = unique_code.casefold()
        handler_version = "1"
        category = "ACTION"
        execution_mode = "SYNC"
        config_model = EmptyConfig
        help_key = "changed.help"

        @classmethod
        @override
        async def execute(cls, context, config):
            return StepResult(outputs={})

    async with SessionFactory() as session:
        with pytest.raises(ValueError, match="metadata differs"):
            await StepTypeService(session, build_registry(classes=(Changed,))).reconcile()
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_metadata_tampering_cannot_be_published_and_retirement_preserves_history() -> None:
    async with SessionFactory() as session:
        service = StepTypeService(session, builtin_registry())
        root = await service.create_type(f"CUSTOM_{uuid7().hex}", "Custom")
        draft = await service.create_version(root.id, 1, "start", "1")
        draft.config_schema = {"type": "string"}
        await session.flush()
        with pytest.raises(ValueError, match="metadata differs"):
            await service.publish(create_ref_id(draft.id, draft.version))
        await service.revise_version(create_ref_id(draft.id, draft.version), "start", "1")
        await service.publish(create_ref_id(draft.id, draft.version))
        await service.retire(create_ref_id(draft.id, draft.version))
        assert (await service.resolve_version(draft.id, for_new_use=False)).status == "RETIRED"
        with pytest.raises(VersionConflictException):
            await service.resolve_version(draft.id, for_new_use=True)
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_draft_publication_rejects_stale_updates_and_freezes_ports() -> None:
    async with SessionFactory() as session:
        service = StepTypeService(session, builtin_registry())
        root = await service.create_type(f"CUSTOM_{uuid7().hex}", "Custom")
        draft = await service.create_version(root.id, 1, "human_task", "1")
        stale = create_ref_id(draft.id, draft.version)
        await service.revise_version(stale, "notification", "1")
        with pytest.raises(VersionConflictException):
            await service.publish(stale)
        published = await service.publish(create_ref_id(draft.id, draft.version))
        assert published.status == "PUBLISHED"
        assert published.published_at is not None
        with pytest.raises(VersionConflictException):
            await service.revise_version(create_ref_id(draft.id, draft.version), "start", "1")
        await session.commit()
        version_id = published.id
    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text(
                    'UPDATE "STEP_TYPE_VERSION" SET "CONFIG_SCHEMA" = \'{}\' WHERE "ID" = :id'
                ).bindparams(id=version_id)
            )
        await session.rollback()
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text('DELETE FROM "STEP_TYPE_PORT" WHERE "STEP_TYPE_VERSION_ID" = :id').bindparams(
                    id=version_id
                )
            )
        await session.rollback()
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text('DELETE FROM "STEP_TYPE_VERSION" WHERE "ID" = :id').bindparams(id=version_id)
            )
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_duplicate_ports_and_parent_versions_are_rejected() -> None:
    async with SessionFactory() as session:
        service = StepTypeService(session, builtin_registry())
        root = await service.create_type(f"CUSTOM_{uuid7().hex}", "Custom")
        draft = await service.create_version(root.id, 1, "human_task", "1")
        session.add(
            StepTypePortEntity(
                step_type_version_id=draft.id,
                direction="OUTPUT",
                port_key="outcome",
                value_schema={"type": "string"},
                required=True,
                nullable=False,
                cardinality="SCALAR",
            )
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
        root = await service.create_type(f"CUSTOM_{uuid7().hex}", "Custom")
        await service.create_version(root.id, 1, "start", "1")
        with pytest.raises(IntegrityError):
            await service.create_version(root.id, 1, "finish", "1")
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "statement",
    [
        """UPDATE "STEP_TYPE_PORT" SET "REQUIRED" = false
       WHERE "STEP_TYPE_VERSION_ID" = :id""",
        """INSERT INTO "STEP_TYPE_PORT"
       ("STEP_TYPE_VERSION_ID", "DIRECTION", "PORT_KEY", "VALUE_SCHEMA", "REQUIRED",
        "NULLABLE", "CARDINALITY", "CREATED_AT")
       VALUES (:id, 'INPUT', 'injected', '{}', true, false, 'SCALAR', now())""",
        """UPDATE "STEP_TYPE_VERSION" SET "DELETED_AT" = now() WHERE "ID" = :id""",
        """UPDATE "STEP_TYPE_VERSION" SET "STATUS" = 'DRAFT', "PUBLISHED_AT" = NULL WHERE "ID" = :id""",
    ],
)
async def test_published_contract_rejects_direct_sql_mutations(statement: str) -> None:
    async with SessionFactory() as session:
        version = (
            await session.exec(
                select(StepTypeVersionEntity).where(
                    StepTypeVersionEntity.handler_key == "human_task",
                    StepTypeVersionEntity.status == "PUBLISHED",
                )
            )
        ).first()
        assert version is not None
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(text(statement), {"id": version.id})
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_publication_has_one_winner() -> None:
    from anyio import create_task_group

    async with SessionFactory() as session:
        service = StepTypeService(session, builtin_registry())
        root = await service.create_type(f"RACE_{uuid7().hex}", "Concurrent")
        draft = await service.create_version(root.id, 1, "start", "1")
        ref_id = create_ref_id(draft.id, draft.version)
        await session.commit()

    results = []

    async def publish() -> None:
        async with SessionFactory() as session:
            try:
                await StepTypeService(session, builtin_registry()).publish(ref_id)
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


@pytest.mark.anyio
async def test_registered_catalog_search_filters_and_historical_detail() -> None:
    registry = build_registry()
    async with SessionFactory() as session, session.begin():
        service = StepTypeService(session, registry)
        rows = await service.reconcile()
        priority = next(row for row in rows if row.handler_key == "request_priority")
        if priority.status == "DRAFT":
            await service.publish(create_ref_id(priority.id, priority.version))
        published = await service.search(
            StepTypeQuery(search="REQUEST_PRIORITY", status="PUBLISHED"),
            available_only=True,
        )
        assert published.total == 1
        item = published.items[0]
        assert item.is_available and item.has_outputs
        assert bool(item.help_text) and item.name_key == "step.request_priority.name"
        escaped = await service.search(StepTypeQuery(search="REQUEST%PRIORITY"))
        assert escaped.total == 0
        with use_language("fa"):
            translated = await service.detail(item.ref_id)
        assert translated.name != item.name
        assert translated.help_text != item.help_text
        historical = await StepTypeService(session, builtin_registry()).detail(item.ref_id)
        assert not historical.is_available
        assert historical.help_text == item.help_text
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_registry_reconciliation_creates_one_version() -> None:
    unique_code = f"EXT_{uuid7().hex}"

    @step_definition
    class Concurrent(StepDefinition):
        code = unique_code
        name = "Concurrent"
        handler_key = unique_code.casefold()
        handler_version = "1"
        category = "ACTION"
        execution_mode = "SYNC"
        config_model = EmptyConfig

        @classmethod
        @override
        async def execute(cls, context, config):
            return StepResult(outputs={})

    registry = build_registry(classes=(Concurrent,))

    async def boot() -> str:
        async with SessionFactory() as session, session.begin():
            versions = await StepTypeService(session, registry).reconcile()
            return str(
                next(row.id for row in versions if row.handler_key == unique_code.casefold())
            )

    assert len(set(await asyncio.gather(boot(), boot()))) == 1
    await engine.dispose()
