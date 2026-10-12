"""One case exposes its actual worker receipt through the existing human form UI."""

import os
import secrets

import pytest
from anyio import create_task_group, sleep
from httpx import ASGITransport, AsyncClient, Response
from pydantic_ai.models.test import TestModel
from sqlmodel import col, select

from apps.ai.application.process_evidence import AIProcessEvidenceService
from apps.ai.domain.entity import AITaskBudgetEntity
from apps.notifications.domain.entity import NotificationEntity
from apps.processes.application.automation import execute_background
from apps.processes.application.timeline import ProcessTimelineService
from apps.processes.domain.dto import ProcessTimelineQueryDTO
from apps.processes.domain.entity import (
    ProcessEventEntity,
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.tasks.application.outbox import dispatch_outbox
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CorrectionFeedbackInput
from apps.work_items.domain.entity import WorkItemCandidateEntity, WorkItemEntity
from apps.workflows.domain.entity import WorkflowStepEntity
from core.celery_app import celery_app
from core.deps import SessionFactory, engine
from core.history import audit_context
from core.i18n import use_language
from core.ref_id import create_ref_id
from core.settings import settings
from main import app
from tests.integration.test_connected_fixture import connected_profile
from tests.integration.test_purchase_pins_fixture import publish_waiting_case_successors
from tests.integration.test_purchase_request_fixture import assert_saved_purchase_snapshot
from tests.integration.test_required_human_approval import approve_order, waiting_order
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException
from utils.pagination import PageRequest
from utils.security import hash_password

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.fixture
def scripted_model(monkeypatch):
    from apps.processes.application import extension_services

    monkeypatch.setattr(settings, "FORM_NAVIGATION_ROUTES", ["/people/pick"])

    monkeypatch.setattr(
        extension_services,
        "create_model",
        lambda *args, **kwargs: TestModel(custom_output_args={"choice": "procurement"}),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("language", ["en", "fa"])
@pytest.mark.parametrize("connected, correction", [(False, False), (True, False), (True, True)])
async def test_same_case_renders_real_receipt_in_authorized_read_only_human_view(
    language, connected, correction, scripted_model
):
    assert os.getenv("RUN_SANDBOX_WORKER") == "1", "requires the actual owned worker/sandbox"
    try:
        with use_language(language), audit_context():
            async with SessionFactory() as session:
                item_id, reviewer_id, publisher_id = await waiting_order(
                    session, receipt_view=True, connected=connected
                )
                if connected:
                    await assert_saved_purchase_snapshot(
                        session, item_id, reviewer_id, publisher_id
                    )
                    if correction:
                        await publish_waiting_case_successors(session, item_id, publisher_id)
                    item_id = await _complete_parallel_reviews(session, item_id, reviewer_id)
                    original = await session.get(WorkItemEntity, item_id)
                    assert original is not None
                    budgets = (
                        await session.exec(
                            select(AITaskBudgetEntity)
                            .join(StepExecutionEntity)
                            .join(
                                ProcessInstanceEntity,
                                col(StepExecutionEntity.process_instance_id)
                                == col(ProcessInstanceEntity.id),
                            )
                            .where(
                                ProcessInstanceEntity.business_request_id
                                == original.business_request_id
                            )
                        )
                    ).all()
                    assert len(budgets) == 1, "same case must include a budgeted scripted AI stage"
                payload = connected_profile()["order_payload"]
                if correction:
                    item_id = await _correct_order(session, item_id, reviewer_id, publisher_id)
                    payload = connected_profile()["corrected_order_payload"]
                human = await session.get(WorkItemEntity, item_id)
                assert human is not None
                human_ref = create_ref_id(human.id, human.version)
                attempt = await approve_order(session, item_id, reviewer_id, payload=payload)
                attempt_id = attempt.id
                await session.commit()
            async with SessionFactory() as session, session.begin():
                reviewer = await session.get(UserEntity, reviewer_id)
                assert reviewer is not None
                replayed = await WorkItemService(session).finish(
                    human_ref, "complete", "approve-order", "approve", payload, reviewer
                )
                assert replayed.id == item_id and replayed.status == "COMPLETED"
                with pytest.raises(VersionConflictException):
                    await WorkItemService(session).finish(
                        human_ref, "complete", "stale-new-intent", "approve", payload, reviewer
                    )
                with pytest.raises(VersionConflictException):
                    await WorkItemService(session).finish(
                        human_ref,
                        "complete",
                        "approve-order",
                        "approve",
                        {**payload, "quantity": payload["quantity"] + 1},
                        reviewer,
                    )
            for _ in range(150):
                await dispatch_outbox(celery_app)
                async with SessionFactory() as session:
                    attempt = await session.get(StepExecutionAttemptEntity, attempt_id)
                    assert attempt is not None
                    if attempt.status == "SUCCEEDED":
                        break
                await sleep(0.2)
            assert attempt.status == "SUCCEEDED"
            assert attempt.automation_snapshot is not None
            receipt = attempt.automation_snapshot["order_dispatch"]["receipt"]
            assert receipt["state"] == "CREATED"
            async with SessionFactory() as session, session.begin():
                execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
                assert execution is not None
                original = await session.get(WorkItemEntity, item_id)
                assert original is not None
                items = (
                    await session.exec(
                        select(WorkItemEntity).where(
                            WorkItemEntity.business_request_id == original.business_request_id,
                            WorkItemEntity.status == "OPEN",
                        )
                    )
                ).all()
                assert len(items) == 1
                reviewer = await session.get(UserEntity, reviewer_id)
                assert reviewer is not None
                await _wait_receipt_notice(items[0].id, reviewer_id)
                receipt_item = await WorkItemService(session).claim(
                    create_ref_id(items[0].id, items[0].version), "claim-receipt", reviewer
                )
                view = await WorkItemService(session).task_view(
                    create_ref_id(receipt_item.id, receipt_item.version), reviewer
                )
                assert view.data == receipt
                assert view.title == (
                    "Confirmed sandbox receipt" if language == "en" else "رسید تأییدشدهٔ آزمایشی"
                )
                runtime = await WorkItemService(session).runtime_state(
                    create_ref_id(receipt_item.id, receipt_item.version), reviewer
                )
                assert runtime is not None
                assert runtime.resolved_locale == language
                assert runtime.direction == ("rtl" if language == "fa" else "ltr")
                assert runtime.data == receipt
                assert runtime.writable_scopes == []
                assert all(not field.writable for field in runtime.field_metadata)
                outsider = UserEntity(
                    username="receipt-outsider-" + str(attempt_id),
                    hashed_password=str(attempt_id),
                )
                session.add(outsider)
                await session.flush()
                with pytest.raises(NotFoundException):
                    await WorkItemService(session).task_view(
                        create_ref_id(receipt_item.id, receipt_item.version), outsider
                    )
                with pytest.raises(ValidationDetailsException):
                    await WorkItemService(session).finish(
                        create_ref_id(receipt_item.id, receipt_item.version),
                        "complete",
                        "forged-receipt",
                        "acknowledge",
                        {**receipt, "receipt_id": str(attempt_id)},
                        reviewer,
                    )
                acknowledge_ref = create_ref_id(receipt_item.id, receipt_item.version)
                await WorkItemService(session).finish(
                    acknowledge_ref,
                    "complete",
                    "acknowledge-receipt",
                    "acknowledge",
                    receipt,
                    reviewer,
                )
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None and process.status == "COMPLETED"
                replay = await WorkItemService(session).finish(
                    acknowledge_ref,
                    "complete",
                    "acknowledge-receipt",
                    "acknowledge",
                    receipt,
                    reviewer,
                )
                assert replay.id == receipt_item.id and replay.status == "COMPLETED"
                if connected:
                    timeline = await ProcessTimelineService(session).get(
                        process, ProcessTimelineQueryDTO()
                    )
                    executed = {
                        step.step_key for step in timeline.steps if step.path_status == "executed"
                    }
                    assert set(connected_profile()["required_stages"]) <= executed
                    if correction:
                        assert "correction" in executed
                    assert len(timeline.children) == 2
                    assert all(child.status == "COMPLETED" for child in timeline.children)
                    evidence = await AIProcessEvidenceService(session).search(
                        process.id, PageRequest()
                    )
                    assert evidence.total == 1
                    row = evidence.items[0]
                    assert row.allowed_input_fields == ["item_code"]
                    assert row.recommendation is not None and row.recommendation.needs_review
                    assert row.budget is not None and not row.budget.unknown_usage
            duplicate = await execute_background(attempt_id)
            assert duplicate.disposition == "duplicate"
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("language", ["en", "fa"])
async def test_same_case_rejection_after_reviews_stages_no_order_or_receipt(
    language, scripted_model
):
    assert os.getenv("RUN_SANDBOX_WORKER") == "1"
    try:
        with use_language(language), audit_context():
            async with SessionFactory() as session:
                item_id, reviewer_id, _ = await waiting_order(
                    session, receipt_view=True, connected=True
                )
                item_id = await _complete_parallel_reviews(session, item_id, reviewer_id)
                item = await session.get(WorkItemEntity, item_id)
                reviewer = await session.get(UserEntity, reviewer_id)
                assert item is not None and reviewer is not None
                rejected = await WorkItemService(session).finish(
                    create_ref_id(item.id, item.version),
                    "reject",
                    "reject-reviewed-order",
                    "reject",
                    connected_profile()["order_payload"],
                    reviewer,
                    comment="Synthetic purchasing request rejected",
                )
                assert rejected.status == "REJECTED"
                executions = (
                    await session.exec(
                        select(StepExecutionEntity)
                        .join(
                            WorkflowStepEntity,
                            col(StepExecutionEntity.workflow_step_id) == col(WorkflowStepEntity.id),
                        )
                        .join(
                            ProcessInstanceEntity,
                            col(StepExecutionEntity.process_instance_id)
                            == col(ProcessInstanceEntity.id),
                        )
                        .where(
                            ProcessInstanceEntity.business_request_id == item.business_request_id,
                            col(WorkflowStepEntity.step_key).in_(["order", "receipt"]),
                        )
                    )
                ).all()
                assert executions == []
                assert (
                    await session.exec(
                        select(WorkItemEntity).where(
                            WorkItemEntity.business_request_id == item.business_request_id,
                            col(WorkItemEntity.status).in_(["OPEN", "CLAIMED", "IN_PROGRESS"]),
                        )
                    )
                ).all() == []
                await session.commit()
            await dispatch_outbox(celery_app)
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("language", ["en", "fa"])
async def test_same_case_two_authenticated_eligible_reviewers_cannot_both_claim(
    language, scripted_model
):
    assert os.getenv("RUN_SANDBOX_WORKER") == "1"
    try:
        with use_language(language), audit_context():
            password = secrets.token_urlsafe(32)
            digest = await hash_password(password)
            async with SessionFactory() as session:
                item_id, reviewer_id, _ = await waiting_order(
                    session, receipt_view=True, connected=True
                )
                item_id = await _complete_parallel_reviews(
                    session, item_id, reviewer_id, claim_final=False
                )
                item = await session.get(WorkItemEntity, item_id)
                assert item is not None
                original_ref = create_ref_id(item.id, item.version)
                candidates = (
                    await session.exec(
                        select(WorkItemCandidateEntity).where(
                            WorkItemCandidateEntity.work_item_id == item_id,
                        )
                    )
                ).all()
                assert len(candidates) == 2
                actors = []
                for candidate in candidates:
                    actor = await session.get(UserEntity, candidate.user_id)
                    assert actor is not None and not actor.is_superuser
                    actor.hashed_password = digest
                    actors.append((actor.id, actor.username))
                await session.commit()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://owned-test"
            ) as client:
                headers = []
                for _, username in actors:
                    login = await client.post(
                        "/api/v1/auth/login", json={"username": username, "password": password}
                    )
                    assert login.status_code == 200, "Owned ordinary reviewer login failed"
                    headers.append(
                        {
                            "Authorization": "Bearer " + login.json()["data"]["access_token"],
                            "Accept-Language": language,
                        }
                    )
                pending: list[Response | None] = [None, None]

                async def claim(index: int) -> None:
                    pending[index] = await client.post(
                        "/api/v1/work-items/" + original_ref + "/claim",
                        headers=headers[index],
                        json={"command_key": "claim-race-" + str(index)},
                    )

                async with create_task_group() as group:
                    for index in range(len(headers)):
                        group.start_soon(claim, index)
                assert all(response is not None for response in pending)
                results = [response for response in pending if response is not None]
                assert sorted(response.status_code for response in results) == [200, 409]
                winner = next(
                    index for index, response in enumerate(results) if response.status_code == 200
                )
                replay = await client.post(
                    "/api/v1/work-items/" + original_ref + "/claim",
                    headers=headers[winner],
                    json={"command_key": "claim-race-" + str(winner)},
                )
                assert replay.status_code == 200
                assert replay.json()["data"]["ref_id"] == results[winner].json()["data"]["ref_id"]
            async with SessionFactory() as session:
                item = await session.get(WorkItemEntity, item_id)
                assert item is not None and item.claimed_by_user_id == actors[winner][0]
    finally:
        await engine.dispose()


async def _complete_parallel_reviews(session, item_id, reviewer_id, *, claim_final=True):
    initial = await session.get(WorkItemEntity, item_id)
    reviewer = await session.get(UserEntity, reviewer_id)
    assert initial is not None and reviewer is not None
    service = WorkItemService(session)
    await service.finish(
        create_ref_id(initial.id, initial.version),
        "complete",
        "triage",
        "approve",
        {"item_code": "DEMO", "quantity": 2},
        reviewer,
    )
    await session.commit()
    ai_budget = (
        await session.exec(
            select(AITaskBudgetEntity)
            .join(StepExecutionEntity)
            .join(
                ProcessInstanceEntity,
                col(StepExecutionEntity.process_instance_id) == col(ProcessInstanceEntity.id),
            )
            .where(ProcessInstanceEntity.business_request_id == initial.business_request_id)
        )
    ).one()
    ai_attempt = (
        await session.exec(
            select(StepExecutionAttemptEntity).where(
                StepExecutionAttemptEntity.step_execution_id == ai_budget.step_execution_id,
                StepExecutionAttemptEntity.status == "WAITING",
            )
        )
    ).one()
    assert ai_attempt.automation_snapshot is not None
    assert ai_attempt.automation_snapshot["ai_decision"] is not None
    await session.commit()
    from tests.integration.test_scripted_ai_fixture import scripted_provider

    result = await execute_background(ai_attempt.id, scripted_provider())
    assert result.disposition == "completed"
    supervision = (
        await session.exec(
            select(WorkItemEntity).where(
                WorkItemEntity.business_request_id == initial.business_request_id,
                WorkItemEntity.status == "OPEN",
            )
        )
    ).one()
    supervision = await service.claim(
        create_ref_id(supervision.id, supervision.version), "claim-supervision", reviewer
    )
    await service.finish(
        create_ref_id(supervision.id, supervision.version),
        "complete",
        "human-ai-review",
        "approve",
        {"item_code": "DEMO", "quantity": 2},
        reviewer,
    )
    branches = (
        await session.exec(
            select(WorkItemEntity).where(
                WorkItemEntity.business_request_id == initial.business_request_id,
                WorkItemEntity.status == "OPEN",
            )
        )
    ).all()
    assert len(branches) == 2
    pinned_versions = set()
    for index, item in enumerate(branches):
        execution = await session.get(StepExecutionEntity, item.step_execution_id)
        assert execution is not None
        process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
        assert process is not None and process.parent_step_execution_id is not None
        pinned_versions.add(process.workflow_version_id)
        candidate = (
            await session.exec(
                select(WorkItemCandidateEntity).where(
                    WorkItemCandidateEntity.work_item_id == item.id,
                )
            )
        ).one()
        actor = await session.get(UserEntity, candidate.user_id)
        assert actor is not None and not actor.is_superuser
        item = await service.claim(create_ref_id(item.id, item.version), "claim-branch", actor)
        await service.finish(
            create_ref_id(item.id, item.version),
            "complete",
            "finish-branch",
            "approve",
            {"item_code": "DEMO", "quantity": 2},
            actor,
        )
        assert process.status == "COMPLETED"
        await session.commit()
        await _wait_parent_settlement(process.parent_step_execution_id)
        celery_app.send_task(
            "bpms.settle_subprocess",
            kwargs={"child_id": str(process.id)},
            queue=settings.CELERY_AUTOMATION_QUEUE,
        )
        if index == 0:
            open_items = (
                await session.exec(
                    select(WorkItemEntity).where(
                        WorkItemEntity.business_request_id == initial.business_request_id,
                        WorkItemEntity.status == "OPEN",
                    )
                )
            ).all()
            assert len(open_items) == 1 and open_items[0].id == branches[1].id
    assert len(pinned_versions) == 1
    final = (
        await session.exec(
            select(WorkItemEntity).where(
                WorkItemEntity.business_request_id == initial.business_request_id,
                WorkItemEntity.status == "OPEN",
            )
        )
    ).one()
    if claim_final:
        final = await service.claim(
            create_ref_id(final.id, final.version), "final-root-approval", reviewer
        )
    return final.id


async def _wait_parent_settlement(execution_id):
    for _ in range(150):
        await dispatch_outbox(celery_app)
        async with SessionFactory() as session:
            execution = await session.get(StepExecutionEntity, execution_id)
            assert execution is not None
            if execution.status == "COMPLETED":
                return
        await sleep(0.2)
    pytest.fail("Actual worker did not settle the committed child result before the deadline")


async def _correct_order(session, item_id, reviewer_id, publisher_id):
    item = await session.get(WorkItemEntity, item_id)
    reviewer = await session.get(UserEntity, reviewer_id)
    requester = await session.get(UserEntity, publisher_id)
    assert item is not None and reviewer is not None and requester is not None
    service = WorkItemService(session)
    await service.finish(
        create_ref_id(item.id, item.version),
        "return",
        "quantity-correction",
        "return",
        connected_profile()["order_payload"],
        reviewer,
        comment="Synthetic quantity needs correction",
        feedback=[
            CorrectionFeedbackInput(scope="/properties/quantity", message="Correct the quantity")
        ],
    )
    correction = (
        await session.exec(
            select(WorkItemEntity).where(
                WorkItemEntity.business_request_id == item.business_request_id,
                WorkItemEntity.status == "OPEN",
            )
        )
    ).one()
    correction = await service.claim(
        create_ref_id(correction.id, correction.version), "claim-correction", requester
    )
    await service.finish(
        create_ref_id(correction.id, correction.version),
        "complete",
        "correct-quantity",
        "approve",
        connected_profile()["corrected_order_payload"],
        requester,
    )
    fresh = (
        await session.exec(
            select(WorkItemEntity).where(
                WorkItemEntity.business_request_id == item.business_request_id,
                WorkItemEntity.status == "OPEN",
            )
        )
    ).one()
    assert fresh.id != item.id
    fresh = await service.claim(
        create_ref_id(fresh.id, fresh.version), "claim-fresh-approval", reviewer
    )
    view = await service.task_view(create_ref_id(fresh.id, fresh.version), reviewer)
    assert view.data == connected_profile()["corrected_order_payload"]
    return fresh.id


async def _wait_receipt_notice(item_id, reviewer_id):
    for _ in range(150):
        await dispatch_outbox(celery_app)
        async with SessionFactory() as session:
            notices = (
                await session.exec(
                    select(NotificationEntity)
                    .join(
                        ProcessEventEntity,
                        col(NotificationEntity.event_id) == col(ProcessEventEntity.id),
                    )
                    .where(
                        ProcessEventEntity.work_item_id == item_id,
                        ProcessEventEntity.event_type == "work_item.created",
                        NotificationEntity.recipient_user_id == reviewer_id,
                    )
                )
            ).all()
        if notices:
            break
        await sleep(0.2)
    assert len(notices) == 1, "actual outbox must persist one recipient receipt-task notice"
