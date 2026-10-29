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
        from apps.ai.application.agent_service import AIAgentService
        from apps.ai.application.authoring import AIAgentAuthoringService
        from apps.ai.domain.agent import AIAgentDraftSpec
        from apps.ai.domain.authoring import AIReportLookupPreviewInput
        from utils.select import SelectQuery

        agent = await AIAgentService(session).create(
            "lookup-preview-" + uuid7().hex,
            "Owned report preview",
            AIAgentDraftSpec.model_validate(
                {
                    "connection_ref": "declared-only",
                    "provider_key": "typesafe",
                    "model_id": "model",
                    "prompt_version": "1",
                    "instructions": "Classify this owned report.",
                    "decision": {"question": "Which queue?", "options_input_key": "report_ref"},
                    "data_policy": policy.model_dump(),
                    "field_classifications": {"report_ref": "INTERNAL"},
                    "user_limits": {
                        "requests": 1,
                        "tool_calls": 1,
                        "input_tokens": 1000,
                        "output_tokens": 500,
                        "total_tokens": 1500,
                        "elapsed_seconds": 30,
                        "spend_usd": "0.50",
                        "strict_spend": False,
                    },
                }
            ),
            owner,
        )
        extra = []
        for kind in ("live", "foreign", "expired", "deleted", "wrong_version"):
            candidate = ReportEntity(
                owner_id=outsider.id if kind == "foreign" else owner.id,
                definition_key=USER_REPORT.key,
                definition_version=USER_REPORT.version + (kind == "wrong_version"),
                max_rows=1,
                chunk_size=1,
                parallelism=1,
                priority=5,
                task_id=str(uuid7()),
                zip_password=uuid7().hex,
                expires_at=get_datetime_utc() + timedelta(hours=-1 if kind == "expired" else 1),
                deleted_at=get_datetime_utc() if kind == "deleted" else None,
            )
            session.add(candidate)
            extra.append(candidate)
        await session.flush()
        authoring = AIAgentAuthoringService(session)
        agent_ref = create_ref_id(agent.id, agent.version)
        first = await authoring.report_sources(agent_ref, SelectQuery(page=1, size=1), owner)
        second = await authoring.report_sources(agent_ref, SelectQuery(page=2, size=1), owner)
        assert first.total == second.total == 2
        assert first.items[0].report_ref != second.items[0].report_ref
        plan = await authoring.lookup_preview(
            agent_ref, AIReportLookupPreviewInput(report_ref=ref, limit=1), owner
        )
        assert plan.tool_called is False and plan.requires_human_tool_approval is True
        item_schema = plan.result_schema["items"]
        assert isinstance(item_schema, dict)
        properties = item_schema["properties"]
        assert isinstance(properties, dict)
        assert set(properties) == {"username", "is_active"}
        assert "private-preview-secret" not in plan.model_dump_json()
        with pytest.raises(NotFoundException):
            await authoring.lookup_preview(
                agent_ref,
                AIReportLookupPreviewInput(
                    report_ref=create_ref_id(extra[1].id, extra[1].version), limit=1
                ),
                owner,
            )
        with pytest.raises(VersionConflictException):
            await authoring.lookup_preview(
                agent_ref,
                AIReportLookupPreviewInput(
                    report_ref=create_ref_id(extra[2].id, extra[2].version), limit=1
                ),
                owner,
            )
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
        assert (await authoring.report_sources(agent_ref, SelectQuery(), owner)).total == 0
        with pytest.raises(NotAllowedException):
            await execute_saved_lookup(session, owner.id, policy, ref, limit=1)
        owner.is_superuser = True
        report.definition_version += 1
        await session.flush()
        with pytest.raises(VersionConflictException):
            await execute_saved_lookup(session, owner.id, policy, ref, limit=1)
        await session.rollback()
    await engine.dispose()
