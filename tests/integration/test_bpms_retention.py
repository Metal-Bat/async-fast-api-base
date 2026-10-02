"""Retention preserves active and BPMS-owned operational records."""

import os
from datetime import timedelta
from uuid import uuid7

import pytest
from sqlmodel import col, select

from apps.tasks.application.retention import cleanup_operational_history
from apps.tasks.domain.entity import TaskExecutionEntity, TaskOutboxEntity
from core.deps import SessionFactory, engine
from utils.date_utils import get_datetime_utc

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_retention_only_removes_old_terminal_unreferenced_work() -> None:
    now = get_datetime_utc()
    old = now - timedelta(days=400)
    async with SessionFactory() as session:
        rows = []
        for name, status, finished in [
            ("system.ping", "SUCCESS", old),
            ("system.ping", "STARTED", None),
            ("system.ping", "RETRY", None),
            ("bpms.execute_background", "SUCCESS", old),
            ("system.ping", "SUCCESS", now),
        ]:
            row = TaskExecutionEntity(
                task_id=str(uuid7()),
                task_name=name,
                status=status,
                created_at=old,
                finished_at=finished,
            )
            session.add(row)
            rows.append(row)
        await session.commit()
        identifiers = [row.id for row in rows]
        await cleanup_operational_history(session, now=now, limit=1)
        await session.commit()
        assert await session.get(TaskExecutionEntity, identifiers[0]) is None
        for key in identifiers[1:]:
            assert await session.get(TaskExecutionEntity, key) is not None
        outbox = TaskOutboxEntity(
            task_id=str(uuid7()),
            task_name="bpms.execute_background",
            queue="automation",
            available_at=old,
            published_at=old,
        )
        session.add(outbox)
        await session.commit()
        await cleanup_operational_history(session, now=now)
        await session.commit()
        assert (
            await session.exec(select(TaskOutboxEntity).where(TaskOutboxEntity.id == outbox.id))
        ).one()
    await engine.dispose()


@pytest.mark.anyio
async def test_application_sql_logging_never_emits_bound_business_values(caplog) -> None:
    import logging

    from sqlalchemy import text

    secret = "private-bpms-value-" + uuid7().hex
    with caplog.at_level(logging.INFO, logger="sqlalchemy.engine.Engine"):
        async with engine.connect() as connection:
            value = (
                await connection.execute(text("SELECT CAST(:value AS text)"), {"value": secret})
            ).scalar_one()
            assert value == secret
    assert secret not in caplog.text
    await engine.dispose()


@pytest.mark.anyio
async def test_retention_preserves_referenced_execution_and_old_configuration_audit() -> None:
    from apps.processes.domain.entity import StepExecutionAttemptEntity, StepExecutionEntity
    from apps.users.domain.entity import UserEntity
    from core.history import history_tables
    from tests.integration.test_processes import _start_waiting_process

    now = get_datetime_utc()
    old = now - timedelta(days=400)
    async with SessionFactory() as session:
        actor = UserEntity(
            username=f"retention-{uuid7()}", hashed_password="unused", is_superuser=True
        )
        session.add(actor)
        await session.flush()
        process, _ = await _start_waiting_process(session, actor, "TIMER")
        execution = TaskExecutionEntity(
            task_id=str(uuid7()),
            task_name="system.ping",
            status="SUCCESS",
            created_at=old,
            finished_at=old,
        )
        session.add(execution)
        await session.flush()
        attempt = (
            await session.exec(
                select(StepExecutionAttemptEntity)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionAttemptEntity.step_execution_id)
                    == col(StepExecutionEntity.id),
                )
                .where(
                    StepExecutionEntity.process_instance_id == process.id,
                    StepExecutionAttemptEntity.status == "WAITING",
                    col(StepExecutionAttemptEntity.task_execution_id).is_(None),
                )
                .limit(1)
            )
        ).one()
        attempt.task_execution_id = execution.id
        table = history_tables()["user"]
        connection = await session.connection()
        history_id = (
            await connection.execute(
                table.insert()
                .values(
                    ENTITY_ID=actor.id,
                    MODIFIER_TYPE="system",
                    MODIFIER_ID="retention-test",
                    OPERATION="update",
                    CHANGED_AT=old,
                )
                .returning(table.c.ID)
            )
        ).scalar_one()
        await session.commit()
        await cleanup_operational_history(session, now=now)
        await session.commit()
        assert await session.get(TaskExecutionEntity, execution.id) is not None
        connection = await session.connection()
        assert (
            await connection.execute(select(table.c.ID).where(table.c.ID == history_id))
        ).scalar_one() == history_id
    await engine.dispose()
