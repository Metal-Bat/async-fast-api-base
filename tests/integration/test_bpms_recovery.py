"""Recovery authorization, atomic audit and restart-safe command identity on PostgreSQL."""

import os
from uuid import uuid7

import pytest
from anyio import create_task_group
from sqlmodel import select

from apps.processes.application.recovery import ProcessRecoveryService
from apps.processes.application.service import ProcessService
from apps.processes.domain.dto import RecoveryCommandDTO
from apps.processes.domain.entity import ProcessEventEntity, ScheduledActionEntity
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from tests.integration.test_processes import _start_waiting_process
from utils.exceptions import NotAllowedException, VersionConflictException
from utils.pagination import PageRequest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_recovery_replays_once_and_rejects_changed_intent_and_unsafe_states() -> None:
    async with SessionFactory() as session:
        admin = UserEntity(
            username=f"recovery-{uuid7()}", hashed_password="unused", is_superuser=True
        )
        session.add(admin)
        await session.flush()
        process, _ = await _start_waiting_process(session, admin, "TIMER")
        await session.commit()
        service = ProcessRecoveryService(session)
        command = RecoveryCommandDTO(command_key="incident", action="resume", reason="OPS-42")
        with pytest.raises(VersionConflictException), session.no_autoflush:
            async with session.begin_nested():
                await service.recover(create_ref_id(process.id, process.version), command, admin)
        await ProcessService(session).command(
            create_ref_id(process.id, process.version), "pause", "pause"
        )
        await session.commit()
        ref_id = create_ref_id(process.id, process.version)
        async with session.begin_nested() as savepoint:
            await service.recover(ref_id, command, admin)
            await savepoint.rollback()
        await session.refresh(process)
        assert process.status == "PAUSED"
        await service.recover(ref_id, command, admin)
        await session.commit()
        assert process.status == "WAITING"
        process_id, admin_id = process.id, admin.id

    async with SessionFactory() as session:
        admin = await session.get(UserEntity, admin_id)
        assert admin is not None
        service = ProcessRecoveryService(session)
        await service.recover(ref_id, command, admin)
        await session.commit()
        events = (
            await session.exec(
                select(ProcessEventEntity).where(
                    ProcessEventEntity.process_instance_id == process_id,
                    ProcessEventEntity.event_type == "operation.recovered",
                )
            )
        ).all()
        assert len(events) == 1
        assert events[0].actor_user_id == admin.id
        assert events[0].public_payload["reason"] == "OPS-42"
        with pytest.raises(VersionConflictException):
            async with session.begin_nested():
                await service.recover(
                    ref_id, command.model_copy(update={"reason": "OPS-43"}), admin
                )
        admin.is_superuser = False
        with pytest.raises(NotAllowedException):
            await service.recover(ref_id, command, admin)
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_failed_timer_recovery_keeps_dispatch_sequence_and_is_atomic() -> None:
    async with SessionFactory() as session:
        admin = UserEntity(
            username=f"timer-recovery-{uuid7()}", hashed_password="unused", is_superuser=True
        )
        session.add(admin)
        await session.flush()
        process, _ = await _start_waiting_process(session, admin, "TIMER")
        _, execution = await ProcessService(session).current(process.id)
        assert execution is not None
        timer = (
            await session.exec(
                select(ScheduledActionEntity).where(
                    ScheduledActionEntity.step_execution_id == execution.id
                )
            )
        ).one()
        timer.status, timer.attempts = "FAILED", 5
        await session.commit()
        ref_id = create_ref_id(process.id, process.version)
        command = RecoveryCommandDTO(
            command_key="timer",
            action="retry_timer",
            reason="OPS-44",
            scheduled_action_ref_id=create_ref_id(timer.id, timer.version),
        )
        page = await ProcessRecoveryService(session).scheduled_actions(
            ref_id, PageRequest(size=1), admin
        )
        assert page.total == 1 and page.items[0].ref_id == command.scheduled_action_ref_id
        await ProcessRecoveryService(session).recover(ref_id, command, admin)
        await session.commit()
        assert timer.status == "PENDING"
        assert timer.attempts == 5
        assert timer.max_attempts == 6
        await ProcessRecoveryService(session).recover(ref_id, command, admin)
        assert timer.max_attempts == 6
    await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_duplicate_recovery_has_one_audit_event() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(
            username=f"concurrent-recovery-{uuid7()}", hashed_password="unused", is_superuser=True
        )
        session.add(actor)
        await session.flush()
        process, _ = await _start_waiting_process(session, actor, "TIMER")
        await ProcessService(session).command(
            create_ref_id(process.id, process.version), "pause", "pause"
        )
        await session.commit()
        reference, process_id, actor_id = (
            create_ref_id(process.id, process.version),
            process.id,
            actor.id,
        )
    command = RecoveryCommandDTO(command_key="concurrent", action="resume", reason="OPS-45")

    async def recover():
        async with SessionFactory() as session:
            actor = await session.get(UserEntity, actor_id)
            assert actor is not None
            await ProcessRecoveryService(session).recover(reference, command, actor)
            await session.commit()

    async with create_task_group() as tasks:
        tasks.start_soon(recover)
        tasks.start_soon(recover)
    async with SessionFactory() as session:
        events = (
            await session.exec(
                select(ProcessEventEntity).where(
                    ProcessEventEntity.process_instance_id == process_id,
                    ProcessEventEntity.event_type == "operation.recovered",
                )
            )
        ).all()
        assert len(events) == 1
    await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["TIMER", "EVENT_WAIT"])
async def test_failed_wait_can_retry_without_duplicating_registered_identity(kind) -> None:
    from apps.processes.application.waits import fail_scheduled_action
    from apps.processes.domain.entity import StepExecutionAttemptEntity

    async with SessionFactory() as session:
        actor = UserEntity(
            username=f"retry-wait-{uuid7()}", hashed_password="unused", is_superuser=True
        )
        session.add(actor)
        await session.flush()
        process, _ = await _start_waiting_process(session, actor, kind)
        service = ProcessService(session)
        _, execution = await service.current(process.id)
        assert execution is not None
        timer = (
            await session.exec(
                select(ScheduledActionEntity).where(
                    ScheduledActionEntity.step_execution_id == execution.id
                )
            )
        ).one()
        timer.status, timer.attempts = "FAILED", 5
        await session.commit()
        await fail_scheduled_action(timer.id)
        await session.refresh(process)
        assert process.status == "FAILED"
        reference = create_ref_id(process.id, process.version)
        command = RecoveryCommandDTO(
            command_key="retry-failed-wait", action="retry", reason="OPS-46"
        )
        await ProcessRecoveryService(session).recover(reference, command, actor)
        await session.commit()
        await session.refresh(timer)
        assert process.status == "WAITING" and timer.status == "PENDING"
        assert timer.attempts == 5 and timer.max_attempts > 5
        before = (
            await session.exec(
                select(StepExecutionAttemptEntity).where(
                    StepExecutionAttemptEntity.step_execution_id == execution.id
                )
            )
        ).all()
        await ProcessRecoveryService(session).recover(reference, command, actor)
        after = (
            await session.exec(
                select(StepExecutionAttemptEntity).where(
                    StepExecutionAttemptEntity.step_execution_id == execution.id
                )
            )
        ).all()
        assert len(after) == len(before)
    await engine.dispose()
