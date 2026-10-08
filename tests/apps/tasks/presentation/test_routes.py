"""Tests for task definition, schedule, and execution routes."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from fastapi import Request

from apps.tasks.domain.dto import (
    ManualTaskDTO,
    PeriodicTaskCreateDTO,
    PeriodicTaskQuery,
    PeriodicTaskUpdateDTO,
    TaskDefinitionQuery,
    TaskExecutionQuery,
)
from apps.tasks.domain.entity import PeriodicTaskEntity, TaskExecutionEntity
from apps.tasks.presentation import routes
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.ref_id import create_ref_id
from utils.exceptions import NotAllowedException, NotFoundException


def request_context() -> Request:
    return Request({"type": "http", "headers": []})


def admin() -> UserEntity:
    return UserEntity(
        id=uuid7(), username=f"admin-{uuid7()}", hashed_password="hash", is_superuser=True
    )


@pytest.mark.anyio
async def test_registered_tasks_have_paginated_policy_and_signature_details() -> None:
    page = await routes.search_task_definitions(request_context(), TaskDefinitionQuery(), admin())
    ping = next(item for item in page.result.items if item.name == "system.ping")
    assert ping.ref_id
    assert ping.signature == "() -> dict[str, str]"
    assert ping.time_limit > ping.soft_time_limit


@pytest.mark.anyio
async def test_schedule_creation_rejects_unregistered_task_name() -> None:
    session = Mock(commit=AsyncMock())
    with pytest.raises(NotFoundException):
        await routes.create_schedule(
            request_context(),
            PeriodicTaskCreateDTO(
                name="invalid",
                task_name="unregistered.task",
                schedule_type="interval",
                interval_seconds=60,
            ),
            admin(),
            session,
        )
    session.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_task_schedule_routes_require_admin_and_persist() -> None:
    regular = UserEntity(id=uuid7(), username="regular", hashed_password="hash")
    actor = admin()
    session = Mock()
    session.add = Mock()
    session.commit = AsyncMock()

    async def refresh(entity: PeriodicTaskEntity) -> None:
        entity.id = entity.id or uuid7()

    session.refresh = AsyncMock(side_effect=refresh)
    result = Mock()
    result.all.return_value = []
    result.one.return_value = 0
    session.exec = AsyncMock(return_value=result)
    data = PeriodicTaskCreateDTO(
        name="heartbeat",
        task_name="system.ping",
        schedule_type="interval",
        interval_seconds=10,
    )

    with pytest.raises(NotAllowedException):
        await RequirePermission("admin.tasks.manage")(regular, session)
    entity = await routes.create_schedule(request_context(), data, actor, session)
    assert bool(entity.data.queue)
    session.commit.assert_awaited_once()
    page = await routes.search_schedules(request_context(), PeriodicTaskQuery(), actor, session)
    assert page.result.items == []


@pytest.mark.anyio
async def test_task_update_delete_history_retry_and_revoke(monkeypatch: pytest.MonkeyPatch) -> None:
    """Administrative task controls persist or invoke Celery as expected."""
    actor = admin()
    schedule = PeriodicTaskEntity(
        id=uuid7(),
        name="schedule",
        task_name="system.ping",
        queue="default",
        schedule_type="interval",
        interval_seconds=10,
    )
    execution = TaskExecutionEntity(
        id=uuid7(), task_id="failed", task_name="system.ping", queue="default", status="FAILURE"
    )
    query_result = Mock()
    query_result.all.return_value = [execution]
    query_result.one_or_none.return_value = execution
    session = Mock()
    session.get = AsyncMock(return_value=schedule)
    session.exec = AsyncMock(return_value=query_result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = Mock()

    updated = await routes.update_schedule(
        request_context(),
        create_ref_id(schedule.id, schedule.version),
        PeriodicTaskUpdateDTO(enabled=False),
        actor,
        session,
    )
    assert not updated.data.enabled
    deleted = await routes.delete_schedule(
        request_context(), create_ref_id(schedule.id, schedule.version), actor, session
    )
    assert deleted.code == 204
    query_result.one.return_value = 1
    executions = await routes.search_executions(
        request_context(), TaskExecutionQuery(), actor, session
    )
    assert executions.result.items[0].task_id == execution.task_id

    submitted = await routes.run_task(
        request_context(), ManualTaskDTO(task_name="system.ping"), actor, session
    )
    retried = await routes.retry_execution(request_context(), "failed", actor, session)
    assert submitted.data.status == "submitted" and retried.data.status == "retried"
    monkeypatch.setattr(routes.celery_app.control, "revoke", Mock())
    monkeypatch.setattr(
        routes.to_thread, "run_sync", AsyncMock(side_effect=lambda operation: operation())
    )
    revoked = await routes.revoke_execution(request_context(), "new-task", actor, session)
    assert revoked.data.status == "revoked"


@pytest.mark.anyio
async def test_task_select_http_supports_filtered_pages_and_plain_arrays() -> None:
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from core.deps import get_current_user, get_db

    app = FastAPI()
    app.include_router(routes.router)

    async def actor():
        return admin()

    async def database():
        yield Mock()

    app.dependency_overrides[get_current_user] = actor
    app.dependency_overrides[get_db] = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get(
            "/tasks/definitions/select", params={"search": "system.ping", "size": 1}
        )
        items = await client.get(
            "/tasks/definitions/select",
            params={"search": "system.ping", "size": 1, "response_format": "items"},
        )
        assert page.status_code == items.status_code == 200, (page.text, items.text)
        assert (
            items.json()
            == page.json()["result"]["items"]
            == [{"key": "system.ping", "value": "system.ping"}]
        )
        bad = await client.get("/tasks/queues/select", params={"size": 101})
        assert bad.status_code == 422
        empty = await client.get(
            "/tasks/definitions/select",
            params={"search": "no-such-task", "response_format": "items"},
        )
        assert empty.status_code == 200 and empty.json() == []
        invalid = await client.get("/tasks/queues/select", params={"response_format": "all"})
        assert invalid.status_code == 422
