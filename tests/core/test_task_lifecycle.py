"""Tests for managed task execution lifecycle behavior."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from celery.exceptions import Retry, SoftTimeLimitExceeded
from structlog.contextvars import bind_contextvars, clear_contextvars, get_contextvars

import core.task_lifecycle as lifecycle
from apps.tasks.application.idempotency import TaskClaim


@pytest.fixture
def managed(monkeypatch):
    monkeypatch.setattr(lifecycle, "run_async", asyncio.run)
    claim = TaskClaim(uuid7(), "task", uuid7(), True)
    acquire = AsyncMock(return_value=claim)
    complete, release, record = AsyncMock(), AsyncMock(), Mock()
    monkeypatch.setattr(lifecycle, "acquire_task", acquire)
    monkeypatch.setattr(lifecycle, "complete_task", complete)
    monkeypatch.setattr(lifecycle, "release_task", release)
    monkeypatch.setattr(lifecycle, "record_execution", record)
    task = SimpleNamespace(
        name="test.task",
        time_limit=1200,
        request=SimpleNamespace(
            id="task",
            headers={},
            retries=0,
            timelimit=(None, None),
            delivery_info={},
            hostname="worker",
        ),
    )
    return task, claim, acquire, complete, release, record


def test_success_retains_result_and_releases_active_state(managed) -> None:
    task, claim, acquire, complete, release, record = managed
    bind_contextvars(request_id="outer")
    try:
        with lifecycle.task_lifecycle(task, (), {}) as state:
            assert get_contextvars()["task_id"] == "task"
            state.result = {"ok": True}
        complete.assert_awaited_once_with(claim, {"ok": True})
        release.assert_awaited_once_with(claim)
        assert acquire.call_args.args[2] == 1260
        assert record.call_args.kwargs["status"] == "SUCCESS"
        assert get_contextvars() == {"request_id": "outer"}
    finally:
        clear_contextvars()


@pytest.mark.parametrize(
    "error",
    [ValueError("bad"), Retry(), SoftTimeLimitExceeded(), SystemExit(1), asyncio.CancelledError()],
)
def test_any_body_error_releases_state_and_preserves_exception(managed, error) -> None:
    task, claim, _, complete, release, record = managed
    with pytest.raises(type(error)) as caught, lifecycle.task_lifecycle(task, (), {}):
        raise error
    assert caught.value is error
    release.assert_awaited_once_with(claim)
    complete.assert_not_awaited()
    assert record.call_args.kwargs["status"] == ("RETRY" if isinstance(error, Retry) else "FAILURE")
    assert "task_id" not in get_contextvars()


def test_cleanup_failure_does_not_mask_original_error(managed) -> None:
    task, _, _, _, release, record = managed
    release.side_effect = ConnectionError("database down")
    with pytest.raises(ValueError, match="body failed"), lifecycle.task_lifecycle(task, (), {}):
        raise ValueError("body failed")
    assert record.call_args.kwargs["result"]["exception_type"] == "ValueError"


def test_failed_success_commit_releases_for_retry(managed) -> None:
    task, claim, _, complete, release, record = managed
    complete.side_effect = ConnectionError("commit failed")
    with (
        pytest.raises(ConnectionError, match="commit failed"),
        lifecycle.task_lifecycle(task, (), {}) as state,
    ):
        state.result = "result"
    release.assert_awaited_once_with(claim)
    assert record.call_args.kwargs["status"] == "FAILURE"


def test_duplicate_does_not_overwrite_original_history_or_release_its_claim(managed) -> None:
    task, _, acquire, complete, release, record = managed
    acquire.return_value = TaskClaim(
        uuid7(), "task", uuid7(), False, completed=True, result="saved"
    )
    with lifecycle.task_lifecycle(task, (), {}) as state:
        assert state.duplicate and state.result == "saved"
    complete.assert_not_awaited()
    release.assert_not_awaited()
    record.assert_not_called()


def test_running_duplicate_waits_without_changing_state(managed) -> None:
    task, _, acquire, _, release, record = managed
    acquire.return_value = TaskClaim(uuid7(), "task", uuid7(), False, retry_after=45)
    with (
        pytest.raises(lifecycle.TaskAlreadyRunning) as busy,
        lifecycle.task_lifecycle(task, (), {}),
    ):
        pytest.fail("busy task executed")
    assert busy.value.retry_after == 45
    release.assert_not_awaited()
    record.assert_not_called()


def test_message_hard_limit_controls_lease_length(managed) -> None:
    task, _, acquire, _, _, _ = managed
    task.request.timelimit = (1800, 600)
    with lifecycle.task_lifecycle(task, (), {}):
        pass
    assert acquire.call_args.args[2] == 1860


def test_uuid7_header_is_the_durable_idempotency_key(managed) -> None:
    task, _, acquire, _, _, _ = managed
    key = uuid7()
    task.request.headers = {"idempotency_key": str(key)}

    with lifecycle.task_lifecycle(task, (), {}):
        pass

    assert acquire.call_args.args[0] == key


def test_worker_span_records_pickup_and_originating_user(managed, monkeypatch) -> None:
    task, *_ = managed
    task.request.headers = {
        "trace_username": "ada",
        "trace_user_id": "0199-user",
    }
    task.request.delivery_info = {"routing_key": "reporting"}
    span = Mock()
    monkeypatch.setattr(lifecycle.trace, "get_current_span", Mock(return_value=span), raising=False)

    with lifecycle.task_lifecycle(task, (), {}):
        pass

    span.add_event.assert_any_call("task.picked_up")
    span.set_attribute.assert_any_call("app.user.username", "ada")
    span.set_attribute.assert_any_call("app.user.id", "0199-user")
    span.set_attribute.assert_any_call("enduser.id", "0199-user")
    span.set_attribute.assert_any_call("messaging.destination.name", "reporting")
