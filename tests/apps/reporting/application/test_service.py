"""Tests for report registration services."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid7

import pytest

from apps.reporting.application.service import ReportService
from apps.reporting.domain.entity import ReportEntity, ReportStatus
from apps.tasks.domain.entity import TaskOutboxEntity
from apps.users.application.reporting import USER_REPORT
from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from utils.date_utils import get_datetime_utc
from utils.pagination import FilterCriteria, FilterOperation


@pytest.mark.anyio
async def test_report_registration_persists_limits_and_transactional_outbox() -> None:
    owner = UserEntity(id=uuid7(), username="admin", hashed_password="hash", is_superuser=True)
    session = Mock()
    session.add = Mock()

    async def flush() -> None:
        report = next(
            call.args[0]
            for call in session.add.call_args_list
            if isinstance(call.args[0], ReportEntity)
        )
        report.id = uuid7()

    session.flush = AsyncMock(side_effect=flush)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    report = await ReportService(session).create(
        USER_REPORT.key,
        owner,
        UserQuery(
            filters=[
                FilterCriteria(
                    field_name="username", operation=FilterOperation.EQUAL, value="admin"
                )
            ]
        ),
        "en",
    )
    outbox = next(
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], TaskOutboxEntity)
    )
    assert report.status == ReportStatus.PENDING
    assert report.filters[0]["field_name"] == "username"
    assert report.max_rows == 100_000 and report.chunk_size == 100
    assert report.expires_at > get_datetime_utc() + timedelta(days=9)
    assert outbox.task_id == report.task_id
    assert UUID(report.task_id).version == 7
    assert UUID(str(outbox.headers["idempotency_key"])).version == 7
    assert outbox.priority == report.priority
    session.commit.assert_awaited_once()
