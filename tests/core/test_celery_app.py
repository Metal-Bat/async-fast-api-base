"""Tests for Celery application configuration and managed task behavior."""

import os
import subprocess
import sys
from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from celery.exceptions import Retry

import core.celery_app as celery_module
from core.task_lifecycle import TaskAlreadyRunning, TaskLifecycle
from core.task_registry import register_task


def test_celery_logging_keeps_parameters_hidden_and_honors_warning_level() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import logging
import structlog
from core.celery_app import configure_celery_logging
from core.deps import engine
from core.settings import settings

assert engine.echo is False
assert engine.sync_engine.hide_parameters is True
settings.LOG_OUTPUTS = ["console"]
settings.LOG_LEVEL = "DEBUG"
configure_celery_logging(loglevel=logging.WARNING)
assert engine.echo is False
log = structlog.get_logger("scheduler_test")
log.debug("hidden_debug")
log.info("hidden_info")
log.warning("visible_warning")
logging.getLogger("sqlalchemy.engine.Engine").info("hidden_query")
""",
        ],
        capture_output=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout + result.stderr
    assert "visible_warning" in output
    assert "hidden_" not in output


def test_celery_execution_policy() -> None:
    config = celery_module.celery_app.conf
    assert celery_module.celery_app.main == celery_module.settings.CELERY_APP_NAME
    assert config.task_default_queue == celery_module.settings.CELERY_DEFAULT_QUEUE
    assert celery_module.settings.CELERY_REPORT_QUEUE == "reporting"
    assert config.task_routes["reporting.*"]["queue"] == "reporting"
    assert config.task_serializer == "json"
    assert config.task_soft_time_limit == 600
    assert config.task_time_limit == 1200
    assert config.worker_max_tasks_per_child == 100
    assert config.worker_max_memory_per_child == 262_144
    assert config.worker_prefetch_multiplier == 1
    assert config.worker_cancel_long_running_tasks_on_connection_loss
    assert config.broker_transport_options["confirm_publish"]
    assert "apps.tasks.tasks" in config.include


def test_beat_process_initializes_scheduler_observability(monkeypatch) -> None:
    configure = Mock()
    monkeypatch.setattr(
        celery_module, "configure_scheduler_observability", configure, raising=False
    )

    celery_module.instrument_scheduler()

    configure.assert_called_once_with(celery_module.engine)


def test_duplicate_returns_previous_result_without_running_body(monkeypatch) -> None:
    body = Mock(return_value={"new": True})

    @register_task("test.duplicate")
    def task():
        return body()

    @contextmanager
    def lifecycle(*_args):
        yield TaskLifecycle(duplicate=True, result={"saved": True})

    monkeypatch.setattr(celery_module, "task_lifecycle", lifecycle)
    assert task.apply(task_id="duplicate", throw=True).result == {"saved": True}
    body.assert_not_called()


def test_bound_task_keeps_retry_request_and_reenters_context(monkeypatch) -> None:
    attempts = []
    exits = []

    @contextmanager
    def lifecycle(task, *_args):
        attempts.append((task.request.id, task.request.retries, task.request.headers))
        try:
            yield TaskLifecycle()
        finally:
            exits.append(task.request.retries)

    monkeypatch.setattr(celery_module, "task_lifecycle", lifecycle)

    @register_task("test.retry_context", bind=True)
    def retrying(self):
        if self.request.retries == 0:
            raise ConnectionError("try again")
        return "ok"

    result = retrying.apply(task_id="same-id", headers={"idempotency_key": "stable"}, throw=False)
    assert result.result == "ok"
    assert [entry[:2] for entry in attempts] == [("same-id", 0), ("same-id", 1)]
    assert all(entry[2]["idempotency_key"] == "stable" for entry in attempts)
    assert exits == [0, 1]


def test_busy_delivery_retries_after_the_lease(monkeypatch) -> None:
    @register_task("test.busy")
    def task():
        pytest.fail("busy task body executed")

    task.push_request(id="busy", headers={}, retries=0)
    monkeypatch.setattr(celery_module, "task_lifecycle", Mock(side_effect=TaskAlreadyRunning(1261)))
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(task, "retry", retry)
    try:
        with pytest.raises(Retry):
            task()
        assert retry.call_args.kwargs["countdown"] == 1261
    finally:
        task.pop_request()
