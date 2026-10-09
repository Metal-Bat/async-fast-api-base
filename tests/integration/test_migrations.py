"""Integration tests for Alembic migration round trips."""

import os
import re
import subprocess

import anyio
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_MIGRATION_INTEGRATION") != "1",
        reason="uses the configured disposable integration database",
    ),
]


def require_disposable_database() -> None:
    """Refuse destructive tests unless the runner names its exact owned database."""
    name = os.getenv("POSTGRES_DB", "")
    if (
        re.fullmatch(r"bpms_flow_[0-9a-f]{32}", name) is None
        or os.getenv("FLOW_TEST_OWNED_DATABASE") != name
        or os.getenv("POSTGRES_HOST", "localhost") not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise RuntimeError("Migration acceptance requires an owned disposable local database")


def test_alembic_empty_upgrade_downgrade_upgrade_round_trip() -> None:
    """Build, remove, and rebuild the schema in a disposable configured database."""
    require_disposable_database()
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    subprocess.run(["alembic", "downgrade", "base"], check=True)
    subprocess.run(["alembic", "upgrade", "head"], check=True)


@pytest.mark.anyio
async def test_schema_revision_has_no_rows_and_data_revision_installs_required_catalogs():
    """Schema is empty; data installs immutable handlers, permissions and schedules once."""
    from sqlalchemy import text

    from apps.step_types.application.registry import get_registry
    from apps.step_types.application.service import StepTypeService
    from apps.users.application.permission_catalog import PERMISSIONS
    from core.deps import SessionFactory, engine

    require_disposable_database()
    await engine.dispose()
    await anyio.run_process(["alembic", "downgrade", "base"])
    await anyio.run_process(["alembic", "upgrade", "0001_schema"])
    async with engine.connect() as connection:
        tables = (
            (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert "WORKFLOW_RESTORE" in tables and "CALENDAR_EVENT" in tables
        for table in tables:
            assert (
                await connection.execute(text(f'SELECT count(*) FROM "{table}"'))
            ).scalar_one() == 0
    async with engine.begin() as connection:
        custom_id = (
            await connection.execute(
                text(
                    'INSERT INTO "STEP_TYPE" ("CODE", "NAME", "IS_ENABLED", "VERSION", "CREATED_AT") VALUES (\'CUSTOM_DRAFT\', \'Retained draft\', true, 1, now()) RETURNING "ID"'
                )
            )
        ).scalar_one()
        draft_id = (
            await connection.execute(
                text(
                    'INSERT INTO "STEP_TYPE_VERSION" ("STEP_TYPE_ID", "NUMBER", "STATUS", "HANDLER_KEY", "HANDLER_VERSION", "EXECUTION_MODE", "CONFIG_SCHEMA", "VERSION", "CREATED_AT") VALUES (:root, 1, \'DRAFT\', \'custom_draft\', \'1\', \'SYNC\', \'{}\'::jsonb, 1, now()) RETURNING "ID"'
                ),
                {"root": custom_id},
            )
        ).scalar_one()
    await engine.dispose()
    await anyio.run_process(["alembic", "upgrade", "head"])
    async with engine.connect() as connection:
        assert (
            await connection.execute(
                text('SELECT "STATUS" FROM "STEP_TYPE_VERSION" WHERE "ID" = :draft'),
                {"draft": draft_id},
            )
        ).scalar_one() == "DRAFT"
        names = set((await connection.execute(text('SELECT "NAME" FROM "PERMISSION"'))).scalars())
        assert names == set(PERMISSIONS)
        assert (
            await connection.execute(text('SELECT count(*) FROM "USER_ROLE"'))
        ).scalar_one() == 0
        assert (await connection.execute(text('SELECT count(*) FROM "ROLE"'))).scalar_one() == 0
        handlers = set(
            (
                await connection.execute(
                    text(
                        'SELECT "HANDLER_KEY", "HANDLER_VERSION" FROM "STEP_TYPE_VERSION" WHERE "STATUS" = \'PUBLISHED\''
                    )
                )
            ).all()
        )
        assert {
            ("transform", "1"),
            ("transform", "2"),
            ("notification", "1"),
            ("notification", "2"),
            ("subprocess", "1"),
            ("event_wait", "1"),
            ("timer", "1"),
        } <= handlers
        assert {
            (item.handler_key, item.handler_version) for item in get_registry().definitions()
        } <= handlers
        schedule_count = (
            await connection.execute(text('SELECT count(*) FROM "PERIODIC_TASK"'))
        ).scalar_one()
        assert schedule_count == 2
    await engine.dispose()
    await anyio.run_process(["alembic", "upgrade", "head"])
    async with engine.connect() as connection:
        assert (
            await connection.execute(text('SELECT count(*) FROM "PERIODIC_TASK"'))
        ).scalar_one() == schedule_count
    await engine.dispose()
    async with SessionFactory() as session:
        catalog = await StepTypeService(session, get_registry()).catalog()
        deployed_codes = {
            "AI_DECISION",
            "CONNECTION_STATUS",
            "PERMISSION_CHECK",
            "REQUEST_PRIORITY",
        }
        deployed = [item for item in catalog if item.code in deployed_codes]
        assert {item.code for item in deployed} == deployed_codes
        assert all(item.is_available for item in deployed)
    await engine.dispose()
    refusal = await anyio.run_process(["alembic", "downgrade", "0001_schema"], check=False)
    assert refusal.returncode != 0
    assert b"Required data cannot be downgraded independently" in refusal.stderr
    async with engine.connect() as connection:
        assert (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one() == "0002_required_data"
        assert (
            await connection.execute(text('SELECT count(*) FROM "PERIODIC_TASK"'))
        ).scalar_one() == schedule_count
    await engine.dispose()


@pytest.mark.anyio
async def test_legacy_revision_is_rejected_without_replaying_schema():
    """Unknown legacy markers fail closed and leave existing application rows untouched."""
    from sqlalchemy import text

    from core.deps import engine

    require_disposable_database()
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE alembic_version SET version_num = 'k026_workflow_restore'")
        )
        count = (
            await connection.execute(text('SELECT count(*) FROM "STEP_TYPE_VERSION"'))
        ).scalar_one()
    await engine.dispose()
    try:
        refusal = await anyio.run_process(["alembic", "upgrade", "head"], check=False)
        assert refusal.returncode != 0
        assert b"Can't locate revision identified by" in refusal.stderr + refusal.stdout
        async with engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one() == "k026_workflow_restore"
            assert (
                await connection.execute(text('SELECT count(*) FROM "STEP_TYPE_VERSION"'))
            ).scalar_one() == count
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE alembic_version SET version_num = '0002_required_data'")
            )
        await engine.dispose()


@pytest.mark.anyio
async def test_populated_initial_head_upgrade_preserves_pins_media_and_history():
    """Install required data without changing existing pins, media or histories."""
    from hashlib import sha256
    from uuid import uuid7

    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import text

    from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
    from apps.media.domain.entity import UserUploadEntity
    from apps.requests.domain.entity import (
        BusinessRequestEntity,
        FormSubmissionEntity,
        RequestTypeEntity,
    )
    from apps.users.domain.entity import UserEntity
    from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
    from core.deps import SessionFactory, engine
    from utils.date_utils import get_datetime_utc

    require_disposable_database()
    await engine.dispose()
    await anyio.run_process(["alembic", "downgrade", "base"])
    revisions = ScriptDirectory.from_config(Config(toml_file="pyproject.toml"))
    initial = next(
        revision.revision
        for revision in revisions.walk_revisions()
        if revision.down_revision is None
    )
    await anyio.run_process(["alembic", "upgrade", initial])
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(username=f"migration-{token}", hashed_password="synthetic-hash")
            session.add(actor)
            await session.flush()
            form = FormDefinitionEntity(
                code=f"MF{token}", name="Retained form", owner_user_id=actor.id
            )
            workflow = WorkflowDefinitionEntity(
                code=f"MW{token}", name="Retained workflow", owner_user_id=actor.id
            )
            session.add_all([form, workflow])
            await session.flush()
            checksum = sha256(b"legacy migration preservation fixture").hexdigest()
            published_at = get_datetime_utc()
            form_version = FormVersionEntity(
                form_definition_id=form.id,
                number=1,
                data_dialect="https://json-schema.org/draft/2020-12/schema",
                render_dialect="bpms.render/1",
                data_schema={"type": "object"},
                render_schema={
                    "dialect": "bpms.render/1",
                    "root": {"component": "vertical", "children": []},
                },
            )
            version = WorkflowVersionEntity(
                workflow_definition_id=workflow.id,
                number=1,
            )
            request_type = RequestTypeEntity(
                code=f"MR{token}",
                name="Retained type",
                workflow_definition_id=workflow.id,
                form_definition_id=form.id,
            )
            session.add_all([form_version, version, request_type])
            await session.flush()
            form_version.status = version.status = "PUBLISHED"
            form_version.checksum = version.graph_checksum = checksum
            form_version.published_at = version.published_at = published_at
            form_version.published_by_user_id = version.published_by_user_id = actor.id
            await session.flush()
            request = BusinessRequestEntity(
                request_type_id=request_type.id,
                requester_user_id=actor.id,
                workflow_version_id=version.id,
                priority=0,
            )
            session.add(request)
            await session.flush()
            submission = FormSubmissionEntity(
                business_request_id=request.id,
                form_version_id=form_version.id,
                data={"amount": "12"},
            )
            session.add(submission)
            await session.flush()
            submission_id = submission.id
            media = UserUploadEntity(
                user_id=actor.id,
                kind="file",
                object_key=f"migration-fixture/{request.id}",
                original_filename="synthetic.txt",
                content_type="text/plain",
                size_bytes=1,
                sha256="a" * 64,
            )
            session.add(media)
            await session.flush()
            request_id, media_id = request.id, media.id
            pins = (request.workflow_version_id, submission.form_version_id)
            version = await session.get(WorkflowVersionEntity, pins[0])
            assert version is not None and version.status == "PUBLISHED"
            checksum = version.graph_checksum
            history_before = (
                await (await session.connection()).execute(
                    text("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal")
                )
            ).scalar_one()
        await engine.dispose()
        await anyio.run_process(["alembic", "upgrade", "head"])
        async with SessionFactory() as session:
            retained = await session.get(BusinessRequestEntity, request_id)
            assert retained is not None and retained.workflow_version_id == pins[0]
            retained_submission = await session.get(FormSubmissionEntity, submission_id)
            assert (
                retained_submission is not None and retained_submission.form_version_id == pins[1]
            )
            assert retained_submission.data == {"amount": "12"}
            retained_media = await session.get(UserUploadEntity, media_id)
            assert retained_media is not None and retained_media.user_id == actor.id
            retained_version = await session.get(WorkflowVersionEntity, pins[0])
            assert retained_version is not None and retained_version.graph_checksum == checksum
            history_after = (
                await (await session.connection()).execute(
                    text("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal")
                )
            ).scalar_one()
            assert history_after >= history_before
            head = (
                await (await session.connection()).execute(
                    text("SELECT version_num FROM alembic_version")
                )
            ).scalar_one()
            assert head == revisions.get_current_head()
            workspace = (
                await (await session.connection()).execute(
                    text("SELECT to_regclass('\"WORKFLOW_WORKSPACE\"')")
                )
            ).scalar_one()
            assert workspace is not None
        drift = await anyio.run_process(["alembic", "check"], check=False)
        assert drift.returncode == 0, (drift.stdout + drift.stderr).decode()
    finally:
        await engine.dispose()
