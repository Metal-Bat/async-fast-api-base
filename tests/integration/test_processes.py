"""PostgreSQL coverage for durable single-token workflow execution."""

import os
import subprocess
import sys
from datetime import timedelta
from typing import Literal, override
from uuid import uuid7

import pytest
from anyio import create_task_group, to_thread
from sqlalchemy.exc import DBAPIError
from sqlmodel import col, func, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.integrations.domain.contracts import AdapterResult
from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.notifications.application.delivery import deliver_notification
from apps.notifications.application.service import NotificationService
from apps.notifications.domain.dto import DeliveryResult
from apps.notifications.domain.entity import NotificationDeliveryEntity, NotificationEntity
from apps.processes.application.automation import execute_background
from apps.processes.application.compensation import CompensationService, execute_compensation
from apps.processes.application.events import ProcessEventService
from apps.processes.application.service import ProcessService
from apps.processes.application.subprocess import SubprocessService
from apps.processes.application.timeline import ProcessTimelineService
from apps.processes.application.waits import (
    ProcessWaitService,
    claim_due_actions,
    fail_scheduled_action,
    fire_claimed_action,
)
from apps.processes.domain.dto import ProcessTimelineQueryDTO
from apps.processes.domain.entity import (
    CompensationRecordEntity,
    EventSubscriptionEntity,
    ExecutionTokenEntity,
    ProcessEventEntity,
    ProcessInstanceEntity,
    ProcessTransitionEntity,
    ScheduledActionEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.processes.presentation.routes import authorized
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.step_types.application.registry import builtin_registry, get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.tasks.domain.entity import TaskOutboxEntity
from apps.users.domain.entity import UserEntity
from apps.work_items.domain.entity import WorkItemEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphBinding,
    GraphFlow,
    GraphSnapshot,
    GraphStep,
    GraphTarget,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from apps.workflows.domain.entity import WorkflowStepEntity
from apps.workflows.domain.subprocess import (
    SubprocessCall,
    SubprocessInterface,
)
from core.deps import SessionFactory, engine
from core.history import audit_context
from core.i18n import use_language
from core.ref_id import create_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    NotAllowedException,
    NotFoundException,
    ServiceUnavailableException,
    ValidationDetailsException,
    VersionConflictException,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


async def _step_refs(session: AsyncSession) -> dict[tuple[str, int], str]:
    rows = (
        await session.exec(
            select(StepTypeEntity.code, StepTypeVersionEntity)
            .join(
                StepTypeVersionEntity,
                col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
            )
            .where(StepTypeVersionEntity.status == "PUBLISHED")
        )
    ).all()
    return {
        (code, version.number): create_ref_id(version.id, version.version) for code, version in rows
    }


async def _published_form(session: AsyncSession, owner: UserEntity):
    service = FormService(session)
    root = await service.create(
        FormCreateDTO(code=f"PF{uuid7().hex}", name="Process input"), owner.id
    )
    version = await service.create_version(
        FormVersionCreateDTO(
            form_ref_id=create_ref_id(root.id, root.version),
            number=1,
            data_schema={
                "type": "object",
                "properties": {"amount": {"type": "string"}},
                "required": ["amount"],
            },
            render_schema={
                "dialect": "bpms.render/1",
                "root": {
                    "component": "vertical",
                    "children": [
                        {
                            "component": "text",
                            "scope": "/properties/amount",
                            "label": "Amount",
                        }
                    ],
                },
                "outcomes": ["approve"],
            },
        )
    )
    version = await service.publish(create_ref_id(version.id, version.version), owner.id)
    return root, version


async def _start_waiting_process(
    session: AsyncSession,
    actor: UserEntity,
    wait_code: Literal["EVENT_WAIT", "TIMER"],
    client_context=None,
    client_branches: bool = False,
) -> tuple[ProcessInstanceEntity, str]:
    form, _ = await _published_form(session, actor)
    refs = await _step_refs(session)
    workflows = WorkflowService(session, builtin_registry())
    root = await workflows.create(
        WorkflowCreateDTO(code=f"WT{uuid7().hex}", name=f"{wait_code} process"), actor.id
    )
    version = await workflows.create_version(
        WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
    )
    wait_config = (
        {"event_type": "payment.received", "expires_in_seconds": 3600}
        if wait_code == "EVENT_WAIT"
        else {"delay_seconds": 3600}
    )
    correlation_key = f"invoice-{uuid7()}"
    transitions = [
        GraphTransition(source="start", target="wait", outcome="next", is_default=True),
        GraphTransition(
            source="wait",
            target="finish",
            outcome="received" if wait_code == "EVENT_WAIT" else "elapsed",
            is_default=True,
        ),
    ]
    if wait_code == "EVENT_WAIT":
        transitions.append(GraphTransition(source="wait", target="finish", outcome="expired"))
    bindings = (
        [
            GraphBinding(
                step="wait",
                target_port="correlation_key",
                target_schema={
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 512,
                    "not": {"type": "null"},
                },
                source_kind="REQUEST",
                source_path="/correlation_key",
                source_schema={
                    "type": "object",
                    "properties": {"correlation_key": {"type": "string"}},
                },
            )
        ]
        if wait_code == "EVENT_WAIT"
        else []
    )
    graph = GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
            GraphStep(
                key="wait",
                type_code=wait_code,
                type_version_ref=refs[(wait_code, 1)],
                config=wait_config,
                display_order=1,
            ),
            GraphStep(
                key="finish",
                type_code="FINISH",
                type_version_ref=refs[("FINISH", 1)],
                display_order=2,
            ),
        ],
        bindings=bindings,
        transitions=transitions,
    )
    if client_branches:
        graph.steps.extend(
            [
                GraphStep(
                    key=key,
                    type_code="FINISH",
                    type_version_ref=refs[("FINISH", 1)],
                    display_order=index,
                )
                for index, key in enumerate(("desktop", "second", "android"), start=3)
            ]
        )
        graph.transitions.extend(
            [
                GraphTransition(
                    source="wait",
                    target="desktop",
                    outcome="received",
                    priority=30,
                    condition='client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)',
                ),
                GraphTransition(
                    source="wait",
                    target="second",
                    outcome="received",
                    priority=20,
                    condition='client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)',
                ),
                GraphTransition(
                    source="wait",
                    target="android",
                    outcome="received",
                    priority=10,
                    condition='client.kind == "ANDROID"',
                ),
            ]
        )
    try:
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph)
    except ValidationDetailsException as exc:
        pytest.fail(f"wait graph rejected: {exc.issues}")
    await workflows.publish(create_ref_id(version.id, version.version), actor.id)
    requests = RequestService(session)
    request_type = await requests.create_type(
        RequestTypeCreateDTO(
            code=f"WQ{uuid7().hex}",
            name=f"{wait_code} request",
            workflow_ref_id=create_ref_id(root.id, root.version),
            form_ref_id=create_ref_id(form.id, form.version),
        )
    )
    draft, _ = await requests.create_draft(
        BusinessRequestCreateDTO(
            request_type_ref_id=create_ref_id(request_type.id, request_type.version),
            data={"amount": "1", "correlation_key": correlation_key},
        ),
        actor,
        client_context,
    )
    submitted, _ = await requests.submit(
        create_ref_id(draft.id, draft.version),
        BusinessRequestSubmitDTO(submit_key=f"wait-{uuid7()}"),
        actor,
        client_context,
    )
    process = (
        await session.exec(
            select(ProcessInstanceEntity).where(
                ProcessInstanceEntity.business_request_id == submitted.id
            )
        )
    ).one()
    return process, correlation_key


@pytest.mark.anyio
async def test_process_events_are_atomic_ordered_immutable_and_project_all_positions() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"timeline-{uuid7().hex}", hashed_password="hash")
        outsider = UserEntity(username=f"timeline-outsider-{uuid7().hex}", hashed_password="hash")
        session.add_all([actor, outsider])
        await session.flush()
        process, _ = await _start_waiting_process(session, actor, "TIMER")
        with audit_context(request_id="request-bpms-014", trace_id="trace-bpms-014"):
            await ProcessEventService(session).append(
                process.id, "process.paused", payload={"status": "correlated"}
            )
        await session.commit()
        process_id, actor_id, outsider_id = process.id, actor.id, outsider.id

    async def append_pause(marker: int) -> None:
        async with SessionFactory() as concurrent, concurrent.begin():
            await ProcessEventService(concurrent).append(
                process_id,
                "process.paused",
                actor_user_id=actor_id,
                payload={"status": "WAITING", "secret": f"hidden-{marker}"},
            )

    async with create_task_group() as group:
        group.start_soon(append_pause, 1)
        group.start_soon(append_pause, 2)

    async with SessionFactory() as session:
        for marker in range(200):
            await ProcessEventService(session).append(
                process_id,
                "process.paused",
                actor_user_id=actor_id,
                payload={"status": f"sample-{marker}"},
            )
        await session.commit()
        before = (
            await session.exec(
                select(func.count())
                .select_from(ProcessEventEntity)
                .where(ProcessEventEntity.process_instance_id == process_id)
            )
        ).one()
        await ProcessEventService(session).append(
            process_id, "process.paused", payload={"status": "rolled-back"}
        )
        await session.rollback()
        after = (
            await session.exec(
                select(func.count())
                .select_from(ProcessEventEntity)
                .where(ProcessEventEntity.process_instance_id == process_id)
            )
        ).one()
        assert after == before

        stored_process = await session.get(ProcessInstanceEntity, process_id)
        outsider = await session.get(UserEntity, outsider_id)
        assert stored_process is not None
        assert outsider is not None
        with pytest.raises(NotFoundException):
            await authorized(
                ProcessService(session),
                create_ref_id(stored_process.id, stored_process.version),
                outsider,
                control=False,
            )
        events = list(
            (
                await session.exec(
                    select(ProcessEventEntity)
                    .where(ProcessEventEntity.process_instance_id == process_id)
                    .order_by(col(ProcessEventEntity.sequence))
                )
            ).all()
        )
        assert [row.sequence for row in events] == list(range(1, len(events) + 1))
        assert all("secret" not in row.public_payload for row in events)
        correlated = next(row for row in events if row.request_id == "request-bpms-014")
        assert correlated.trace_id == "trace-bpms-014"

        live_token = (
            await session.exec(
                select(ExecutionTokenEntity).where(
                    ExecutionTokenEntity.process_instance_id == process_id,
                    ExecutionTokenEntity.status == "WAITING",
                )
            )
        ).one()
        session.add(
            ExecutionTokenEntity(
                process_instance_id=process_id,
                current_step_id=live_token.current_step_id,
                status="FAILED",
            )
        )
        await session.flush()
        timeline = await ProcessTimelineService(session).get(
            stored_process, ProcessTimelineQueryDTO(page=1, size=5)
        )
        later_page = await ProcessTimelineService(session).get(
            stored_process, ProcessTimelineQueryDTO(page=3, size=25)
        )
        assert len(timeline.current_positions) == 2
        assert timeline.events.total == len(events)
        assert timeline.events.items == sorted(
            timeline.events.items, key=lambda item: item.sequence
        )
        assert [item.sequence for item in later_page.events.items] == list(
            range(51, min(76, len(events) + 1))
        )
        assert all(step.executions or step.path_status == "not_reached" for step in timeline.steps)

        with pytest.raises(DBAPIError, match="append-only"):
            await session.exec(
                update(ProcessEventEntity)
                .where(col(ProcessEventEntity.id) == events[0].id)
                .values(event_type="process.cancelled")
            )
            await session.flush()
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_event_wait_consumes_once_and_beats_claimed_deadline() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"event-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        process, correlation_key = await _start_waiting_process(session, actor, "EVENT_WAIT")
        execution = (
            await session.exec(
                select(StepExecutionEntity).where(
                    StepExecutionEntity.process_instance_id == process.id,
                    StepExecutionEntity.status == "WAITING",
                )
            )
        ).one()
        subscription = (
            await session.exec(
                select(EventSubscriptionEntity).where(
                    EventSubscriptionEntity.step_execution_id == execution.id
                )
            )
        ).one()
        deadline = (
            await session.exec(
                select(ScheduledActionEntity).where(
                    ScheduledActionEntity.step_execution_id == execution.id
                )
            )
        ).one()
        assert process.status == "WAITING" and subscription.status == "ACTIVE"
        assert subscription.correlation_hash != correlation_key
        deadline.due_at = get_datetime_utc() - timedelta(seconds=1)
        await session.commit()
        process_id, subscription_id, deadline_id = process.id, subscription.id, deadline.id

    timer_owner = uuid7()
    assert deadline_id in await claim_due_actions(timer_owner)
    async with SessionFactory() as session:
        messages = (
            await session.exec(
                select(TaskOutboxEntity).where(
                    TaskOutboxEntity.task_name == "bpms.fire_scheduled_action"
                )
            )
        ).all()
        assert any(item.kwargs.get("action_id") == str(deadline_id) for item in messages)
    delivery_key = f"provider-{uuid7()}"
    async with SessionFactory() as session:
        result = await ProcessWaitService(session).deliver_event(
            "payment.received",
            correlation_key,
            delivery_key,
            "received",
            {"amount": 42},
            source="test_message_adapter",
        )
        await session.commit()
        assert result == "consumed"

    assert not await fire_claimed_action(deadline_id, timer_owner)
    async with SessionFactory() as session:
        assert (
            await ProcessWaitService(session).deliver_event(
                "payment.received",
                correlation_key,
                delivery_key,
                "received",
                {"amount": 42},
                source="test_message_adapter",
            )
        ) == "duplicate"
        assert (
            await ProcessWaitService(session).deliver_event(
                "payment.received",
                correlation_key,
                f"provider-late-{uuid7()}",
                "received",
                {},
                source="test_message_adapter",
            )
        ) == "late_ignored"
        stored_process = await session.get(ProcessInstanceEntity, process_id)
        stored_subscription = await session.get(EventSubscriptionEntity, subscription_id)
        stored_deadline = await session.get(ScheduledActionEntity, deadline_id)
        assert stored_process is not None and stored_process.status == "COMPLETED"
        assert stored_subscription is not None and stored_subscription.status == "CONSUMED"
        assert stored_subscription.delivery_source == "test_message_adapter"
        assert stored_deadline is not None and stored_deadline.status == "CANCELLED"
    await engine.dispose()


@pytest.mark.anyio
async def test_timer_wait_recovers_expired_lease_and_fires_once() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"timer-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        process, _ = await _start_waiting_process(session, actor, "TIMER")
        execution = (
            await session.exec(
                select(StepExecutionEntity).where(
                    StepExecutionEntity.process_instance_id == process.id,
                    StepExecutionEntity.status == "WAITING",
                )
            )
        ).one()
        action = (
            await session.exec(
                select(ScheduledActionEntity).where(
                    ScheduledActionEntity.step_execution_id == execution.id
                )
            )
        ).one()
        action.due_at = get_datetime_utc() - timedelta(seconds=1)
        await session.commit()
        process_id, action_id = process.id, action.id

    abandoned_owner, replacement_owner = uuid7(), uuid7()
    assert action_id in await claim_due_actions(abandoned_owner, lease_seconds=1)
    async with SessionFactory() as session:
        action = await session.get(ScheduledActionEntity, action_id)
        assert action is not None
        action.lease_until = get_datetime_utc() - timedelta(seconds=1)
        await session.commit()
    assert action_id in await claim_due_actions(replacement_owner)
    async with SessionFactory() as session:
        messages = (
            await session.exec(
                select(TaskOutboxEntity).where(
                    TaskOutboxEntity.task_name == "bpms.fire_scheduled_action"
                )
            )
        ).all()
        matching = [item for item in messages if item.kwargs.get("action_id") == str(action_id)]
        assert len(matching) == 2
    assert not await fire_claimed_action(action_id, abandoned_owner)
    assert await fire_claimed_action(action_id, replacement_owner)
    assert action_id not in await claim_due_actions(uuid7())

    async with SessionFactory() as session:
        action = await session.get(ScheduledActionEntity, action_id)
        process = await session.get(ProcessInstanceEntity, process_id)
        assert action is not None and action.status == "FIRED" and action.attempts == 2
        assert process is not None and process.status == "COMPLETED"
    await engine.dispose()


@pytest.mark.anyio
async def test_event_registration_rolls_back_atomically_and_cancel_closes_waits() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"rollback-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        rolled_back, _ = await _start_waiting_process(session, actor, "EVENT_WAIT")
        rolled_back_id = rolled_back.id
        subscription_id = (
            await session.exec(
                select(EventSubscriptionEntity.id)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.id) == col(EventSubscriptionEntity.step_execution_id),
                )
                .where(StepExecutionEntity.process_instance_id == rolled_back.id)
            )
        ).one()
        await session.rollback()
    async with SessionFactory() as session:
        assert await session.get(ProcessInstanceEntity, rolled_back_id) is None
        assert await session.get(EventSubscriptionEntity, subscription_id) is None

        actor = UserEntity(username=f"cancel-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        process, _ = await _start_waiting_process(session, actor, "EVENT_WAIT")
        process_ref = create_ref_id(process.id, process.version)
        process_id = process.id
        await session.commit()

    async with SessionFactory() as session:
        await ProcessService(session).command(process_ref, "cancel", "cancel-wait")
        await session.commit()
    async with SessionFactory() as session:
        process = await session.get(ProcessInstanceEntity, process_id)
        subscriptions = (
            await session.exec(
                select(EventSubscriptionEntity)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.id) == col(EventSubscriptionEntity.step_execution_id),
                )
                .where(StepExecutionEntity.process_instance_id == process_id)
            )
        ).all()
        actions = (
            await session.exec(
                select(ScheduledActionEntity)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.id) == col(ScheduledActionEntity.step_execution_id),
                )
                .where(StepExecutionEntity.process_instance_id == process_id)
            )
        ).all()
        assert process is not None and process.status == "CANCELLED"
        assert {item.status for item in subscriptions} == {"CANCELLED"}
        assert {item.status for item in actions} == {"CANCELLED"}
    await engine.dispose()


@pytest.mark.anyio
async def test_exhausted_timer_delivery_fails_the_waiting_process() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"exhausted-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        process, _ = await _start_waiting_process(session, actor, "TIMER")
        execution = (
            await session.exec(
                select(StepExecutionEntity).where(
                    StepExecutionEntity.process_instance_id == process.id,
                    StepExecutionEntity.status == "WAITING",
                )
            )
        ).one()
        action = (
            await session.exec(
                select(ScheduledActionEntity).where(
                    ScheduledActionEntity.step_execution_id == execution.id
                )
            )
        ).one()
        action.due_at = get_datetime_utc() - timedelta(seconds=1)
        action.attempts = action.max_attempts
        await session.commit()
        process_id, action_id = process.id, action.id

    assert action_id not in await claim_due_actions(uuid7())
    async with SessionFactory() as session:
        action = await session.get(ScheduledActionEntity, action_id)
        messages = (
            await session.exec(
                select(TaskOutboxEntity).where(
                    TaskOutboxEntity.task_name == "bpms.fail_scheduled_action"
                )
            )
        ).all()
        assert action is not None and action.status == "FAILED"
        assert any(item.kwargs.get("action_id") == str(action_id) for item in messages)
    assert await fail_scheduled_action(action_id)
    async with SessionFactory() as session:
        process = await session.get(ProcessInstanceEntity, process_id)
        assert process is not None and process.status == "FAILED"
        assert process.last_error_code == "scheduled_action.retry_exhausted"
    await engine.dispose()


@pytest.mark.anyio
async def test_runtime_executes_once_and_invalid_resume_never_advances() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"process-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        form, form_version = await _published_form(session, actor)
        form_ref = create_ref_id(form_version.id, form_version.version)
        refs = await _step_refs(session)
        workflows = WorkflowService(session, builtin_registry())

        root = await workflows.create(
            WorkflowCreateDTO(code=f"PX{uuid7().hex}", name="Transform process"), actor.id
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                GraphStep(
                    key="convert",
                    type_code="TRANSFORM",
                    type_version_ref=refs[("TRANSFORM", 2)],
                    config={"conversion_key": "integer"},
                    display_order=1,
                ),
                GraphStep(
                    key="finish",
                    type_code="FINISH",
                    type_version_ref=refs[("FINISH", 1)],
                    display_order=2,
                ),
            ],
            bindings=[
                GraphBinding(
                    step="convert",
                    target_port="value",
                    target_schema={"type": ["string", "integer"]},
                    source_kind="REQUEST",
                    source_path="/amount",
                    source_schema={
                        "type": "object",
                        "properties": {"amount": {"type": "string"}},
                    },
                )
            ],
            transitions=[
                GraphTransition(source="start", target="convert", outcome="next", is_default=True),
                GraphTransition(source="convert", target="finish", outcome="next", is_default=True),
            ],
        )
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph)
        published = await workflows.publish(create_ref_id(version.id, version.version), actor.id)

        requests = RequestService(session)
        request_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"PR{uuid7().hex}",
                name="Transform request",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "42"},
            ),
            actor,
        )
        request_ref = create_ref_id(draft.id, draft.version)
        completed, _ = await requests.submit(
            request_ref, BusinessRequestSubmitDTO(submit_key="run-once"), actor
        )
        replay, _ = await requests.submit(
            request_ref, BusinessRequestSubmitDTO(submit_key="run-once"), actor
        )
        assert completed.status == replay.status == "COMPLETED"
        processes = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == completed.id
                )
            )
        ).all()
        assert len(processes) == 1
        executions = (
            await session.exec(
                select(StepExecutionEntity)
                .where(StepExecutionEntity.process_instance_id == processes[0].id)
                .order_by(col(StepExecutionEntity.created_at))
            )
        ).all()
        assert [item.status for item in executions] == ["COMPLETED"] * 3
        assert executions[1].input_snapshot == {"value": "42"}
        assert executions[1].output_snapshot == {"result": 42}
        assert (
            await session.exec(
                select(func.count())
                .select_from(ProcessTransitionEntity)
                .where(ProcessTransitionEntity.process_instance_id == processes[0].id)
            )
        ).one() == 2

        wait_root = await workflows.create(
            WorkflowCreateDTO(code=f"PW{uuid7().hex}", name="Human wait"), actor.id
        )
        wait_version = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(wait_root.id, wait_root.version), number=1
            )
        )
        wait_graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                GraphStep(
                    key="review",
                    type_code="HUMAN_TASK",
                    type_version_ref=refs[("HUMAN_TASK", 1)],
                    form_ref=form_ref,
                    field_policy={
                        "read": ["/properties/amount"],
                        "write": ["/properties/amount"],
                        "required": ["/properties/amount"],
                        "hidden": [],
                    },
                    display_order=1,
                ),
                GraphStep(
                    key="finish",
                    type_code="FINISH",
                    type_version_ref=refs[("FINISH", 1)],
                    display_order=2,
                ),
            ],
            targets=[GraphTarget(step="review", user_ref=create_ref_id(actor.id, actor.version))],
            transitions=[
                GraphTransition(source="start", target="review", outcome="next", is_default=True),
                GraphTransition(
                    source="review", target="finish", outcome="approve", is_default=True
                ),
            ],
        )
        await workflows.replace_graph(
            create_ref_id(wait_version.id, wait_version.version), wait_graph
        )
        wait_published = await workflows.publish(
            create_ref_id(wait_version.id, wait_version.version), actor.id
        )
        wait_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"WR{uuid7().hex}",
                name="Human request",
                workflow_ref_id=create_ref_id(wait_root.id, wait_root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        waiting_request, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(wait_type.id, wait_type.version),
                data={"amount": "7"},
            ),
            actor,
        )
        waiting_request, _ = await requests.submit(
            create_ref_id(waiting_request.id, waiting_request.version),
            BusinessRequestSubmitDTO(submit_key="wait-once"),
            actor,
        )
        waiting_process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == waiting_request.id
                )
            )
        ).one()
        assert waiting_process.status == "WAITING"
        with pytest.raises(VersionConflictException, match="output"):
            await ProcessService(session).resume(
                create_ref_id(waiting_process.id, waiting_process.version),
                "bad-resume",
                "approve",
                {},
            )
        assert waiting_process.status == "FAILED"
        transition_count = (
            await session.exec(
                select(func.count())
                .select_from(ProcessTransitionEntity)
                .where(ProcessTransitionEntity.process_instance_id == waiting_process.id)
            )
        ).one()
        assert transition_count == 1
        attempts = (
            await session.exec(
                select(StepExecutionAttemptEntity)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.id)
                    == col(StepExecutionAttemptEntity.step_execution_id),
                )
                .where(StepExecutionEntity.process_instance_id == waiting_process.id)
            )
        ).all()
        assert attempts[-1].error_code == "handler.output.invalid"
        assert published.id != wait_published.id
        race_request, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "99"},
            ),
            actor,
        )
        race_ref = create_ref_id(race_request.id, race_request.version)
        race_id = race_request.id
        actor_id = actor.id
        await session.commit()

    async def submit_once() -> None:
        async with SessionFactory() as session:
            actor = await session.get(UserEntity, actor_id)
            assert actor is not None
            await RequestService(session).submit(
                race_ref, BusinessRequestSubmitDTO(submit_key="concurrent-start"), actor
            )
            await session.commit()

    async with create_task_group() as tasks:
        tasks.start_soon(submit_once)
        tasks.start_soon(submit_once)

    async with SessionFactory() as session:
        assert (
            await session.exec(
                select(func.count())
                .select_from(ProcessInstanceEntity)
                .where(ProcessInstanceEntity.business_request_id == race_id)
            )
        ).one() == 1
    await engine.dispose()


@pytest.mark.anyio
async def test_parallel_join_and_compensation_are_durable_and_idempotent() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"advanced-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        form, _ = await _published_form(session, actor)
        refs = await _step_refs(session)
        workflows = WorkflowService(session, builtin_registry())
        root = await workflows.create(
            WorkflowCreateDTO(code=f"PA{uuid7().hex}", name="Parallel process"), actor.id
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        correlations = {"left": f"left-{uuid7()}", "right": f"right-{uuid7()}"}
        graph = GraphSnapshot(
            steps=[
                GraphStep(
                    key="start",
                    type_code="START",
                    type_version_ref=refs[("START", 1)],
                    flow=GraphFlow(split="ALL"),
                ),
                GraphStep(
                    key="left",
                    type_code="EVENT_WAIT",
                    type_version_ref=refs[("EVENT_WAIT", 1)],
                    config={"event_type": "branch.left"},
                    flow=GraphFlow(compensation_step="undo"),
                    display_order=1,
                ),
                GraphStep(
                    key="right",
                    type_code="EVENT_WAIT",
                    type_version_ref=refs[("EVENT_WAIT", 1)],
                    config={"event_type": "branch.right"},
                    flow=GraphFlow(compensation_step="undo"),
                    display_order=2,
                ),
                GraphStep(
                    key="finish",
                    type_code="FINISH",
                    type_version_ref=refs[("FINISH", 1)],
                    flow=GraphFlow(join="ALL"),
                    display_order=3,
                ),
                GraphStep(
                    key="undo",
                    type_code="TRANSFORM",
                    type_version_ref=refs[("TRANSFORM", 2)],
                    config={"conversion_key": "string"},
                    flow=GraphFlow(compensation_only=True),
                    display_order=4,
                ),
            ],
            bindings=[
                GraphBinding(
                    step=key,
                    target_port="correlation_key",
                    target_schema={
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 512,
                        "not": {"type": "null"},
                    },
                    source_kind="CONSTANT",
                    constant_value=correlations[key],
                )
                for key in ("left", "right")
            ]
            + [
                GraphBinding(
                    step="undo",
                    target_port="value",
                    target_schema={},
                    source_kind="CONSTANT",
                    constant_value="undo",
                )
            ],
            transitions=[
                GraphTransition(source="start", target="left", outcome="left"),
                GraphTransition(source="start", target="right", outcome="right"),
                GraphTransition(source="left", target="finish", outcome="received"),
                GraphTransition(source="right", target="finish", outcome="received"),
            ],
        )
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph)
        await workflows.publish(create_ref_id(version.id, version.version), actor.id)
        requests = RequestService(session)
        request_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"PAR{uuid7().hex}",
                name="Parallel request",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "1"},
            ),
            actor,
        )
        waiting, _ = await requests.submit(
            create_ref_id(draft.id, draft.version),
            BusinessRequestSubmitDTO(submit_key="parallel"),
            actor,
        )
        process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == waiting.id
                )
            )
        ).one()
        assert process.status == "WAITING"
        process_id = process.id
        await session.commit()

        deliveries: list[str] = []

        async def deliver(event_type: str, correlation_key: str) -> None:
            async with SessionFactory() as delivery_session:
                result = await ProcessWaitService(delivery_session).deliver_event(
                    event_type,
                    correlation_key,
                    f"delivery-{event_type}-{uuid7()}",
                    "received",
                    {},
                    source="concurrency-test",
                )
                await delivery_session.commit()
                deliveries.append(result)

        async with create_task_group() as tasks:
            tasks.start_soon(deliver, "branch.left", correlations["left"])
            tasks.start_soon(deliver, "branch.right", correlations["right"])
        assert sorted(deliveries) == ["consumed", "consumed"]
        process = await session.get(ProcessInstanceEntity, process_id, populate_existing=True)
        assert process is not None and process.status == "COMPLETED"
        events = (
            await session.exec(
                select(ProcessEventEntity).where(
                    ProcessEventEntity.process_instance_id == process.id,
                    ProcessEventEntity.event_type == "join.released",
                )
            )
        ).all()
        assert len(events) == 1
        records = list(
            (
                await session.exec(
                    select(CompensationRecordEntity)
                    .where(CompensationRecordEntity.process_instance_id == process.id)
                    .order_by(col(CompensationRecordEntity.ordinal).desc())
                )
            ).all()
        )
        assert [record.ordinal for record in records] == [2, 1]

        process.status = "FAILED"
        process.ended_at = get_datetime_utc()
        compensation = CompensationService(session)
        first = await compensation.begin(process.id, "compensate-1", actor.id)
        assert first is not None and first.ordinal == 2
        await compensation.fail(first.id, "provider.reversal_failed")
        assert process.status == "COMPENSATION_FAILED"
        await compensation.retry_failed(first.id)
        first = await compensation.begin(process.id, "compensate-retry", actor.id)
        assert first is not None and first.ordinal == 2
        await session.commit()

        await execute_compensation(first.id)
        await execute_compensation(first.id)
        records = list(
            (
                await session.exec(
                    select(CompensationRecordEntity)
                    .where(CompensationRecordEntity.process_instance_id == process_id)
                    .order_by(col(CompensationRecordEntity.ordinal).desc())
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
        first, second = records
        assert first.status == "COMPLETED" and second.status == "RUNNING"
        await execute_compensation(second.id)
        process = await session.get(ProcessInstanceEntity, process_id, populate_existing=True)
        assert process is not None
        assert process.status == "COMPENSATED"
        await session.refresh(second)
        assert [record.status for record in records] == ["COMPLETED", "COMPLETED"]

        cancel_draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "2"},
            ),
            actor,
        )
        waiting_cancel, _ = await requests.submit(
            create_ref_id(cancel_draft.id, cancel_draft.version),
            BusinessRequestSubmitDTO(submit_key=f"cancel-{uuid7()}"),
            actor,
        )
        cancel_process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == waiting_cancel.id
                )
            )
        ).one()
        await ProcessService(session).command(
            create_ref_id(cancel_process.id, cancel_process.version),
            "cancel",
            "cancel-parallel",
            actor.id,
        )
        cancel_tokens = list(
            (
                await session.exec(
                    select(ExecutionTokenEntity).where(
                        ExecutionTokenEntity.process_instance_id == cancel_process.id
                    )
                )
            ).all()
        )
        assert cancel_process.status == "CANCELLED"
        assert {token.status for token in cancel_tokens} == {"CANCELLED"}
        await session.rollback()
    await engine.dispose()


class _SuccessfulProvider:
    def validate(self, provider, kind, config) -> None:
        assert (provider, kind, config.endpoint_key) == ("https_status", "SERVICE", "probe")

    async def invoke(self, pin) -> AdapterResult:
        assert pin.secret_ref == "probe_secret"
        return AdapterResult(status_code=204)


class _FailIfCalledProvider(_SuccessfulProvider):
    @override
    async def invoke(self, pin) -> AdapterResult:
        raise AssertionError("A cancelled attempt must not invoke its provider")


@pytest.mark.anyio
async def test_background_outbox_and_callback_are_atomic_and_idempotent(monkeypatch) -> None:
    from apps.processes.application import automation

    monkeypatch.setitem(
        automation.settings.INTEGRATION_HTTP_ENDPOINTS, "probe", "https://probe.test"
    )
    async with SessionFactory() as session:
        actor = UserEntity(username=f"automation-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        form, _ = await _published_form(session, actor)
        refs = await _step_refs(session)
        connection = IntegrationConnectionEntity(
            code=f"AUTO{uuid7().hex}",
            name="Automation probe",
            provider="https_status",
            kind="SERVICE",
            non_secret_config={"endpoint_key": "probe"},
            secret_ref="probe_secret",
            secret_version="v1",
            verification_status="VERIFIED",
            owner_user_id=actor.id,
        )
        session.add(connection)
        await session.flush()
        workflows = WorkflowService(session, builtin_registry())
        root = await workflows.create(
            WorkflowCreateDTO(code=f"PA{uuid7().hex}", name="Automation"), actor.id
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                GraphStep(
                    key="service",
                    type_code="SERVICE_TASK",
                    type_version_ref=refs[("SERVICE_TASK", 1)],
                    config={
                        "connection_ref": create_ref_id(connection.id, connection.version),
                        "operation_key": "connection.status",
                    },
                    display_order=1,
                ),
                GraphStep(
                    key="finish",
                    type_code="FINISH",
                    type_version_ref=refs[("FINISH", 1)],
                    display_order=2,
                ),
            ],
            bindings=[
                GraphBinding(
                    step="service",
                    target_port="payload",
                    target_schema={
                        "$defs": {"JsonValue": {}},
                        "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                        "type": "object",
                        "not": {"type": "null"},
                    },
                    source_kind="CONSTANT",
                    constant_value={"probe": True},
                    source_schema={"type": "object"},
                )
            ],
            transitions=[
                GraphTransition(source="start", target="service", outcome="next", is_default=True),
                GraphTransition(source="service", target="finish", outcome="next", is_default=True),
            ],
        )
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph)
        await workflows.publish(create_ref_id(version.id, version.version), actor.id)
        requests = RequestService(session)
        request_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"AR{uuid7().hex}",
                name="Automation request",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        request, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "1"},
                priority=8,
            ),
            actor,
        )
        rolled_back, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "2"},
                priority=3,
            ),
            actor,
        )
        await session.commit()
        outbox_before_rollback = (
            await session.exec(select(func.count()).select_from(TaskOutboxEntity))
        ).one()

    async with SessionFactory() as session:
        rollback_actor = await session.get(UserEntity, actor.id)
        assert rollback_actor is not None
        await RequestService(session).submit(
            create_ref_id(rolled_back.id, rolled_back.version),
            BusinessRequestSubmitDTO(submit_key="roll-back"),
            rollback_actor,
        )
        await session.rollback()
    async with SessionFactory() as session:
        assert (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == rolled_back.id
                )
            )
        ).one_or_none() is None
        assert (
            await session.exec(select(func.count()).select_from(TaskOutboxEntity))
        ).one() == outbox_before_rollback

    async with SessionFactory() as session:
        committed_actor = await session.get(UserEntity, actor.id)
        committed_request = await session.get(type(request), request.id)
        assert committed_actor is not None and committed_request is not None
        request, _ = await RequestService(session).submit(
            create_ref_id(committed_request.id, committed_request.version),
            BusinessRequestSubmitDTO(submit_key="automate"),
            committed_actor,
        )
        attempt = (
            await session.exec(
                select(StepExecutionAttemptEntity)
                .where(col(StepExecutionAttemptEntity.automation_snapshot).is_not(None))
                .order_by(col(StepExecutionAttemptEntity.started_at).desc())
            )
        ).first()
        assert attempt is not None and attempt.status == "WAITING"
        message = (
            await session.exec(
                select(TaskOutboxEntity).where(TaskOutboxEntity.task_id == str(attempt.id))
            )
        ).one()
        assert message.kwargs == {"attempt_id": str(attempt.id)}
        assert message.headers["idempotency_key"] == str(attempt.id)
        assert message.priority > 0 and request.priority == 8
        assert "probe_secret" not in str(message.kwargs) + str(message.headers)
        await session.commit()

    completed = await execute_background(attempt.id, _SuccessfulProvider())
    duplicate = await execute_background(attempt.id, _SuccessfulProvider())
    assert completed.disposition == "completed"
    assert duplicate.disposition == "duplicate"
    async with SessionFactory() as session:
        stored = await session.get(StepExecutionAttemptEntity, attempt.id)
        process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == request.id
                )
            )
        ).one()
        assert stored is not None and stored.status == "SUCCEEDED"
        assert process.status == "COMPLETED"

        cancel_actor = await session.get(UserEntity, actor.id)
        cancel_type = await session.get(type(request_type), request_type.id)
        assert cancel_actor is not None and cancel_type is not None
        cancel_request, _ = await RequestService(session).create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(cancel_type.id, cancel_type.version),
                data={"amount": "3"},
            ),
            cancel_actor,
        )
        cancel_request, _ = await RequestService(session).submit(
            create_ref_id(cancel_request.id, cancel_request.version),
            BusinessRequestSubmitDTO(submit_key="cancel-background"),
            cancel_actor,
        )
        cancel_process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == cancel_request.id
                )
            )
        ).one()
        cancel_attempt = (
            await session.exec(
                select(StepExecutionAttemptEntity)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.id)
                    == col(StepExecutionAttemptEntity.step_execution_id),
                )
                .where(
                    StepExecutionEntity.process_instance_id == cancel_process.id,
                    col(StepExecutionAttemptEntity.automation_snapshot).is_not(None),
                )
            )
        ).one()
        await ProcessService(session).command(
            create_ref_id(cancel_process.id, cancel_process.version),
            "cancel",
            "cancel-once",
        )
        await session.commit()

    late = await execute_background(cancel_attempt.id, _FailIfCalledProvider())
    assert late.disposition == "late_ignored"
    await engine.dispose()


class _NotificationProvider:
    def __init__(self, *results: DeliveryResult | Exception) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, str]] = []

    async def deliver(
        self, pin, *, destination, subject, content, idempotency_key
    ) -> DeliveryResult:
        self.calls.append((destination, idempotency_key))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.anyio
async def test_notifications_are_atomic_owned_retryable_and_idempotent() -> None:
    settings.INTEGRATION_HTTP_ENDPOINTS["approved"] = "https://notification.example.test/send"
    async with SessionFactory() as session:
        actor = UserEntity(
            username=f"notification-owner-{uuid7().hex}",
            email=f"owner-{uuid7().hex}@example.test",
            hashed_password="hash",
        )
        recipient = UserEntity(
            username=f"notification-recipient-{uuid7().hex}",
            email=f"recipient-{uuid7().hex}@example.test",
            hashed_password="hash",
        )
        outsider = UserEntity(
            username=f"notification-outsider-{uuid7().hex}", hashed_password="hash"
        )
        session.add_all([actor, recipient, outsider])
        await session.flush()
        connection = IntegrationConnectionEntity(
            code=f"N{uuid7().hex}",
            name="Notification gateway",
            provider="https_notification",
            kind="NOTIFICATION",
            non_secret_config={"endpoint_key": "approved"},
            secret_ref="notification_gateway",
            secret_version="1",
            status="ACTIVE",
            verification_status="VERIFIED",
            owner_user_id=actor.id,
        )
        session.add(connection)
        await session.flush()
        form, _ = await _published_form(session, actor)
        refs = await _step_refs(session)
        registry = builtin_registry()
        notification_handler = registry.resolve("notification", "2")
        schemas = {
            port.port_key: port.metadata().value_schema for port in notification_handler.ports
        }
        workflows = WorkflowService(session, registry)
        root = await workflows.create(
            WorkflowCreateDTO(code=f"NW{uuid7().hex}", name="Notification process"), actor.id
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                GraphStep(
                    key="notify",
                    type_code="NOTIFICATION",
                    type_version_ref=refs[("NOTIFICATION", 2)],
                    config={
                        "connection_ref": create_ref_id(connection.id, connection.version),
                        "template_key": "workflow.notice",
                        "template_version": "1",
                        "channel": "EMAIL",
                        "locale": "en",
                    },
                    display_order=1,
                ),
                GraphStep(
                    key="finish",
                    type_code="FINISH",
                    type_version_ref=refs[("FINISH", 1)],
                    display_order=2,
                ),
            ],
            bindings=[
                GraphBinding(
                    step="notify",
                    target_port="recipients",
                    target_schema=schemas["recipients"],
                    source_kind="CONSTANT",
                    constant_value=[create_ref_id(recipient.id, recipient.version)],
                ),
                GraphBinding(
                    step="notify",
                    target_port="data",
                    target_schema=schemas["data"],
                    source_kind="CONSTANT",
                    constant_value={"message": "<b>safe message</b>"},
                ),
            ],
            transitions=[
                GraphTransition(source="start", target="notify", outcome="next", is_default=True),
                GraphTransition(source="notify", target="finish", outcome="next", is_default=True),
            ],
        )
        try:
            invalid_graph = graph.model_copy(deep=True)
            invalid_graph.bindings[1].constant_value = {}
            with pytest.raises(ValidationDetailsException) as invalid_template:
                await workflows.replace_graph(
                    create_ref_id(version.id, version.version), invalid_graph
                )
            assert invalid_template.value.issues
            await workflows.replace_graph(create_ref_id(version.id, version.version), graph)
            await workflows.publish(create_ref_id(version.id, version.version), actor.id)
        except ValidationDetailsException as exc:
            pytest.fail(f"notification graph rejected: {exc.issues}")
        request_type = await RequestService(session).create_type(
            RequestTypeCreateDTO(
                code=f"NR{uuid7().hex}",
                name="Notification request",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )

        async def submit(current_session, current_actor, current_request_type, key: str):
            draft, _ = await RequestService(current_session).create_draft(
                BusinessRequestCreateDTO(
                    request_type_ref_id=create_ref_id(
                        current_request_type.id, current_request_type.version
                    ),
                    data={"amount": "1"},
                ),
                current_actor,
            )
            request, _ = await RequestService(current_session).submit(
                create_ref_id(draft.id, draft.version),
                BusinessRequestSubmitDTO(submit_key=key),
                current_actor,
            )
            notification = (
                await current_session.exec(
                    select(NotificationEntity).where(
                        NotificationEntity.business_request_id == request.id
                    )
                )
            ).one()
            delivery = (
                await current_session.exec(
                    select(NotificationDeliveryEntity).where(
                        NotificationDeliveryEntity.notification_id == notification.id
                    )
                )
            ).one()
            process = await current_session.get(
                ProcessInstanceEntity, notification.process_instance_id
            )
            assert process is not None
            return request, process, notification, delivery

        _, process, notification, delivery = await submit(
            session, actor, request_type, f"notification-{uuid7()}"
        )
        outbox = (
            await session.exec(
                select(TaskOutboxEntity).where(
                    TaskOutboxEntity.task_id == f"notification:{delivery.id}"
                )
            )
        ).one()
        assert outbox.kwargs == {"delivery_id": str(delivery.id)}
        assert "@" not in str(outbox.kwargs) + str(outbox.headers)
        assert notification.content == "&lt;b&gt;safe message&lt;/b&gt;"
        assert process.status == "WAITING"
        await session.commit()
        ids = actor.id, recipient.id, outsider.id, connection.id, request_type.id

    adapter = _NotificationProvider(DeliveryResult(status="DELIVERED", provider_message_ref="m-1"))
    assert await deliver_notification(delivery.id, adapter) == "delivered"
    assert await deliver_notification(delivery.id, adapter) == "duplicate"
    assert len(adapter.calls) == 1

    async with SessionFactory() as session:
        actor = await session.get(UserEntity, ids[0])
        recipient = await session.get(UserEntity, ids[1])
        outsider = await session.get(UserEntity, ids[2])
        request_type = await session.get(type(request_type), ids[4])
        stored_process = await session.get(ProcessInstanceEntity, process.id)
        assert actor is not None and recipient is not None and outsider is not None
        assert request_type is not None and stored_process is not None
        assert stored_process.status == "COMPLETED"
        service = NotificationService(session)
        visible = await service.get(create_ref_id(notification.id, notification.version), recipient)
        with pytest.raises(NotAllowedException):
            await service.get(create_ref_id(notification.id, notification.version), outsider)
        await service.mark_read(create_ref_id(visible.id, visible.version), recipient)
        visible.created_at = get_datetime_utc() - timedelta(
            days=settings.NOTIFICATION_RETENTION_DAYS + 1
        )
        assert await service.redact_expired() == 1
        assert visible.status == "EXPIRED" and "safe message" not in (visible.content or "")

        _, retry_process, _, retry_delivery = await submit(
            session, actor, request_type, f"retry-{uuid7()}"
        )
        await session.commit()

    failing = _NotificationProvider(RuntimeError("private provider detail"))
    with pytest.raises(ServiceUnavailableException, match="provider unavailable"):
        await deliver_notification(retry_delivery.id, failing)
    successful = _NotificationProvider(DeliveryResult(status="DELIVERED"))
    assert await deliver_notification(retry_delivery.id, successful) == "delivered"

    async with SessionFactory() as session:
        actor = await session.get(UserEntity, ids[0])
        request_type = await session.get(type(request_type), ids[4])
        connection = await session.get(IntegrationConnectionEntity, ids[3])
        assert actor is not None and request_type is not None and connection is not None
        stored_delivery = await session.get(NotificationDeliveryEntity, retry_delivery.id)
        stored_process = await session.get(ProcessInstanceEntity, retry_process.id)
        assert stored_delivery is not None and stored_delivery.attempt_count == 2
        assert stored_delivery.last_error_code is None
        assert stored_process is not None and stored_process.status == "COMPLETED"

        _, cancel_process, cancel_notification, cancel_delivery = await submit(
            session, actor, request_type, f"cancel-{uuid7()}"
        )
        cancel_notification_id = cancel_notification.id
        cancel_delivery_id = cancel_delivery.id
        await ProcessService(session).command(
            create_ref_id(cancel_process.id, cancel_process.version), "cancel", f"cancel-{uuid7()}"
        )
        await session.commit()

        _, _, rolled_back_notification, rolled_back_delivery = await submit(
            session, actor, request_type, f"rollback-{uuid7()}"
        )
        notification_id, delivery_id = rolled_back_notification.id, rolled_back_delivery.id
        outbox_id = f"notification:{delivery_id}"
        await session.rollback()

    async with SessionFactory() as session:
        cancelled_notification = await session.get(NotificationEntity, cancel_notification_id)
        cancelled_delivery = await session.get(NotificationDeliveryEntity, cancel_delivery_id)
        assert cancelled_notification is not None and cancelled_notification.status == "CANCELLED"
        assert cancelled_delivery is not None and cancelled_delivery.status == "CANCELLED"
        assert await session.get(NotificationEntity, notification_id) is None
        assert await session.get(NotificationDeliveryEntity, delivery_id) is None
        assert (
            await session.exec(
                select(TaskOutboxEntity).where(TaskOutboxEntity.task_id == outbox_id)
            )
        ).one_or_none() is None
        actor = await session.get(UserEntity, ids[0])
        request_type = await session.get(type(request_type), ids[4])
        assert actor is not None and request_type is not None
        _, bounce_process, _, bounce_delivery = await submit(
            session, actor, request_type, f"bounce-{uuid7()}"
        )
        await session.commit()
    assert (
        await deliver_notification(
            bounce_delivery.id, _NotificationProvider(DeliveryResult(status="BOUNCED"))
        )
        == "bounced"
    )

    async with SessionFactory() as session:
        actor = await session.get(UserEntity, ids[0])
        request_type = await session.get(type(request_type), ids[4])
        connection = await session.get(IntegrationConnectionEntity, ids[3])
        assert actor is not None and request_type is not None and connection is not None
        bounced = await session.get(NotificationDeliveryEntity, bounce_delivery.id)
        bounced_process = await session.get(ProcessInstanceEntity, bounce_process.id)
        assert bounced is not None and bounced.status == "BOUNCED"
        assert bounced_process is not None and bounced_process.status == "COMPLETED"

        _, revoked_process, _, revoked_delivery = await submit(
            session, actor, request_type, f"revoked-{uuid7()}"
        )
        connection.status = "REVOKED"
        await session.commit()
    assert await deliver_notification(revoked_delivery.id, _NotificationProvider()) == "failed"

    async with SessionFactory() as session:
        revoked = await session.get(NotificationDeliveryEntity, revoked_delivery.id)
        revoked_process = await session.get(ProcessInstanceEntity, revoked_process.id)
        assert (
            revoked is not None and revoked.last_error_code == "notification.connection.unavailable"
        )
        assert revoked_process is not None and revoked_process.status == "COMPLETED"
    await engine.dispose()


@pytest.mark.anyio
async def test_registered_sync_steps_publish_and_execute_with_scoped_services() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"step-extension-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        registry = get_registry()
        step_service = StepTypeService(session, registry)
        for version in await step_service.reconcile():
            if version.status == "DRAFT" and version.handler_key in {
                "request_priority",
                "permission_check",
            }:
                await step_service.publish(create_ref_id(version.id, version.version))
        refs = await _step_refs(session)
        with use_language("fa"):
            priority_dto = await step_service.detail(refs[("REQUEST_PRIORITY", 1)])
        assert priority_dto.name == "اولویت درخواست"
        assert priority_dto.help_text == "اولویت درخواست جاری را می‌خواند."
        form, _ = await _published_form(session, actor)
        workflows = WorkflowService(session, registry)
        root = await workflows.create(
            WorkflowCreateDTO(
                code=f"WX{uuid7().hex}", name="Extension process", access_mode="OPEN"
            ),
            actor.id,
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                GraphStep(
                    key="priority",
                    type_code="REQUEST_PRIORITY",
                    type_version_ref=refs[("REQUEST_PRIORITY", 1)],
                    display_order=1,
                ),
                GraphStep(
                    key="permission",
                    type_code="PERMISSION_CHECK",
                    type_version_ref=refs[("PERMISSION_CHECK", 1)],
                    config={"permission_key": "workflows.manage"},
                    display_order=2,
                ),
                GraphStep(key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]),
            ],
            transitions=[
                GraphTransition(source="start", target="priority", outcome="next", is_default=True),
                GraphTransition(
                    source="priority", target="permission", outcome="next", is_default=True
                ),
                GraphTransition(
                    source="permission", target="finish", outcome="next", is_default=True
                ),
            ],
        )
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph)
        await workflows.publish(create_ref_id(version.id, version.version), actor.id)
        requests = RequestService(session)
        request_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"EQ{uuid7().hex}",
                name="Extension request",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "1"},
            ),
            actor,
        )
        submitted, _ = await requests.submit(
            create_ref_id(draft.id, draft.version),
            BusinessRequestSubmitDTO(submit_key=f"extension-{uuid7()}"),
            actor,
        )
        process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id
                )
            )
        ).one()
        assert process.status == "COMPLETED"
        outputs = (
            await session.exec(
                select(WorkflowStepEntity.step_key, StepExecutionEntity.output_snapshot)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.workflow_step_id) == col(WorkflowStepEntity.id),
                )
                .where(StepExecutionEntity.process_instance_id == process.id)
            )
        ).all()
        by_step = dict(outputs)
        assert by_step["priority"] == {"priority": submitted.priority}
        assert by_step["permission"] == {"allowed": False}
        from apps.processes.application.extension_services import ProcessStepServices
        from utils.exceptions import VersionConflictException

        wrong_request = ProcessStepServices(
            session, actor_id=actor.id, process_id=process.id, request_id=uuid7()
        )
        with pytest.raises(VersionConflictException, match="scope"):
            await wrong_request.request_priority()
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_registered_background_step_uses_pinned_connection_and_outbox(monkeypatch) -> None:
    from apps.processes.application import automation

    monkeypatch.setitem(
        automation.settings.INTEGRATION_HTTP_ENDPOINTS, "probe", "https://probe.test"
    )
    async with SessionFactory() as session:
        actor = UserEntity(username=f"extension-api-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        registry = get_registry()
        step_service = StepTypeService(session, registry)
        for registered in await step_service.reconcile():
            if registered.handler_key == "connection_status" and registered.status == "DRAFT":
                await step_service.publish(create_ref_id(registered.id, registered.version))
        refs = await _step_refs(session)
        form, _ = await _published_form(session, actor)
        connection = IntegrationConnectionEntity(
            code=f"EXAPI{uuid7().hex}",
            name="Extension API probe",
            provider="https_status",
            kind="SERVICE",
            non_secret_config={"endpoint_key": "probe"},
            secret_ref="probe_secret",
            secret_version="v1",
            verification_status="VERIFIED",
            owner_user_id=actor.id,
        )
        session.add(connection)
        await session.flush()
        workflows = WorkflowService(session, registry)
        root = await workflows.create(
            WorkflowCreateDTO(code=f"AX{uuid7().hex}", name="Extension API"), actor.id
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                GraphStep(
                    key="probe",
                    type_code="CONNECTION_STATUS",
                    type_version_ref=refs[("CONNECTION_STATUS", 1)],
                    config={"connection_ref": create_ref_id(connection.id, connection.version)},
                ),
                GraphStep(key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]),
            ],
            transitions=[
                GraphTransition(source="start", target="probe", outcome="next", is_default=True),
                GraphTransition(source="probe", target="finish", outcome="next", is_default=True),
            ],
        )
        from utils.exceptions import ValidationDetailsException

        with pytest.raises(ValidationDetailsException):
            await workflows.validate_graph(graph, uuid7())
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph, actor.id)
        await workflows.publish(create_ref_id(version.id, version.version), actor.id)
        requests = RequestService(session)
        request_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"AQ{uuid7().hex}",
                name="Extension API request",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "1"},
            ),
            actor,
        )
        await session.commit()

    async with SessionFactory() as session:
        submitted, _ = await RequestService(session).submit(
            create_ref_id(draft.id, draft.version),
            BusinessRequestSubmitDTO(submit_key=f"extension-api-{uuid7()}"),
            actor,
        )
        process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id
                )
            )
        ).one()
        attempt = (
            await session.exec(
                select(StepExecutionAttemptEntity)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.id)
                    == col(StepExecutionAttemptEntity.step_execution_id),
                )
                .where(
                    StepExecutionEntity.process_instance_id == process.id,
                    col(StepExecutionAttemptEntity.automation_snapshot).is_not(None),
                )
            )
        ).one()
        assert attempt.status == "WAITING"
        assert attempt.automation_snapshot is not None
        assert "probe_secret" not in str(
            (
                await session.exec(
                    select(TaskOutboxEntity).where(TaskOutboxEntity.task_id == str(attempt.id))
                )
            )
            .one()
            .kwargs
        )
        await session.commit()
    completed = await execute_background(attempt.id, _SuccessfulProvider())
    duplicate = await execute_background(attempt.id, _SuccessfulProvider())
    assert completed.disposition == "completed"
    assert duplicate.disposition == "duplicate"
    async with SessionFactory() as session:
        execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
        assert execution is not None and execution.output_snapshot == {"status_code": 204}
    await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("approval_mode", ["none", "approve", "deny", "expire", "cancel"])
async def test_ai_decision_reserves_budget_and_routes_unknown_confidence_to_human(
    monkeypatch,
    approval_mode,
) -> None:
    from decimal import Decimal

    from pydantic import SecretStr
    from pydantic_ai.models.test import TestModel

    from apps.ai.application.agent_service import AIAgentService
    from apps.ai.application.budget_service import AIBudgetService
    from apps.ai.domain.agent import AIAgentDraftSpec, AIPrice
    from apps.ai.domain.contracts import AIChoice, AIDecisionContract, AIPermittedData, AITaskLimits
    from apps.ai.domain.entity import AIReservationEntity, AITaskBudgetEntity
    from apps.integrations.application.providers import StatusProvider
    from apps.integrations.application.service import ConnectionService
    from apps.integrations.domain.dto import AIConnectionConfig, ConnectionCreateDTO
    from apps.processes.application import extension_services

    class FakeSecrets:
        def resolve(self, reference: str, version: str) -> SecretStr:
            if (reference, version) != ("ai_secret", "1"):
                raise ValueError("Unavailable")
            return SecretStr("fake-key")

    provider = StatusProvider(FakeSecrets(), {})
    monkeypatch.setattr(
        extension_services,
        "create_model",
        lambda *args, **kwargs: TestModel(custom_output_args={"choice": "bug"}),
    )
    tool_calls = []
    tool_key = f"lookup_{uuid7().hex}"
    if approval_mode != "none":
        from cryptography.fernet import Fernet
        from pydantic_ai.messages import ModelResponse, ToolCallPart
        from pydantic_ai.models.function import FunctionModel

        from apps.ai.application.tools import TrustedAITool, register_trusted_tool
        from core.settings import settings

        monkeypatch.setattr(
            settings, "INTEGRATION_SECRET_KEYS", [SecretStr(Fernet.generate_key().decode())]
        )

        def lookup(record_id: str) -> str:
            tool_calls.append(record_id)
            return "Authorized result"

        register_trusted_tool(
            TrustedAITool(
                key=tool_key,
                version="1",
                description="Approved lookup",
                function=lookup,
                retrieval_source="approved_documents",
            )
        )

        def respond(messages, info):
            if any(
                part.part_kind == "tool-return" for message in messages for part in message.parts
            ):
                return ModelResponse(
                    parts=[ToolCallPart(info.output_tools[0].name, {"choice": "bug"})],
                    model_name="gpt-fake",
                )
            return ModelResponse(
                parts=[ToolCallPart(tool_key, {"record_id": "DOC-1"}, "lookup-1")],
                model_name="gpt-fake",
            )

        monkeypatch.setattr(
            extension_services,
            "create_model",
            lambda *a, **kw: FunctionModel(respond, model_name="gpt-fake"),
        )
    limits = AITaskLimits(
        requests=2 if approval_mode != "none" else 1,
        tool_calls=1 if approval_mode != "none" else 0,
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        elapsed_seconds=30,
        spend_usd=Decimal("0.50"),
        strict_spend=False,
    )
    async with SessionFactory() as session:
        actor = UserEntity(username=f"ai-process-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        step_service = StepTypeService(session, get_registry())
        for registered in await step_service.reconcile():
            if registered.handler_key == "ai_decision" and registered.status == "DRAFT":
                await step_service.publish(create_ref_id(registered.id, registered.version))
        refs = await _step_refs(session)
        form, form_version = await _published_form(session, actor)
        connections = ConnectionService(session, provider)
        connection = await connections.create(
            ConnectionCreateDTO(
                code=f"AI{uuid7().hex}",
                name="AI fake",
                provider="openai",
                kind="AI",
                non_secret_config=AIConnectionConfig(
                    models=["gpt-fake"],
                    provider_retention="Contract checked by operator",
                ),
                secret_ref="ai_secret",
                secret_version="1",
            ),
            actor,
        )
        await connections.verify(create_ref_id(connection.id, connection.version), actor)
        agents = AIAgentService(
            session,
            connections,
            admin_limits=limits,
            prices={
                "openai:gpt-fake": AIPrice(
                    version="test-price-1",
                    fixed_per_request_usd=Decimal("0.01"),
                    input_per_million_usd=Decimal(1),
                    output_per_million_usd=Decimal(1),
                )
            },
        )
        draft = await agents.create(
            f"AI{uuid7().hex}",
            "Classify ticket",
            AIAgentDraftSpec(
                connection_ref=create_ref_id(connection.id, connection.version),
                provider_key="openai",
                model_id="gpt-fake",
                prompt_version="1",
                instructions="Classify the ticket into one choice.",
                decision=AIDecisionContract(
                    question="Which area owns this ticket?",
                    options=[
                        AIChoice(key="bug", labels={"en": "Bug"}, description="Product defect"),
                        AIChoice(
                            key="billing", labels={"en": "Billing"}, description="Invoice problem"
                        ),
                    ],
                ),
                data_policy=AIPermittedData(
                    allowed_fields={"ticket"},
                    allowed_classifications={"INTERNAL"},
                    allowed_tools={tool_key} if approval_mode != "none" else set(),
                    allowed_retrieval_sources={"approved_documents"}
                    if approval_mode != "none"
                    else set(),
                ),
                field_classifications={"ticket": "INTERNAL"},
                user_limits=limits,
            ),
            actor,
        )
        published = await agents.publish(create_ref_id(draft.id, draft.version), actor)
        workflows = WorkflowService(session, get_registry())
        root = await workflows.create(
            WorkflowCreateDTO(code=f"AIW{uuid7().hex}", name="AI review process"), actor.id
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        data_schema = next(
            port.metadata().value_schema
            for port in get_registry().resolve("ai_decision", "1").ports
            if port.port_key == "data"
        )
        graph = GraphSnapshot(
            steps=[
                GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                GraphStep(
                    key="classify",
                    type_code="AI_DECISION",
                    type_version_ref=refs[("AI_DECISION", 1)],
                    config={"agent_ref": create_ref_id(published.id, published.version)},
                ),
                GraphStep(
                    key="review",
                    type_code="HUMAN_TASK",
                    type_version_ref=refs[("HUMAN_TASK", 1)],
                    form_ref=create_ref_id(form_version.id, form_version.version),
                    field_policy={
                        "read": ["/properties/amount"],
                        "write": ["/properties/amount"],
                        "required": ["/properties/amount"],
                        "hidden": [],
                    },
                ),
                GraphStep(key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]),
            ],
            bindings=[
                GraphBinding(
                    step="classify",
                    target_port="data",
                    target_schema=data_schema,
                    source_kind="CONSTANT",
                    constant_value={"ticket": "Button crashes; password is private"},
                )
            ],
            targets=[GraphTarget(step="review", user_ref=create_ref_id(actor.id, actor.version))],
            transitions=[
                GraphTransition(source="start", target="classify", outcome="next", is_default=True),
                GraphTransition(source="classify", target="review", outcome="review"),
                GraphTransition(
                    source="classify", target="finish", outcome="next", is_default=True
                ),
                GraphTransition(
                    source="review", target="finish", outcome="approve", is_default=True
                ),
            ],
        )
        missing_review = graph.model_copy(
            update={
                "transitions": [
                    edge
                    for edge in graph.transitions
                    if not (edge.source == "classify" and edge.outcome == "review")
                ]
            }
        )
        with pytest.raises(ValidationDetailsException) as missing_review_error:
            await workflows.validate_graph(missing_review, actor.id)
        assert any(
            issue["code"] == "ai.review_handoff.required"
            for issue in missing_review_error.value.issues
        )
        missing_normal = graph.model_copy(
            update={
                "transitions": [
                    edge
                    for edge in graph.transitions
                    if not (edge.source == "classify" and edge.outcome == "next")
                ]
            }
        )
        with pytest.raises(ValidationDetailsException) as missing_normal_error:
            await workflows.validate_graph(missing_normal, actor.id)
        assert any(
            issue["code"] == "ai.normal_handoff.required"
            for issue in missing_normal_error.value.issues
        )
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph, actor.id)
        await workflows.publish(create_ref_id(version.id, version.version), actor.id)
        requests = RequestService(session)
        request_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"AIR{uuid7().hex}",
                name="AI request",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft_request, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "1"},
            ),
            actor,
        )
        await session.commit()
    async with SessionFactory() as session:
        submitted, _ = await RequestService(session).submit(
            create_ref_id(draft_request.id, draft_request.version),
            BusinessRequestSubmitDTO(submit_key=f"ai-{uuid7()}"),
            actor,
        )
        process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id
                )
            )
        ).one()
        budget = (
            await session.exec(
                select(AITaskBudgetEntity)
                .join(StepExecutionEntity)
                .where(StepExecutionEntity.process_instance_id == process.id)
            )
        ).one()
        attempt = (
            await session.exec(
                select(StepExecutionAttemptEntity).where(
                    StepExecutionAttemptEntity.step_execution_id == budget.step_execution_id
                )
            )
        ).one()
        assert attempt.automation_snapshot is not None
        assert (
            attempt.automation_snapshot["ai_decision"]["question"] == "Which area owns this ticket?"
        )
        await session.commit()
    from anyio import create_task_group

    deliveries = []

    async def deliver():
        deliveries.append(await execute_background(attempt.id, provider))

    if approval_mode == "approve":
        async with create_task_group() as group:
            group.start_soon(deliver)
            group.start_soon(deliver)
        assert {entry.disposition for entry in deliveries} <= {
            "waiting_approval",
            "already_dispatched",
        }
        result = next(entry for entry in deliveries if entry.disposition == "waiting_approval")
    else:
        result = await execute_background(attempt.id, provider)
    if approval_mode != "none":
        from apps.ai.application.approval_service import AIToolApprovalService
        from apps.ai.domain.entity import AIToolApprovalEntity
        from apps.work_items.application.service import WorkItemService
        from apps.work_items.presentation.routes import work_item_dto

        assert result.disposition == "waiting_approval"
        assert tool_calls == []
        assert (await execute_background(attempt.id, provider)).disposition == "waiting_approval"
        async with SessionFactory() as session:
            approval = (
                await session.exec(
                    select(AIToolApprovalEntity).where(
                        AIToolApprovalEntity.step_execution_attempt_id == attempt.id
                    )
                )
            ).one()
            assert approval.status == "PENDING"
            assert approval.payload_ciphertext is not None
            assert b"DOC-1" not in approval.payload_ciphertext
            item = await session.get(WorkItemEntity, approval.work_item_id)
            assert item is not None
            work = WorkItemService(session)
            item = await work.claim(create_ref_id(item.id, item.version), "claim-ai", actor)
            dto = await work_item_dto(work, item, actor)
            assert dto.submission_ref_id is None
            from apps.work_items.domain.dto import WorkItemForwardDTO
            from utils.exceptions import NotAllowedException

            outsider = UserEntity(
                username=f"ai-approval-outsider-{uuid7().hex}", hashed_password="hash"
            )
            session.add(outsider)
            await session.flush()
            service = AIToolApprovalService(session)
            with pytest.raises(NotAllowedException):
                await service.decide(
                    create_ref_id(item.id, item.version),
                    outsider,
                    approved=True,
                    command_key="intrusion",
                )
            with pytest.raises(VersionConflictException, match="forward"):
                await work.forward(
                    create_ref_id(item.id, item.version),
                    WorkItemForwardDTO(
                        command_key="forward-ai",
                        reason="Cannot transfer this approval",
                        user_ref_ids=[create_ref_id(outsider.id, outsider.version)],
                    ),
                    actor,
                )
            if approval_mode == "expire":
                from datetime import timedelta

                from utils.date_utils import get_datetime_utc

                approval.expires_at = get_datetime_utc() - timedelta(seconds=1)
                await session.flush()
                assert await service.expire(attempt.id)
                assert not await service.expire(attempt.id)
            elif approval_mode == "cancel":
                process = await session.get(
                    ProcessInstanceEntity, process.id, populate_existing=True
                )
                assert process is not None
                await ProcessService(session).command(
                    create_ref_id(process.id, process.version), "cancel", "cancel-ai", actor.id
                )
            else:
                await service.decide(
                    create_ref_id(item.id, item.version),
                    actor,
                    approved=approval_mode == "approve",
                    command_key="approve-ai",
                )
            await session.commit()
        if approval_mode != "approve":
            assert tool_calls == []
            assert (await execute_background(attempt.id, provider)).disposition == "late_ignored"
            async with SessionFactory() as session:
                terminal = await session.get(AIToolApprovalEntity, approval.id)
                assert terminal is not None
                assert (
                    terminal.status
                    == {"deny": "DENIED", "expire": "EXPIRED", "cancel": "CANCELLED"}[approval_mode]
                )
                assert terminal.payload_ciphertext is None
            await engine.dispose()
            return
        deliveries = []
        async with create_task_group() as group:
            group.start_soon(deliver)
            group.start_soon(deliver)
        assert {entry.disposition for entry in deliveries} <= {
            "completed",
            "duplicate",
            "already_dispatched",
        }
        result = next(entry for entry in deliveries if entry.disposition == "completed")
        assert tool_calls == ["DOC-1"]
        async with SessionFactory() as session:
            stored = await session.get(AIToolApprovalEntity, approval.id)
            assert stored is not None
            assert stored.status == "CONSUMED" and stored.payload_ciphertext is None
    duplicate = await execute_background(attempt.id, provider)
    assert result.disposition == "completed"
    assert duplicate.disposition == "duplicate"
    async with SessionFactory() as session:
        reservation = (
            await session.exec(
                select(AIReservationEntity).where(AIReservationEntity.task_budget_id == budget.id)
            )
        ).all()
        assert len(reservation) == (2 if approval_mode != "none" else 1)
        assert all(row.status == "SETTLED" and row.model_used is not None for row in reservation)
        budget_state = await AIBudgetService(session).status_for_execution(budget.step_execution_id)
        assert budget_state.used.requests == (2 if approval_mode != "none" else 1)
        assert budget_state.remaining.requests == 0
        assert budget_state.price_version == "test-price-1"
        assert not budget_state.unknown_usage
        item = (
            await session.exec(
                select(WorkItemEntity).where(
                    WorkItemEntity.business_request_id == submitted.id,
                    WorkItemEntity.status == "OPEN",
                )
            )
        ).one()
        assert item.status == "OPEN"
    await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("kind", "release", "expected"),
    [
        ("DESKTOP", "2.10", "desktop"),
        ("DESKTOP", "2.9", "finish"),
        ("DESKTOP", "2.10-rc.1", "finish"),
        ("ANDROID", "1.0", "android"),
        ("B2B", None, "finish"),
        (None, None, "finish"),
    ],
)
async def test_client_branch_uses_saved_origin_after_restart(kind, release, expected):
    from apps.clients.domain.contracts import ClientContext

    context = (
        ClientContext(client_id=uuid7(), kind=kind, release=release, trusted=True)
        if kind
        else ClientContext.legacy()
    )
    async with SessionFactory() as session:
        actor = UserEntity(username=f"predicate-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        process, correlation = await _start_waiting_process(
            session, actor, "EVENT_WAIT", context, True
        )
        process_id = process.id
        assert process.status == "WAITING"
        await session.commit()
    # A new worker session has no current HTTP client. It must read the saved origin.
    command = str(uuid7())
    async with SessionFactory() as session:
        assert (
            await ProcessWaitService(session).deliver_event(
                "payment.received", correlation, command, "received", {}, source="test"
            )
            == "consumed"
        )
        await session.commit()
    async with SessionFactory() as session:
        assert (
            await ProcessWaitService(session).deliver_event(
                "payment.received", correlation, command, "received", {}, source="test"
            )
            == "duplicate"
        )
        completed = await session.get(ProcessInstanceEntity, process_id)
        assert completed is not None and completed.status == "COMPLETED"
        events = (
            await session.exec(
                select(ProcessEventEntity).where(
                    ProcessEventEntity.process_instance_id == process_id,
                    ProcessEventEntity.event_type == "transition.taken",
                )
            )
        ).all()
        branch = [
            event.public_payload
            for event in events
            if event.public_payload.get("source_step") == "wait"
        ]
        assert len(branch) == 1
        assert branch[0]["target_step"] == expected
        assert branch[0]["predicate_contract"] == "bpms.predicates/1"
        assert "client" not in branch[0] and "release" not in branch[0]
        await session.commit()
    await engine.dispose()


@pytest.mark.anyio
async def test_two_pinned_subprocess_calls_have_distinct_children_and_resume_once() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"subprocess-run-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        form, _ = await _published_form(session, actor)
        refs = await _step_refs(session)
        workflows = WorkflowService(session, builtin_registry())
        child_root = await workflows.create(
            WorkflowCreateDTO(code=f"SC{uuid7().hex}", name="ManagerApproval"), actor.id
        )
        child = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(child_root.id, child_root.version), number=1
            )
        )
        child = await workflows.replace_graph(
            create_ref_id(child.id, child.version),
            GraphSnapshot(
                interface=SubprocessInterface(outcomes={"approved": "approved_finish"}),
                steps=[
                    GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                    GraphStep(
                        key="approved_finish",
                        type_code="FINISH",
                        type_version_ref=refs[("FINISH", 1)],
                    ),
                ],
                transitions=[
                    GraphTransition(source="start", target="approved_finish", outcome="next")
                ],
            ),
            actor.id,
        )
        child = await workflows.publish(create_ref_id(child.id, child.version), actor.id)
        child_ref = create_ref_id(child.id, child.version)
        parent_root = await workflows.create(
            WorkflowCreateDTO(code=f"SP{uuid7().hex}", name="Two approvals"), actor.id
        )
        parent = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version), number=1
            )
        )
        parent = await workflows.replace_graph(
            create_ref_id(parent.id, parent.version),
            GraphSnapshot(
                steps=[
                    GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                    GraphStep(
                        key="first",
                        type_code="SUBPROCESS",
                        type_version_ref=refs[("SUBPROCESS", 1)],
                        subprocess=SubprocessCall(workflow_version_ref=child_ref),
                    ),
                    GraphStep(
                        key="second",
                        type_code="SUBPROCESS",
                        type_version_ref=refs[("SUBPROCESS", 1)],
                        subprocess=SubprocessCall(workflow_version_ref=child_ref),
                    ),
                    GraphStep(
                        key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                    GraphStep(
                        key="failed", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                ],
                transitions=[
                    GraphTransition(source="start", target="first", outcome="next"),
                    GraphTransition(source="first", target="second", outcome="approved"),
                    GraphTransition(source="first", target="failed", outcome="failure"),
                    GraphTransition(source="second", target="finish", outcome="approved"),
                    GraphTransition(source="second", target="failed", outcome="failure"),
                ],
            ),
            actor.id,
        )
        parent = await workflows.publish(create_ref_id(parent.id, parent.version), actor.id)
        requests = RequestService(session)
        request_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"SQ{uuid7().hex}",
                name="Two approvals request",
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "1"},
            ),
            actor,
        )
        submitted, _ = await requests.submit(
            create_ref_id(draft.id, draft.version),
            BusinessRequestSubmitDTO(submit_key=f"subprocess-{uuid7()}"),
            actor,
        )
        root = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                )
            )
        ).one()
        assert root.status == "WAITING"
        children = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_not(None),
                )
            )
        ).all()
        assert len(children) == 1
        assert children[0].status == "COMPLETED"
        assert children[0].workflow_version_id == child.id
        timeline = await ProcessTimelineService(session).get(root, ProcessTimelineQueryDTO())
        assert len(timeline.children) == 1
        assert timeline.children[0].status == "COMPLETED"
        assert timeline.children[0].parent_execution_ref_id
        parent_service = ProcessService(session)
        first_call = await session.get(StepExecutionEntity, children[0].parent_step_execution_id)
        assert first_call is not None
        call_step = await session.get(WorkflowStepEntity, first_call.workflow_step_id)
        call_token = await session.get(ExecutionTokenEntity, first_call.execution_token_id)
        assert call_step is not None and call_token is not None
        root_request, root_submission = await parent_service._request_context(root)
        assert (
            await SubprocessService(session, parent_service)._start(
                root, call_token, first_call, call_step, root_request, root_submission
            )
        ).id == children[0].id
        outbox = (
            await session.exec(
                select(TaskOutboxEntity).where(
                    TaskOutboxEntity.task_name == "bpms.settle_subprocess",
                )
            )
        ).all()
        assert any(row.kwargs == {"child_id": str(children[0].id)} for row in outbox)
        await session.commit()

        def run_worker() -> str:
            result = subprocess.check_output(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; from apps.tasks.tasks import settle_bpms_subprocess; "
                        "print(settle_bpms_subprocess.run(sys.argv[1])['status'])"
                    ),
                    str(children[0].id),
                ],
                env={**os.environ, "PYTHONPATH": "src"},
                text=True,
            )
            return result.strip()

        worker_results: list[str] = []

        async def deliver() -> None:
            worker_results.append(await to_thread.run_sync(run_worker))

        async with create_task_group() as tasks:
            tasks.start_soon(deliver)
            tasks.start_soon(deliver)
        assert set(worker_results) <= {"completed", "duplicate"}
        assert worker_results.count("completed") <= 1
        session.expire_all()
        await session.refresh(root)
        await session.refresh(submitted)
        await session.refresh(request_type)
        await session.refresh(actor)
        runtime = SubprocessService(session, ProcessService(session))
        children = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_not(None),
                )
            )
        ).all()
        assert len(children) == 2
        assert children[0].parent_step_execution_id != children[1].parent_step_execution_id
        assert await runtime.settle(children[1].id) in {"completed", "duplicate"}
        await session.refresh(root)
        assert root.status == "COMPLETED"
        timeline = await ProcessTimelineService(session).get(root, ProcessTimelineQueryDTO())
        assert len(timeline.children) == 2
        assert len({child.parent_execution_ref_id for child in timeline.children}) == 2
        late_draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": "1"},
            ),
            actor,
        )
        late_request, _ = await requests.submit(
            create_ref_id(late_draft.id, late_draft.version),
            BusinessRequestSubmitDTO(submit_key=f"late-subprocess-{uuid7()}"),
            actor,
        )
        late_parent = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == late_request.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                )
            )
        ).one()
        late_child = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == late_request.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_not(None),
                )
            )
        ).one()
        late_parent.status = "CANCELLED"
        late_parent.ended_at = get_datetime_utc()
        assert await runtime.settle(late_child.id) == "late_ignored"
        assert late_parent.status == "CANCELLED"
        await session.commit()
    await engine.dispose()


@pytest.mark.anyio
async def test_subprocess_timer_wait_uses_existing_scheduler_and_resumes_parent() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"subprocess-timer-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        form, _ = await _published_form(session, actor)
        refs = await _step_refs(session)
        workflows = WorkflowService(session, builtin_registry())
        child_root = await workflows.create(
            WorkflowCreateDTO(code=f"TC{uuid7().hex}", name="Timer child"), actor.id
        )
        child = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(child_root.id, child_root.version),
                number=1,
            )
        )
        child = await workflows.replace_graph(
            create_ref_id(child.id, child.version),
            GraphSnapshot(
                interface=SubprocessInterface(outcomes={"elapsed": "child_finish"}),
                steps=[
                    GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                    GraphStep(
                        key="timer",
                        type_code="TIMER",
                        type_version_ref=refs[("TIMER", 1)],
                        config={"delay_seconds": 1},
                    ),
                    GraphStep(
                        key="child_finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                ],
                transitions=[
                    GraphTransition(source="start", target="timer", outcome="next"),
                    GraphTransition(source="timer", target="child_finish", outcome="elapsed"),
                ],
            ),
            actor.id,
        )
        child = await workflows.publish(create_ref_id(child.id, child.version), actor.id)
        parent_root = await workflows.create(
            WorkflowCreateDTO(
                code=f"TP{uuid7().hex}",
                name="Timer parent",
            ),
            actor.id,
        )
        parent = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version),
                number=1,
            )
        )
        parent = await workflows.replace_graph(
            create_ref_id(parent.id, parent.version),
            GraphSnapshot(
                steps=[
                    GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                    GraphStep(
                        key="call",
                        type_code="SUBPROCESS",
                        type_version_ref=refs[("SUBPROCESS", 1)],
                        subprocess=SubprocessCall(
                            workflow_version_ref=create_ref_id(child.id, child.version)
                        ),
                    ),
                    GraphStep(
                        key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                    GraphStep(
                        key="failed", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                ],
                transitions=[
                    GraphTransition(source="start", target="call", outcome="next"),
                    GraphTransition(source="call", target="finish", outcome="elapsed"),
                    GraphTransition(source="call", target="failed", outcome="failure"),
                ],
            ),
            actor.id,
        )
        parent = await workflows.publish(create_ref_id(parent.id, parent.version), actor.id)
        requests = RequestService(session)
        kind = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"TQ{uuid7().hex}",
                name="Timer subprocess request",
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(kind.id, kind.version),
                data={"amount": "1"},
            ),
            actor,
        )
        submitted, _ = await requests.submit(
            create_ref_id(draft.id, draft.version),
            BusinessRequestSubmitDTO(submit_key=f"timer-subprocess-{uuid7()}"),
            actor,
        )
        root = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                )
            )
        ).one()
        child_run = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_not(None),
                )
            )
        ).one()
        assert child_run.status == "WAITING"
        assert root.status == "WAITING"
        timeline = await ProcessTimelineService(session).get(root, ProcessTimelineQueryDTO())
        assert timeline.children[0].current_positions[0].wait_kind == "TIMER"
        action = (
            await session.exec(
                select(ScheduledActionEntity)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.id) == col(ScheduledActionEntity.step_execution_id),
                )
                .where(StepExecutionEntity.process_instance_id == child_run.id)
            )
        ).one()
        action.due_at = get_datetime_utc() - timedelta(seconds=1)
        child_id = child_run.id
        root_id = root.id
        await session.commit()
    owner = uuid7()
    assert action.id in await claim_due_actions(owner)
    assert await fire_claimed_action(action.id, owner)
    async with SessionFactory() as session:
        child_run = await session.get(ProcessInstanceEntity, child_id)
        assert child_run is not None and child_run.status == "COMPLETED"
        assert await SubprocessService(session, ProcessService(session)).settle(child_id) in {
            "completed",
            "duplicate",
        }
        await session.commit()
        root = await session.get(ProcessInstanceEntity, root_id)
        assert root is not None and root.status == "COMPLETED"
        actor = await session.get(UserEntity, actor.id)
        assert actor is not None
        requests = RequestService(session)
        failed_draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(kind.id, kind.version),
                data={"amount": "2"},
            ),
            actor,
        )
        failed_request, _ = await requests.submit(
            create_ref_id(failed_draft.id, failed_draft.version),
            BusinessRequestSubmitDTO(submit_key=f"failed-timer-subprocess-{uuid7()}"),
            actor,
        )
        failed_parent = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == failed_request.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                )
            )
        ).one()
        failed_child = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == failed_request.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_not(None),
                )
            )
        ).one()
        failed_wait = (
            await session.exec(
                select(StepExecutionEntity).where(
                    StepExecutionEntity.process_instance_id == failed_child.id,
                    StepExecutionEntity.status == "WAITING",
                )
            )
        ).one()
        assert await ProcessService(session).fail_wait_execution(
            failed_child.id, failed_wait.id, "timer.delivery.failed"
        )
        assert failed_child.status == "FAILED"
        assert (
            await SubprocessService(session, ProcessService(session)).settle(failed_child.id)
            == "completed"
        )
        assert failed_parent.status == "COMPLETED"
        transitions = (
            await session.exec(
                select(ProcessTransitionEntity).where(
                    ProcessTransitionEntity.process_instance_id == failed_parent.id,
                )
            )
        ).all()
        assert transitions[-1].outcome_key == "failure"
        await session.commit()
    await engine.dispose()
