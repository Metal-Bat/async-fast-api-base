"""PostgreSQL execution of BPMS operational aggregate queries."""

import os

import pytest

from apps.processes.application.operations import collect_operational_snapshot
from core.deps import SessionFactory, engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_empty_runtime_has_a_zero_operational_snapshot() -> None:
    async with SessionFactory() as session:
        snapshot = await collect_operational_snapshot(session)

    assert snapshot.cartable_backlog == {}
    assert snapshot.wait_oldest_age_seconds == {}
    assert snapshot.outbox_pending == 0
    assert snapshot.outbox_oldest_age_seconds == 0.0
    assert snapshot.compensation_backlog == {}
    await engine.dispose()
