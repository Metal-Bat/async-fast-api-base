"""Tests for the consolidated initial schema revision."""

import importlib.util
from io import StringIO
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from utils.security import verify_password


def load_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[3]
        / "src/migrations/versions/b13a0c7d2e44_initial_schema.py"
    )
    spec = importlib.util.spec_from_file_location("initial_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.anyio
async def test_initial_admin_uses_local_environment_credentials(monkeypatch) -> None:
    migration = load_migration()
    bulk_insert = Mock()
    monkeypatch.setattr(migration.op, "bulk_insert", bulk_insert)
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "admin")

    migration._create_initial_admin()

    row = bulk_insert.call_args.args[1][0]
    assert row["USERNAME"] == "admin"
    assert row["IS_SUPERUSER"] is True
    assert await verify_password("admin", row["HASHED_PASSWORD"])


def test_initial_admin_is_optional_but_requires_a_complete_pair(monkeypatch) -> None:
    migration = load_migration()
    bulk_insert = Mock()
    monkeypatch.setattr(migration.op, "bulk_insert", bulk_insert)
    monkeypatch.delenv("INITIAL_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    migration._create_initial_admin()
    bulk_insert.assert_not_called()

    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin")
    with pytest.raises(RuntimeError, match="must be configured together"):
        migration._create_initial_admin()


def test_report_cleanup_schedule_uses_reporting_queue_by_default(monkeypatch) -> None:
    migration = load_migration()
    bulk_insert = Mock()
    monkeypatch.setattr(migration.op, "bulk_insert", bulk_insert)
    monkeypatch.delenv("CELERY_REPORT_QUEUE", raising=False)

    migration._create_report_cleanup_schedule()

    row = bulk_insert.call_args.args[1][0]
    assert row["TASK_NAME"] == "reporting.cleanup_expired"
    assert row["QUEUE"] == "reporting"


def test_initial_schema_is_the_root_revision_and_creates_uuid_idempotency_keys(
    monkeypatch,
) -> None:
    versions = Path(__file__).resolve().parents[3] / "src/migrations/versions"
    assert sorted(path.name for path in versions.glob("*.py")) == [
        "b13a0c7d2e44_initial_schema.py",
        "c24f913ab601_workflow_workspace.py",
    ]

    migration = load_migration()
    created_tables: dict[str, tuple[object, ...]] = {}
    monkeypatch.delenv("INITIAL_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *items, **_kwargs: created_tables.__setitem__(name, items),
    )
    monkeypatch.setattr(migration.op, "create_index", Mock())
    monkeypatch.setattr(migration.op, "bulk_insert", Mock())
    monkeypatch.setattr(migration.op, "get_bind", Mock())
    monkeypatch.setattr(migration.op, "f", lambda value: value)

    assert migration.revision == "b13a0c7d2e44"
    assert migration.down_revision is None
    sql = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": sql, "literal_binds": True},
    )
    with Operations.context(context):
        migration.upgrade()

    assert "AI_AGENT" in created_tables
    assert "PROCESS_INSTANCE" in created_tables
    assert "CREATE TRIGGER" in sql.getvalue()

    key = next(
        item
        for item in created_tables["TASK_IDEMPOTENCY"]
        if isinstance(item, sa.Column) and item.name == "KEY"
    )
    assert isinstance(key.type, sa.Uuid)
