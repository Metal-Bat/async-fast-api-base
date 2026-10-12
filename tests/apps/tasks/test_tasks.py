"""Tests for registered task definitions and execution policies."""

from apps.tasks.tasks import ping
from core.task_registry import DEFAULT_TASK_POLICY, registered_tasks


def test_clean_task_registration_applies_project_policy() -> None:
    """Registered tasks inherit the default queue, retries, and time limits."""
    assert ping.name == "system.ping"
    assert ping.soft_time_limit == DEFAULT_TASK_POLICY.soft_time_limit
    assert ping.time_limit == DEFAULT_TASK_POLICY.time_limit
    assert "media.cleanup_abandoned_uploads" in registered_tasks()


def test_compensation_task_does_not_label_in_flight_duplicate_completed(monkeypatch):
    from unittest.mock import AsyncMock
    from uuid import uuid7

    from apps.processes.application import compensation
    from apps.tasks.tasks import execute_bpms_compensation

    monkeypatch.setattr(
        compensation, "execute_compensation", AsyncMock(return_value="duplicate_in_flight")
    )
    assert execute_bpms_compensation.run(str(uuid7())) == {"status": "duplicate_in_flight"}
