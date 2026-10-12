"""Actual PostgreSQL/outbox/worker/HTTPS evidence for the protected local operation."""

import os
from uuid import uuid5, uuid7

import pytest
from anyio import sleep
from scripts.order_sandbox import SANDBOX_CONNECTION_CODE
from sqlmodel import col, select

from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.integrations.domain.entity import (
    IntegrationConnectionEntity,
    IntegrationConnectionGrantEntity,
)
from apps.processes.application.automation import execute_background
from apps.processes.application.service import ProcessService
from apps.processes.domain.entity import (
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.step_types.application.registry import builtin_registry, get_registry
from apps.tasks.application.outbox import dispatch_outbox
from apps.tasks.domain.entity import TaskOutboxEntity
from apps.users.domain.auth_entity import (
    PermissionEntity,
    RoleEntity,
    RolePermissionEntity,
    UserRoleEntity,
)
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.entity import WorkItemActionEntity, WorkItemEntity
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
from core.celery_app import celery_app
from core.deps import SessionFactory, engine
from core.history import audit_context
from core.i18n import use_language
from core.ref_id import create_ref_id
from tests.integration.test_processes import _step_refs
from utils.date_utils import get_datetime_utc
from utils.exceptions import ValidationDetailsException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_receipt_and_ai_inspection_use_real_sessions_and_participant_authorization():
    from secrets import token_urlsafe

    from httpx import ASGITransport, AsyncClient

    from main import app
    from utils.security import hash_password

    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session, session.begin():
                item_id, reviewer_id, publisher_id = await waiting_order(session)
                attempt = await approve_order(session, item_id, reviewer_id)
                execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
                assert execution is not None
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None
                process_id = process.id
                process_ref = create_ref_id(process.id, process.version)
                execution_ref = create_ref_id(execution.id, execution.version)
                publisher = await session.get(UserEntity, publisher_id)
                assert publisher is not None
                password = token_urlsafe(32)
                publisher.hashed_password = await hash_password(password)
                outsider = UserEntity(
                    username="order-outsider-" + uuid7().hex,
                    hashed_password=publisher.hashed_password,
                )
                session.add(outsider)
                await session.flush()
                username, outsider_name = publisher.username, outsider.username
                role_id = (
                    await session.exec(
                        select(UserRoleEntity.role_id).where(UserRoleEntity.user_id == publisher_id)
                    )
                ).one()
                permission_id = (
                    await session.exec(
                        select(PermissionEntity.id).where(PermissionEntity.name == "requests.start")
                    )
                ).one()
                session.add(RolePermissionEntity(role_id=role_id, permission_id=permission_id))
                recovery_permission = (
                    await session.exec(
                        select(PermissionEntity.id).where(
                            PermissionEntity.name == "processes.recover"
                        )
                    )
                ).one()
                session.add(
                    RolePermissionEntity(role_id=role_id, permission_id=recovery_permission)
                )
                session.add(UserRoleEntity(user_id=outsider.id, role_id=role_id))
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                headers = []
                for login_name in (username, outsider_name):
                    login = await client.post(
                        "/api/v1/auth/login",
                        json={"username": login_name, "password": password},
                    )
                    assert login.status_code == 200, login.text
                    headers.append(
                        {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
                    )
                for resource in ("orders", "ai-evidence"):
                    path = f"/api/v1/processes/{process_ref}/{resource}/search"
                    assert (await client.post(path, json={})).status_code == 401
                    assert (await client.post(path, headers=headers[1], json={})).status_code == 404
                    assert (
                        await client.post(path, headers=headers[0], json={"size": 101})
                    ).status_code == 422
                    response = await client.post(
                        path, headers=headers[0], json={"page": 1, "size": 1}
                    )
                    assert response.status_code == 200, response.text
                    result = response.json()["result"]
                    assert result["total"] == (1 if resource == "orders" else 0)
                    assert "owned-order" not in response.text
                    assert "quantity" not in response.text
                    if resource == "orders":
                        assert result["items"][0]["state"] == "PREPARED"
                        assert result["items"][0]["receipt"] is None
                for action in ("reconcile", "reconcile-cancellation"):
                    denied = await client.post(
                        f"/api/v1/processes/{process_ref}/orders/{action}",
                        headers=headers[0],
                        json={
                            "step_execution_ref_id": execution_ref,
                            "command_key": "forbidden-lookup",
                            "reason": "permission-test",
                        },
                    )
                    assert denied.status_code == 403, denied.text
                forged = await client.post(
                    f"/api/v1/processes/{process_ref}/resume",
                    headers=headers[0],
                    json={
                        "command_key": "invented-receipt",
                        "outcome": "next",
                        "outputs": {"result": {"state": "CREATED"}},
                    },
                )
                assert forged.status_code == 409, forged.text
            async with SessionFactory() as session, session.begin():
                process = await session.get(ProcessInstanceEntity, process_id)
                assert process is not None
                await ProcessService(session).command(
                    create_ref_id(process.id, process.version),
                    "cancel",
                    "inspection-cleanup",
                    actor_user_id=publisher_id,
                )
    finally:
        await engine.dispose()


async def waiting_order(
    session, *, reversible=False, granted=False, receipt_view=False, claim=True, connected=False
):
    """Create only uniquely named records in the disposable flow database."""
    token = uuid7().hex
    publisher = UserEntity(username="order-publisher-" + token, hashed_password=token)
    reviewer = UserEntity(username="order-reviewer-" + token, hashed_password=token)
    session.add_all([publisher, reviewer])
    await session.flush()
    role = RoleEntity(name="order-publisher-" + token)
    session.add(role)
    await session.flush()
    permission = (
        await session.exec(
            select(PermissionEntity).where(PermissionEntity.name == "workflows.manage")
        )
    ).one()
    session.add_all(
        [
            RolePermissionEntity(role_id=role.id, permission_id=permission.id),
            UserRoleEntity(role_id=role.id, user_id=publisher.id),
        ]
    )
    if receipt_view or connected:
        start_permission = (
            await session.exec(
                select(PermissionEntity).where(PermissionEntity.name == "requests.start")
            )
        ).one()
        participant_role = RoleEntity(name="order-participant-" + token)
        session.add(participant_role)
        await session.flush()
        session.add_all(
            [
                RolePermissionEntity(role_id=role.id, permission_id=start_permission.id),
                RolePermissionEntity(
                    role_id=participant_role.id, permission_id=start_permission.id
                ),
                UserRoleEntity(role_id=participant_role.id, user_id=reviewer.id),
            ]
        )
        await session.flush()
    connection = IntegrationConnectionEntity(
        code="order-" + token,
        name="Explicit local order sandbox",
        provider="https_sandbox_orders",
        kind="SERVICE",
        owner_user_id=reviewer.id if granted else publisher.id,
        secret_ref=SANDBOX_CONNECTION_CODE,
        secret_version="1",
        verification_status="VERIFIED",
        non_secret_config={"endpoint_key": "owned_orders"},
    )
    session.add(connection)
    await session.flush()
    if granted:
        session.add(
            IntegrationConnectionGrantEntity(
                integration_connection_id=connection.id, user_id=publisher.id, can_use=True
            )
        )
        await session.flush()
    forms = FormService(session)
    form = await forms.create(
        FormCreateDTO(code="ORDER" + token, name="Sandbox order approval"), publisher.id
    )
    fields = ["/properties/item_code", "/properties/quantity"]
    form_version = await forms.create_version(
        FormVersionCreateDTO(
            form_ref_id=create_ref_id(form.id, form.version),
            number=1,
            data_schema={
                "type": "object",
                "properties": {"item_code": {"type": "string"}, "quantity": {"type": "integer"}},
                "required": ["item_code", "quantity"],
                "additionalProperties": False,
            },
            render_schema={
                "dialect": "bpms.render/1",
                "root": {
                    "component": "vertical",
                    "children": [
                        {"component": "text", "scope": fields[0], "label": "Demo item"},
                        {"component": "number", "scope": fields[1], "label": "Quantity"},
                    ],
                },
                "outcomes": ["approve", "reject", "return"] if connected else ["approve", "reject"],
            },
        )
    )
    form_version = await forms.publish(
        create_ref_id(form_version.id, form_version.version), publisher.id
    )
    refs = await _step_refs(session)
    registry = get_registry() if connected else builtin_registry()
    payload_schema = next(
        port.value_schema
        for port in registry.resolve("service_task", "1").metadata().ports
        if port.port_key == "payload"
    )
    submission_schema = next(
        port.value_schema
        for port in registry.resolve("human_task", "1").metadata().ports
        if port.port_key == "submission"
    )
    workflows = WorkflowService(session, registry)
    workflow = await workflows.create(
        WorkflowCreateDTO(code="ORDER" + token, name="Human-approved local sandbox order"),
        publisher.id,
    )
    version = await workflows.create_version(
        WorkflowVersionCreateDTO(
            workflow_ref_id=create_ref_id(workflow.id, workflow.version), number=1
        )
    )
    graph = GraphSnapshot(
        steps=[
            GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
            GraphStep(
                key="approve",
                type_code="HUMAN_TASK",
                type_version_ref=refs[("HUMAN_TASK", 1)],
                form_ref=create_ref_id(form_version.id, form_version.version),
                field_policy={"read": fields, "write": fields, "required": fields, "hidden": []},
                task_contract={
                    "default_view": "order",
                    "views": [
                        {
                            "key": "order",
                            "purpose": "edit",
                            "title": {"en": "Approve sandbox order", "fa": "تأیید سفارش آزمایشی"},
                            "scopes": fields,
                        }
                    ],
                    "actions": [
                        {
                            "key": "approve",
                            "kind": "complete",
                            "outcome_key": "approve",
                            "title": {"en": "Approve", "fa": "تأیید"},
                            "required_scopes": fields,
                            "validation": "complete",
                        },
                        {
                            "key": "reject",
                            "kind": "reject",
                            "outcome_key": "reject",
                            "title": {"en": "Reject", "fa": "رد"},
                            "require_comment": True,
                        },
                    ],
                },
            ),
            GraphStep(
                key="order",
                type_code="SERVICE_TASK",
                type_version_ref=refs[("SERVICE_TASK", 1)],
                config={
                    "connection_ref": create_ref_id(connection.id, connection.version),
                    "operation_key": "sandbox.order.create/1",
                },
            ),
            GraphStep(key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]),
        ],
        targets=[
            GraphTarget(step="approve", user_ref=create_ref_id(reviewer.id, reviewer.version))
        ],
        bindings=[
            GraphBinding(
                step="order",
                target_port="payload",
                target_schema=payload_schema,
                source_kind="STEP_OUTPUT",
                source_step="approve",
                source_port="submission",
                source_schema=submission_schema,
            )
        ],
        transitions=[
            GraphTransition(source="start", target="approve", outcome="next", is_default=True),
            GraphTransition(source="approve", target="order", outcome="approve", is_default=True),
            GraphTransition(source="approve", target="finish", outcome="reject"),
            GraphTransition(source="order", target="finish", outcome="next", is_default=True),
        ],
    )
    if receipt_view:
        from tests.integration.test_connected_fixture import add_receipt_view

        assert not reversible
        await add_receipt_view(session, graph, publisher, reviewer, token, refs, registry)
    if connected:
        from tests.integration.test_purchase_fixture import add_parallel_reviews

        await add_parallel_reviews(session, graph, publisher, reviewer, token, refs, registry)
    if reversible:
        next(step for step in graph.steps if step.key == "order").flow = GraphFlow(
            compensation_step="cancel_order"
        )
        graph.steps.extend(
            [
                GraphStep(
                    key="wait",
                    type_code="EVENT_WAIT",
                    type_version_ref=refs[("EVENT_WAIT", 1)],
                    config={"event_type": "demo.order.shipped"},
                ),
                GraphStep(
                    key="cancel_order",
                    type_code="SERVICE_TASK",
                    type_version_ref=refs[("SERVICE_TASK", 1)],
                    config={
                        "connection_ref": create_ref_id(connection.id, connection.version),
                        "operation_key": "sandbox.order.cancel/1",
                    },
                    flow=GraphFlow(compensation_only=True),
                ),
            ]
        )
        next(edge for edge in graph.transitions if edge.source == "order").target = "wait"
        graph.transitions.append(
            GraphTransition(source="wait", target="finish", outcome="received", is_default=True)
        )
        wait_schema = next(
            port.value_schema
            for port in registry.resolve("event_wait", "1").metadata().ports
            if port.port_key == "correlation_key"
        )
        graph.bindings.extend(
            [
                GraphBinding(
                    step="wait",
                    target_port="correlation_key",
                    target_schema=wait_schema,
                    source_kind="CONSTANT",
                    constant_value=token,
                ),
                GraphBinding(
                    step="cancel_order",
                    target_port="payload",
                    target_schema=payload_schema,
                    source_kind="CONSTANT",
                    constant_value={},
                ),
            ]
        )
    try:
        await workflows.replace_graph(create_ref_id(version.id, version.version), graph)
    except ValidationDetailsException as error:
        raise AssertionError(f"Protected fixture publication issues: {error.issues}") from error
    await workflows.publish(create_ref_id(version.id, version.version), publisher.id)
    requests = RequestService(session)
    request_form = form
    if connected:
        from tests.integration.test_purchase_request_fixture import publish_purchase_form

        request_form = await publish_purchase_form(session, publisher, token)
    request_type = await requests.create_type(
        RequestTypeCreateDTO(
            code="ORDER" + token,
            name="Sandbox orders",
            workflow_ref_id=create_ref_id(workflow.id, workflow.version),
            form_ref_id=create_ref_id(request_form.id, request_form.version),
        )
    )
    if connected:
        from tests.integration.test_purchase_request_fixture import create_purchase_draft

        request = await create_purchase_draft(session, request_type, publisher)
    else:
        request, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"item_code": "DEMO", "quantity": 2},
            ),
            publisher,
        )
    await requests.submit(
        create_ref_id(request.id, request.version),
        BusinessRequestSubmitDTO(submit_key=token),
        publisher,
    )
    item = (
        await session.exec(
            select(WorkItemEntity).where(WorkItemEntity.business_request_id == request.id)
        )
    ).one()
    if claim:
        item = await WorkItemService(session).claim(
            create_ref_id(item.id, item.version), token, reviewer
        )
    return item.id, reviewer.id, publisher.id


async def approve_order(session, item_id, reviewer_id, *, payload=None):
    item = await session.get(WorkItemEntity, item_id)
    reviewer = await session.get(UserEntity, reviewer_id)
    assert item is not None and reviewer is not None
    human_execution = await session.get(StepExecutionEntity, item.step_execution_id)
    assert human_execution is not None
    await WorkItemService(session).finish(
        create_ref_id(item.id, item.version),
        "complete",
        "approve-order",
        "approve",
        payload if payload is not None else {"item_code": "DEMO", "quantity": 2},
        reviewer,
    )
    return (
        await session.exec(
            select(StepExecutionAttemptEntity)
            .join(
                StepExecutionEntity,
                col(StepExecutionEntity.id) == col(StepExecutionAttemptEntity.step_execution_id),
            )
            .where(
                StepExecutionEntity.process_instance_id == human_execution.process_instance_id,
                StepExecutionEntity.wait_kind == "BACKGROUND",
            )
        )
    ).one()


@pytest.mark.anyio
async def test_committed_human_approval_dispatches_actual_worker_order_receipt():
    assert os.getenv("RUN_SANDBOX_WORKER") == "1", "mandatory real sandbox/worker missing"
    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session, session.begin():
                item_id, reviewer_id, _ = await waiting_order(session)
            async with SessionFactory() as session, session.begin():
                attempt = await approve_order(session, item_id, reviewer_id)
                attempt_id = attempt.id
                execution_id = attempt.step_execution_id
                assert attempt.status == "WAITING"
            await dispatch_outbox(celery_app)
            for _ in range(150):
                async with SessionFactory() as session:
                    attempt = await session.get(StepExecutionAttemptEntity, attempt_id)
                    assert attempt is not None and attempt.status not in {"FAILED", "CANCELLED"}
                    if attempt.status == "SUCCEEDED":
                        break
                await sleep(0.2)
            assert attempt.status == "SUCCEEDED"
            assert attempt.automation_snapshot is not None
            receipt = attempt.automation_snapshot["order_dispatch"]["receipt"]
            assert receipt["operation_id"] == str(uuid5(execution_id, "sandbox.order.create/1"))
            assert receipt["state"] == "CREATED"
            assert (await execute_background(attempt_id)).disposition == "duplicate"
            async with SessionFactory() as session:
                execution = await session.get(StepExecutionEntity, execution_id)
                assert execution is not None and execution.output_snapshot == {"result": receipt}
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None and process.status == "COMPLETED"
                from apps.processes.application.order_recovery import OrderRecoveryService
                from utils.pagination import PageRequest

                evidence = await OrderRecoveryService().search(session, process.id, PageRequest())
                assert evidence.total == 1 and evidence.items[0].state == "CONFIRMED"
                assert evidence.items[0].receipt is not None
                assert evidence.items[0].receipt.model_dump(mode="json") == receipt
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_rolled_back_approval_has_no_dispatch_or_completed_human_action():
    assert os.getenv("RUN_SANDBOX_WORKER") == "1", "mandatory real sandbox/worker missing"

    class RollbackProbe(Exception):
        pass

    attempt_id = None

    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session, session.begin():
                item_id, reviewer_id, _ = await waiting_order(session)
            with pytest.raises(RollbackProbe):
                async with SessionFactory() as session, session.begin():
                    attempt = await approve_order(session, item_id, reviewer_id)
                    attempt_id = attempt.id
                    raise RollbackProbe
            async with SessionFactory() as session:
                assert attempt_id is not None
                assert await session.get(StepExecutionAttemptEntity, attempt_id) is None
                assert not (
                    await session.exec(
                        select(TaskOutboxEntity).where(TaskOutboxEntity.task_id == str(attempt_id))
                    )
                ).all()
                assert not (
                    await session.exec(
                        select(WorkItemActionEntity).where(
                            WorkItemActionEntity.work_item_id == item_id,
                            WorkItemActionEntity.action == "COMPLETE",
                        )
                    )
                ).all()
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        "offboarded",
        "role_revoked",
        "grant_revoked",
        "connection_rotated",
        "payload_changed",
        "cancelled",
    ],
)
async def test_current_authority_and_approval_are_rechecked_before_dispatch(change):
    assert os.getenv("RUN_SANDBOX_WORKER") == "1", "mandatory real sandbox/worker missing"
    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session, session.begin():
                item_id, reviewer_id, publisher_id = await waiting_order(
                    session, granted=change == "grant_revoked"
                )
            async with SessionFactory() as session, session.begin():
                attempt = await approve_order(session, item_id, reviewer_id)
                attempt_id = attempt.id
                execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
                assert execution is not None and attempt.automation_snapshot is not None
                identity = uuid5(execution.id, "sandbox.order.create/1")
                from apps.processes.domain.automation import AutomationSnapshot

                pin = AutomationSnapshot.model_validate(attempt.automation_snapshot).connection
                assert pin is not None
                if change == "offboarded":
                    publisher = await session.get(UserEntity, publisher_id)
                    assert publisher is not None
                    publisher.deleted_at = get_datetime_utc()
                elif change == "role_revoked":
                    links = (
                        await session.exec(
                            select(UserRoleEntity).where(UserRoleEntity.user_id == publisher_id)
                        )
                    ).all()
                    for link in links:
                        await session.delete(link)
                elif change == "grant_revoked":
                    grant = (
                        await session.exec(
                            select(IntegrationConnectionGrantEntity).where(
                                IntegrationConnectionGrantEntity.user_id == publisher_id
                            )
                        )
                    ).one()
                    grant.deleted_at = get_datetime_utc()
                elif change == "connection_rotated":
                    connection = (
                        await session.exec(
                            select(IntegrationConnectionEntity).where(
                                IntegrationConnectionEntity.owner_user_id == publisher_id
                            )
                        )
                    ).one()
                    connection.secret_version = "2"
                elif change == "payload_changed":
                    execution.input_snapshot = {"payload": {"item_code": "DEMO", "quantity": 3}}
                else:
                    process = await session.get(
                        ProcessInstanceEntity, execution.process_instance_id
                    )
                    assert process is not None
                    await ProcessService(session).command(
                        create_ref_id(process.id, process.version),
                        "cancel",
                        "cancel-order",
                        actor_user_id=publisher_id,
                    )
            if change == "cancelled":
                assert (await execute_background(attempt_id)).disposition == "late_ignored"
            else:
                from utils.exceptions import NotAllowedException

                with pytest.raises(
                    NotAllowedException if change == "grant_revoked" else VersionConflictException
                ):
                    await execute_background(attempt_id)
            from apps.processes.application.automation import _provider

            assert await _provider().lookup_order(pin, identity) is None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_direct_process_resume_cannot_fabricate_human_approval():
    assert os.getenv("RUN_SANDBOX_WORKER") == "1", "mandatory real sandbox/worker missing"
    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session, session.begin():
                item_id, _, publisher_id = await waiting_order(session)
            with pytest.raises(VersionConflictException, match="human approval"):
                async with SessionFactory() as session, session.begin():
                    item = await session.get(WorkItemEntity, item_id)
                    assert item is not None
                    execution = await session.get(StepExecutionEntity, item.step_execution_id)
                    assert execution is not None
                    process = await session.get(
                        ProcessInstanceEntity, execution.process_instance_id
                    )
                    assert process is not None
                    await ProcessService(session).resume(
                        create_ref_id(process.id, process.version),
                        "fabricated-approval",
                        "approve",
                        {"submission": {"item_code": "DEMO", "quantity": 2}, "outcome": "approve"},
                        actor_user_id=publisher_id,
                    )
            async with SessionFactory() as session:
                item = await session.get(WorkItemEntity, item_id)
                assert item is not None and item.status == "CLAIMED"
                assert not (
                    await session.exec(
                        select(WorkItemActionEntity).where(
                            WorkItemActionEntity.work_item_id == item_id,
                            WorkItemActionEntity.action == "COMPLETE",
                        )
                    )
                ).all()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_direct_resume_cannot_invent_order_receipt_after_real_human_approval():
    try:
        with use_language("en"), audit_context():
            async with SessionFactory() as session, session.begin():
                item_id, reviewer_id, publisher_id = await waiting_order(session)
                attempt = await approve_order(session, item_id, reviewer_id)
                attempt_id = attempt.id
                execution = await session.get(StepExecutionEntity, attempt.step_execution_id)
                assert execution is not None
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None
                process_ref = create_ref_id(process.id, process.version)
            with pytest.raises(VersionConflictException, match="provider receipt"):
                async with SessionFactory() as session, session.begin():
                    await ProcessService(session).resume(
                        process_ref,
                        "invented-provider-output",
                        "next",
                        {
                            "result": {
                                "operation_id": str(uuid7()),
                                "receipt_id": str(uuid7()),
                                "state": "CREATED",
                                "payload_hash": "0" * 64,
                            }
                        },
                        actor_user_id=publisher_id,
                    )
            async with SessionFactory() as session, session.begin():
                attempt = await session.get(StepExecutionAttemptEntity, attempt_id)
                assert attempt is not None and attempt.status == "WAITING"
                process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
                assert process is not None and process.status == "WAITING"
                await ProcessService(session).command(
                    create_ref_id(process.id, process.version),
                    "cancel",
                    "forgery-cleanup",
                    actor_user_id=publisher_id,
                )
    finally:
        await engine.dispose()
