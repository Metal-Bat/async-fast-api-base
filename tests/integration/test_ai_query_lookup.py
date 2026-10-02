"""Approved AI reads reuse registered report queries and current authorization."""

import os
from datetime import timedelta
from uuid import uuid7

import pytest

from apps.ai.application.query_lookup import execute_saved_lookup
from apps.ai.domain.contracts import AIPermittedData
from apps.reporting.domain.entity import ReportEntity
from apps.users.application.reporting import USER_REPORT
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, NotFoundException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_saved_lookup_is_bounded_projected_and_authorized() -> None:
    async with SessionFactory() as session:
        owner = UserEntity(
            username=f"lookup-{uuid7()}", hashed_password="private", is_superuser=True
        )
        outsider = UserEntity(username=f"lookup-other-{uuid7()}", hashed_password="private")
        session.add_all([owner, outsider])
        await session.flush()
        report = ReportEntity(
            owner_id=owner.id,
            definition_key=USER_REPORT.key,
            definition_version=USER_REPORT.version,
            max_rows=100,
            chunk_size=10,
            parallelism=1,
            priority=5,
            task_id=str(uuid7()),
            expires_at=get_datetime_utc() + timedelta(hours=1),
        )
        session.add(report)
        await session.flush()
        ref = create_ref_id(report.id, report.version)
        policy = AIPermittedData(
            allowed_fields={"report_ref"},
            allowed_classifications={"INTERNAL"},
            allowed_tools={"lookup_saved_report"},
            allowed_retrieval_sources={"report.users"},
        )
        rows = await execute_saved_lookup(session, owner.id, policy, ref, limit=1)
        assert len(rows) == 1
        assert set(rows[0]) == {"username", "is_active"}
        redacted = policy.model_copy(update={"redacted_fields": {"username"}})
        sanitized = await execute_saved_lookup(session, owner.id, redacted, ref, limit=1)
        assert sanitized[0]["username"] == "[REDACTED]"
        with pytest.raises(ValueError, match="limit"):
            await execute_saved_lookup(session, owner.id, policy, ref, limit=100)
        with pytest.raises(NotFoundException):
            await execute_saved_lookup(session, outsider.id, policy, ref, limit=1)
        for rejected in (
            policy.model_copy(update={"allowed_tools": set()}),
            policy.model_copy(update={"allowed_retrieval_sources": set()}),
            policy.model_copy(update={"allowed_classifications": {"PUBLIC"}}),
        ):
            with pytest.raises(NotAllowedException):
                await execute_saved_lookup(session, owner.id, rejected, ref, limit=1)
        owner.is_superuser = False
        await session.flush()
        with pytest.raises(NotAllowedException):
            await execute_saved_lookup(session, owner.id, policy, ref, limit=1)
        owner.is_superuser = True
        report.definition_version += 1
        await session.flush()
        with pytest.raises(VersionConflictException):
            await execute_saved_lookup(session, owner.id, policy, ref, limit=1)
        await session.rollback()
    await engine.dispose()
