"""Tests for background report generation task helpers."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from botocore.exceptions import ConnectionError as BotoConnectionError

from apps.reporting import tasks
from apps.reporting.tasks import (
    REPORT_POLICY,
    _cleanup_stale_workdirs,
    _read_row_count,
    artifact_name,
)


def test_stale_hard_kill_workdir_is_removed(tmp_path, monkeypatch) -> None:
    stale = tmp_path / f"report-{uuid7()}-abandoned"
    fresh = tmp_path / f"report-{uuid7()}-active"
    unrelated = tmp_path / "keep-me"
    stale.mkdir()
    fresh.mkdir()
    unrelated.mkdir()
    cutoff_age = (
        tasks.settings.CELERY_TASK_TIME_LIMIT + tasks.settings.CELERY_TASK_LEASE_GRACE_SECONDS + 10
    )
    old = datetime.now(UTC).timestamp() - cutoff_age
    os.utime(stale, (old, old))
    monkeypatch.setattr(tasks.tempfile, "gettempdir", lambda: str(tmp_path))

    assert _cleanup_stale_workdirs() == 1
    assert not stale.exists()
    assert fresh.exists() and unrelated.exists()


@pytest.mark.anyio
async def test_report_count_reads_a_scalar_instead_of_casting_a_row() -> None:
    result = Mock()
    result.scalar_one.return_value = 3
    session = Mock()
    session.execute = AsyncMock(return_value=result)
    assert await _read_row_count(session, object()) == 3
    result.scalar_one.assert_called_once_with()


def test_report_policy_retries_transient_s3_connection_failures() -> None:
    assert BotoConnectionError in REPORT_POLICY.retry_for


def test_report_artifact_name_contains_created_at_time() -> None:
    created_at = datetime(2026, 9, 18, 11, 12, 50, tzinfo=UTC)
    assert artifact_name("users", created_at, "zip") == "users-report-20260918-111250.zip"
