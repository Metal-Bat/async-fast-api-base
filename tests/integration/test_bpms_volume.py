"""Measured operational queries over a hot process and a mostly-published outbox."""

import json
import os
from pathlib import Path
from uuid import uuid7

import pytest
from sqlalchemy import text
from sqlmodel import select

from apps.processes.domain.entity import ProcessEventEntity
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from tests.integration.test_processes import _start_waiting_process

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_BPMS_VOLUME") != "1", reason="loads disposable PostgreSQL volume fixtures"
    ),
]


@pytest.mark.anyio
async def test_operational_queries_remain_bounded_at_volume(tmp_path) -> None:
    plans = {}
    async with SessionFactory() as session:
        owner = UserEntity(
            username=f"volume-{uuid7()}", hashed_password="unused", is_superuser=True
        )
        session.add(owner)
        await session.flush()
        process, _ = await _start_waiting_process(session, owner, "TIMER")
        sequence = process.event_sequence
        connection = await session.connection()
        await connection.execute(
            text("""
            INSERT INTO "PROCESS_EVENT" ("PROCESS_INSTANCE_ID", "BUSINESS_REQUEST_ID", "SEQUENCE", "EVENT_TYPE", "PUBLIC_PAYLOAD", "OCCURRED_AT")
            SELECT :process, :request, :sequence + i, 'step.started', '{"status":"RUNNING"}'::jsonb,
                   now() - i * interval '1 second' FROM generate_series(1, 25000) AS i
        """),
            {"process": process.id, "request": process.business_request_id, "sequence": sequence},
        )
        await connection.execute(
            text("""
            INSERT INTO "TASK_OUTBOX" ("TASK_ID", "TASK_NAME", "QUEUE", "ARGS", "KWARGS", "HEADERS", "PRIORITY", "AVAILABLE_AT", "PUBLISHED_AT", "ATTEMPTS", "VERSION", "CREATED_AT", "UPDATED_AT")
            SELECT uuidv7()::text, 'system.ping', 'volume', '[]'::json, '{}'::json, '{}'::json, 0,
                   now() - interval '1 day', CASE WHEN i <= 100 THEN NULL ELSE now() END, 0, 1, now(), now()
            FROM generate_series(1, 50000) AS i
        """)
        )
        await connection.execute(
            text("""
            INSERT INTO "USER_HISTORY" ("ENTITY_ID", "MODIFIER_TYPE", "MODIFIER_ID", "CHANGED_AT", "OPERATION")
            SELECT :owner, 'system', 'volume', now() - i * interval '1 second', 'update'
            FROM generate_series(1, 25000) AS i
        """),
            {"owner": owner.id},
        )
        for table in ("PROCESS_EVENT", "TASK_OUTBOX", "USER_HISTORY"):
            # Fixed code-owned table names; no request input reaches this statement.
            await connection.execute(text('ANALYZE "' + table + '"'))
        queries = {
            "process_events": (
                'SELECT * FROM "PROCESS_EVENT" WHERE "PROCESS_INSTANCE_ID" = :id ORDER BY "SEQUENCE" DESC LIMIT 100',
                process.id,
            ),
            "audit": (
                'SELECT * FROM "USER_HISTORY" WHERE "ENTITY_ID" = :id ORDER BY "CHANGED_AT" DESC, "ID" DESC LIMIT 100',
                owner.id,
            ),
            "outbox": (
                'SELECT * FROM "TASK_OUTBOX" WHERE "PUBLISHED_AT" IS NULL AND "AVAILABLE_AT" <= now() ORDER BY "AVAILABLE_AT", "ID" LIMIT 1 FOR UPDATE SKIP LOCKED',
                None,
            ),
        }
        for label, (query, identifier) in queries.items():
            plan = (
                await connection.execute(
                    text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query),
                    {"id": identifier} if identifier else {},
                )
            ).scalar_one()[0]
            plans[label] = plan
            assert plan["Plan"]["Actual Rows"] <= (1 if label == "outbox" else 100)
            assert plan["Execution Time"] < 1000
        assert (
            len(
                (
                    await session.exec(
                        select(ProcessEventEntity)
                        .where(ProcessEventEntity.process_instance_id == process.id)
                        .limit(100)
                    )
                ).all()
            )
            == 100
        )
        await session.rollback()
    await engine.dispose()
    output = Path(os.getenv("BPMS_PLAN_OUTPUT", str(tmp_path / "plans.json")))
    output.write_text(json.dumps(plans, indent=2) + "\n")
    print(
        {
            name: {"execution_ms": plan["Execution Time"], "rows": plan["Plan"]["Actual Rows"]}
            for name, plan in plans.items()
        }
    )
