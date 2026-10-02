"""PostgreSQL accounting for one logical AI task across sessions."""

import os
from decimal import Decimal
from uuid import uuid7

import pytest
from anyio import create_task_group
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.budget_service import AIBudgetService
from apps.ai.domain.budget import BudgetAmounts
from apps.ai.domain.contracts import AITaskLimits
from apps.ai.domain.entity import AITaskBudgetEntity
from apps.processes.domain.entity import StepExecutionEntity
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from tests.integration.test_processes import _start_waiting_process
from utils.exceptions import VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_reservation_survives_restart_and_blocks_excess_dispatch() -> None:
    limits = AITaskLimits(
        requests=2,
        tool_calls=0,
        input_tokens=100,
        output_tokens=40,
        total_tokens=120,
        elapsed_seconds=3600,
        spend_usd=Decimal("0.40"),
    )
    upper = BudgetAmounts(
        requests=1,
        input_tokens=50,
        output_tokens=20,
        total_tokens=70,
        spend_usd=Decimal("0.30"),
    )
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(
                bind=connection, join_transaction_mode="create_savepoint"
            ) as session:
                actor = UserEntity(
                    username=f"ai-budget-{uuid7().hex}", hashed_password="hash", is_superuser=True
                )
                session.add(actor)
                await session.flush()
                process, _ = await _start_waiting_process(session, actor, "EVENT_WAIT")
                execution = (
                    await session.exec(
                        select(StepExecutionEntity).where(
                            StepExecutionEntity.process_instance_id == process.id,
                            StepExecutionEntity.status == "WAITING",
                        )
                    )
                ).one()
                budget = await AIBudgetService(session).create(
                    execution.id, limits, price_version="test-prices-1"
                )
                first = await AIBudgetService(session).reserve(budget.id, "attempt-1", upper)
                assert first.status == "RESERVED"
                budget_id = budget.id
                execution_id = execution.id
                reservation_id = first.id
                await session.commit()

            async with AsyncSession(
                bind=connection, join_transaction_mode="create_savepoint"
            ) as session:
                service = AIBudgetService(session)
                same = await service.reserve(budget_id, "attempt-1", upper)
                assert same.id == reservation_id
                with pytest.raises(VersionConflictException, match="exhausted"):
                    await service.reserve(budget_id, "attempt-2", upper)
                await service.settle(budget_id, "attempt-1", None)
                status = await service.status_for_execution(execution_id)
                assert status.unknown_usage and status.reserved.requests == 1
                row = await session.get(AITaskBudgetEntity, budget_id)
                assert row is not None and row.reserved["requests"] == 1
                await session.rollback()
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_duplicate_reservations_allow_only_one_dispatch() -> None:
    limits = AITaskLimits(
        requests=1,
        tool_calls=0,
        input_tokens=100,
        output_tokens=40,
        total_tokens=140,
        elapsed_seconds=3600,
        spend_usd=Decimal("0.40"),
        strict_spend=False,
    )
    upper = BudgetAmounts(
        requests=1,
        input_tokens=100,
        output_tokens=40,
        total_tokens=140,
        spend_usd=Decimal("0.30"),
    )
    async with SessionFactory() as session:
        actor = UserEntity(
            username=f"ai-concurrent-{uuid7().hex}", hashed_password="hash", is_superuser=True
        )
        session.add(actor)
        await session.flush()
        process, _ = await _start_waiting_process(session, actor, "EVENT_WAIT")
        execution = (
            await session.exec(
                select(StepExecutionEntity).where(
                    StepExecutionEntity.process_instance_id == process.id,
                    StepExecutionEntity.status == "WAITING",
                )
            )
        ).one()
        budget = await AIBudgetService(session).create(
            execution.id, limits, price_version="test-prices-concurrent"
        )
        budget_id = budget.id
        await session.commit()

    outcomes: list[str] = []

    async def reserve_once() -> None:
        async with SessionFactory() as session, session.begin():
            try:
                await AIBudgetService(session).reserve(
                    budget_id, "same-attempt", upper, allow_existing=False
                )
            except VersionConflictException:
                outcomes.append("duplicate")
            else:
                outcomes.append("reserved")

    async with create_task_group() as group:
        group.start_soon(reserve_once)
        group.start_soon(reserve_once)
    assert sorted(outcomes) == ["duplicate", "reserved"]
    await engine.dispose()
