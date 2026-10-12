"""Lost acknowledgments never authorize another order; operators use receipt lookup."""

import os
from pathlib import Path
from uuid import uuid7

import pytest
from anyio import sleep
from sqlmodel import select

from apps.processes.application.automation import execute_background
from apps.processes.application.compensation import execute_compensation
from apps.processes.application.service import ProcessService
from apps.processes.domain.entity import (
    CompensationRecordEntity,
    ProcessEventEntity,
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.tasks.application.outbox import dispatch_outbox
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.entity import WorkItemEntity
from core.celery_app import celery_app
from core.deps import SessionFactory, engine
from core.history import audit_context
from core.i18n import use_language
from core.ref_id import create_ref_id
from tests.integration.test_connected_workflow import _complete_parallel_reviews
from tests.integration.test_connected_workflow import scripted_model as connected_scripted_model
from tests.integration.test_required_human_approval import approve_order, waiting_order
from utils.exceptions import NotAllowedException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]

scripted_model = connected_scripted_model


@pytest.mark.anyio
async def test_crash_before_http_has_unknown_lookup_and_cannot_claim_compensated():
    from datetime import timedelta

    from apps.processes.application.compensation import CompensationService
    from apps.processes.application.order_recovery import OrderRecoveryService
    from apps.processes.domain.dtos.orders import OrderReconciliationDTO
    from utils.date_utils import get_datetime_utc

    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session, session.begin():
                item_id, reviewer_id, publisher_id = await waiting_order(session)
                attempt = await approve_order(session, item_id, reviewer_id)
                snapshot = dict(attempt.automation_snapshot or {})
                snapshot["order_dispatch"] = {
                    **snapshot["order_dispatch"],
                    "state": "DISPATCHING",
                    "dispatched_at": (get_datetime_utc() - timedelta(seconds=30)).isoformat(),
                }
                attempt.automation_snapshot = snapshot
                execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
                assert execution is not None
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None
                operator = UserEntity(
                    username="pre-http-" + uuid7().hex,
                    hashed_password=uuid7().hex,
                    is_superuser=True,
                )
                session.add(operator)
                await session.flush()
                process_id, operator_id = process.id, operator.id
                process_ref = create_ref_id(process.id, process.version)
                command = OrderReconciliationDTO(
                    step_execution_ref_id=create_ref_id(execution.id, execution.version),
                    command_key="crash-lookup",
                    reason="before-http",
                )
            result = await OrderRecoveryService().reconcile(process_ref, command, operator_id)
            assert result.state == "UNKNOWN" and result.receipt is None
            async with SessionFactory() as session, session.begin():
                process = await session.get(ProcessInstanceEntity, process_id)
                assert process is not None
                await ProcessService(session).command(
                    create_ref_id(process.id, process.version),
                    "cancel",
                    "cancel-unknown",
                    actor_user_id=publisher_id,
                )
            async with SessionFactory() as session, session.begin():
                with pytest.raises(VersionConflictException, match="reconciliation"):
                    await CompensationService(session).begin(
                        process_id, "unsafe-compensation", publisher_id
                    )
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.usefixtures("scripted_model")
@pytest.mark.parametrize("connected", [False, True])
async def test_acknowledgment_loss_reconciles_same_receipt_without_replaying_order(connected):
    assert os.getenv("RUN_SANDBOX_WORKER") == "1", "mandatory real sandbox/worker missing"
    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session:
                item_id, reviewer_id, publisher_id = await waiting_order(
                    session, connected=connected, receipt_view=connected
                )
                if connected:
                    item_id = await _complete_parallel_reviews(session, item_id, reviewer_id)
                await session.commit()
            async with SessionFactory() as session, session.begin():
                attempt = await approve_order(session, item_id, reviewer_id)
                identity = attempt.id
                operator = UserEntity(
                    username="reconcile-" + uuid7().hex,
                    hashed_password=uuid7().hex,
                    is_superuser=True,
                )
                session.add(operator)
                await session.flush()
                operator_id = operator.id
            Path(os.environ["ORDER_SANDBOX_FAULT_FILE"]).write_text("lose_reply")
            await dispatch_outbox(celery_app)
            for _ in range(150):
                # Exercise successive real dispatcher batches, as the scheduler does.
                # Earlier isolation cases may have staged more than one batch.
                await dispatch_outbox(celery_app)
                async with SessionFactory() as session:
                    attempt = await session.get(StepExecutionAttemptEntity, identity)
                    assert attempt is not None and attempt.automation_snapshot is not None
                    if (attempt.automation_snapshot.get("order_dispatch") or {}).get(
                        "state"
                    ) == "UNKNOWN":
                        break
                await sleep(0.2)
            assert attempt.automation_snapshot["order_dispatch"]["state"] == "UNKNOWN", (
                attempt.status,
                attempt.error_code,
            )
            assert (await execute_background(identity)).disposition == "operation_unknown"
            async with SessionFactory() as session:
                execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
                assert execution is not None
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None
                process_ref = create_ref_id(process.id, process.version)
                execution_ref = create_ref_id(execution.id, execution.version)
            from apps.processes.application.order_recovery import OrderRecoveryService
            from apps.processes.domain.dtos.orders import OrderReconciliationDTO

            command = OrderReconciliationDTO(
                step_execution_ref_id=execution_ref,
                command_key="lost-reply",
                reason="incident-demo",
            )
            with pytest.raises(NotAllowedException):
                await OrderRecoveryService().reconcile(process_ref, command, publisher_id)
            result = await OrderRecoveryService().reconcile(process_ref, command, operator_id)
            assert result.receipt is not None and result.receipt.state == "CREATED"
            assert result.state == "CONFIRMED"
            replay = await OrderRecoveryService().reconcile(process_ref, command, operator_id)
            assert replay == result
            with pytest.raises(VersionConflictException):
                await OrderRecoveryService().reconcile(
                    process_ref,
                    command.model_copy(update={"reason": "different-intent"}),
                    operator_id,
                )
            async with SessionFactory() as session:
                attempt = await session.get(StepExecutionAttemptEntity, identity)
                assert attempt is not None and attempt.status == "SUCCEEDED"
                assert attempt.automation_snapshot is not None
                assert attempt.automation_snapshot["order_dispatch"][
                    "receipt"
                ] == result.receipt.model_dump(mode="json")
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None
                if connected:
                    assert process.status == "WAITING"
                    items = (
                        await session.exec(
                            select(WorkItemEntity).where(
                                WorkItemEntity.business_request_id == process.business_request_id,
                                WorkItemEntity.status == "OPEN",
                            )
                        )
                    ).all()
                    assert len(items) == 1
                    reviewer = await session.get(UserEntity, reviewer_id)
                    assert reviewer is not None
                    item = await WorkItemService(session).claim(
                        create_ref_id(items[0].id, items[0].version), "recovered-receipt", reviewer
                    )
                    view = await WorkItemService(session).task_view(
                        create_ref_id(item.id, item.version), reviewer
                    )
                    assert view.data == result.receipt.model_dump(mode="json")
                    await WorkItemService(session).finish(
                        create_ref_id(item.id, item.version),
                        "complete",
                        "acknowledge-recovered",
                        "acknowledge",
                        view.data,
                        reviewer,
                    )
                    await session.commit()
                assert process.status == "COMPLETED"
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.usefixtures("scripted_model")
@pytest.mark.parametrize("connected", [False, True])
@pytest.mark.parametrize("lose_reply", [False, True])
async def test_explicit_compensation_records_actual_separate_cancellation_receipt(
    lose_reply, connected
):
    assert os.getenv("RUN_SANDBOX_WORKER") == "1", "mandatory real sandbox/worker missing"
    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session:
                item_id, reviewer_id, publisher_id = await waiting_order(
                    session, reversible=True, connected=connected
                )
                if connected:
                    item_id = await _complete_parallel_reviews(session, item_id, reviewer_id)
                await session.commit()
            async with SessionFactory() as session, session.begin():
                attempt = await approve_order(session, item_id, reviewer_id)
                attempt_id = attempt.id
            await dispatch_outbox(celery_app)
            for _ in range(150):
                async with SessionFactory() as session:
                    attempt = await session.get(StepExecutionAttemptEntity, attempt_id)
                    assert attempt is not None
                    if attempt.status == "SUCCEEDED":
                        break
                await sleep(0.2)
            assert attempt.status == "SUCCEEDED"
            async with SessionFactory() as session, session.begin():
                execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
                assert execution is not None
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None and process.status == "WAITING"
                await ProcessService(session).command(
                    create_ref_id(process.id, process.version),
                    "cancel",
                    "cancel-unshipped",
                    actor_user_id=publisher_id,
                )
                await session.flush()
                await ProcessService(session).command(
                    create_ref_id(process.id, process.version),
                    "compensate",
                    "reverse-unshipped",
                    actor_user_id=publisher_id,
                )
                process_id = process.id
                record = (
                    await session.exec(
                        select(CompensationRecordEntity).where(
                            CompensationRecordEntity.process_instance_id == process.id
                        )
                    )
                ).one()
                record_id = record.id
            if lose_reply:
                Path(os.environ["ORDER_SANDBOX_FAULT_FILE"]).write_text("lose_reply")
            await dispatch_outbox(celery_app)
            for _ in range(150):
                async with SessionFactory() as session:
                    record = await session.get(CompensationRecordEntity, record_id)
                    assert record is not None
                    if record.status in {"COMPLETED", "FAILED"}:
                        break
                await sleep(0.2)
            if lose_reply:
                assert record.status == "FAILED"
                from apps.processes.application.order_recovery import OrderRecoveryService
                from apps.processes.domain.dtos.orders import OrderReconciliationDTO

                async with SessionFactory() as session, session.begin():
                    process = await session.get(ProcessInstanceEntity, process_id)
                    execution = await session.get(StepExecutionEntity, record.source_execution_id)
                    assert process is not None and execution is not None
                    operator = UserEntity(
                        username="cancel-recovery-" + uuid7().hex,
                        hashed_password=uuid7().hex,
                        is_superuser=True,
                    )
                    session.add(operator)
                    await session.flush()
                    operator_id = operator.id
                    process_ref = create_ref_id(process.id, process.version)
                    command = OrderReconciliationDTO(
                        step_execution_ref_id=create_ref_id(execution.id, execution.version),
                        command_key="recover-cancel",
                        reason="ack-loss",
                    )
                with pytest.raises(NotAllowedException):
                    await OrderRecoveryService().reconcile_cancellation(
                        process_ref, command, publisher_id
                    )
                queued = await OrderRecoveryService().reconcile_cancellation(
                    process_ref, command, operator_id
                )
                assert queued.status == "RUNNING"
                await dispatch_outbox(celery_app)
                for _ in range(150):
                    async with SessionFactory() as session:
                        record = await session.get(CompensationRecordEntity, record_id)
                        assert record is not None
                        if record.status in {"COMPLETED", "FAILED"}:
                            break
                    await sleep(0.2)
                replay = await OrderRecoveryService().reconcile_cancellation(
                    process_ref, command, operator_id
                )
                assert replay.status == "COMPLETED"
            assert record.status == "COMPLETED"
            await execute_compensation(record_id)
            async with SessionFactory() as session:
                process = await session.get(ProcessInstanceEntity, process_id)
                assert process is not None and process.status == "COMPENSATED"
                events = (
                    await session.exec(
                        select(ProcessEventEntity).where(
                            ProcessEventEntity.process_instance_id == process_id,
                            ProcessEventEntity.event_type == "compensation.receipt_confirmed",
                        )
                    )
                ).all()
                assert len(events) == 1
                assert events[0].public_payload["state"] == "CANCELLED"
                assert events[0].public_payload["receipt_id"]
                assert (
                    events[0].public_payload["operation_id"]
                    != events[0].public_payload["order_operation_id"]
                )
    finally:
        await engine.dispose()
