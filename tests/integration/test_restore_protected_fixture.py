"""Restore an uncertain owned HTTPS order without replaying its external effect."""

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid7

import anyio
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.application.order_recovery import OrderRecoveryService
from apps.processes.application.orders import ProtectedOrderDispatch
from apps.processes.application.service import ProcessService
from apps.processes.domain.dtos.orders import OrderReconciliationDTO
from apps.processes.domain.entity import (
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.tasks.application.outbox import dispatch_outbox
from apps.users.domain.entity import UserEntity
from core.celery_app import celery_app
from core.deps import SessionFactory
from core.history import audit_context
from core.ref_id import create_ref_id
from tests.integration.test_required_human_approval import approve_order, waiting_order
from utils.exceptions import NotAllowedException, VersionConflictException


@dataclass(frozen=True)
class UnknownOrder:
    attempt_id: UUID
    process_ref: str
    command: OrderReconciliationDTO
    operator_id: UUID
    publisher_id: UUID
    orders: int


def order_count() -> int:
    """Read only the already-owned sandbox ledger; do not call create during recovery."""
    path = Path(os.environ["ORDER_SANDBOX_FAULT_FILE"]).parent / "order-sandbox.sqlite3"
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as database:
        row = database.execute("SELECT count(*) FROM orders").fetchone()
        assert row is not None and isinstance(row[0], int)
        return row[0]


async def prepare_unknown_order() -> UnknownOrder:
    """Wait for a real worker's accepted effect with its acknowledgment deliberately lost."""
    assert os.environ["RUN_SANDBOX_WORKER"] == "1"
    with audit_context():
        async with SessionFactory() as session, session.begin():
            item_id, reviewer_id, publisher_id = await waiting_order(session)
            attempt = await approve_order(session, item_id, reviewer_id)
            identity = attempt.id
            actor = UserEntity(
                username="restore-operator-" + uuid7().hex,
                hashed_password=uuid7().hex,
                is_superuser=True,
            )
            session.add(actor)
            await session.flush()
            operator_id = actor.id
        before = order_count()
        Path(os.environ["ORDER_SANDBOX_FAULT_FILE"]).write_text("lose_reply")
        for _ in range(150):
            await dispatch_outbox(celery_app)
            async with SessionFactory() as session:
                attempt = await session.get(StepExecutionAttemptEntity, identity)
                assert attempt is not None
                if (attempt.automation_snapshot or {}).get("order_dispatch", {}).get(
                    "state"
                ) == "UNKNOWN":
                    execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
                    assert execution is not None
                    process = await session.get(
                        ProcessInstanceEntity, execution.process_instance_id
                    )
                    assert process is not None
                    assert order_count() == before + 1
                    return UnknownOrder(
                        identity,
                        create_ref_id(process.id, process.version),
                        OrderReconciliationDTO(
                            step_execution_ref_id=create_ref_id(execution.id, execution.version),
                            command_key="restore-original-lookup",
                            reason="owned-restore-drill",
                        ),
                        operator_id,
                        publisher_id,
                        before + 1,
                    )
            await anyio.sleep(0.2)
    raise AssertionError("Owned order did not reach UNKNOWN within its original bounded deadline")


async def reconcile_restored(restored_engine, evidence: UnknownOrder) -> None:
    """Explicit operator lookup confirms the same receipt before any restored execution resumes."""
    sessions = async_sessionmaker(restored_engine, class_=AsyncSession, expire_on_commit=False)
    with audit_context():
        dispatcher = ProtectedOrderDispatch(sessions, OrderRecoveryService().provider)
        assert (await dispatcher.execute(evidence.attempt_id)).disposition == "operation_unknown"
        assert order_count() == evidence.orders
        async with sessions() as session, session.begin():
            with pytest.raises(VersionConflictException):
                await ProcessService(session).resume(
                    evidence.process_ref, "unsafe-restored-resume", "success", {}
                )
        recovery = OrderRecoveryService(sessions=sessions)
        with pytest.raises(NotAllowedException):
            await recovery.reconcile(evidence.process_ref, evidence.command, evidence.publisher_id)
        result = await recovery.reconcile(
            evidence.process_ref, evidence.command, evidence.operator_id
        )
        assert result.state == "CONFIRMED" and result.receipt is not None
        assert (
            await recovery.reconcile(evidence.process_ref, evidence.command, evidence.operator_id)
            == result
        )
        assert (await dispatcher.execute(evidence.attempt_id)).disposition == "duplicate"
        assert order_count() == evidence.orders
        async with sessions() as session:
            attempt = await session.get(StepExecutionAttemptEntity, evidence.attempt_id)
            assert attempt is not None and attempt.status == "SUCCEEDED"
        # Original source remains uncertain until independently reconciled; the
        # restored database has no worker and its pending outbox is not published.
        async with SessionFactory() as session:
            source = await session.get(StepExecutionAttemptEntity, evidence.attempt_id)
            assert source is not None and source.automation_snapshot is not None
            assert source.automation_snapshot["order_dispatch"]["state"] == "UNKNOWN"
        original = await OrderRecoveryService().reconcile(
            evidence.process_ref, evidence.command, evidence.operator_id
        )
        assert original.receipt == result.receipt and order_count() == evidence.orders
