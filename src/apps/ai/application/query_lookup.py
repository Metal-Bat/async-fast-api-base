"""Bounded reads from the existing database-saved, code-registered report queries."""

import json
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field
from pydantic_ai import RunContext
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.tools import TrustedAITool, register_trusted_tool
from apps.ai.domain.contracts import AIPermittedData
from apps.reporting.application.base import ReportActor
from apps.reporting.application.registry import get_report_definition
from apps.reporting.application.service import ReportService
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from core.ref_id import open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, VersionConflictException


@dataclass(frozen=True)
class AIQueryContext:
    session: AsyncSession
    actor_id: UUID
    policy: AIPermittedData


async def execute_saved_lookup(
    session: AsyncSession,
    actor_id: UUID,
    policy: AIPermittedData,
    report_ref: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Reauthorize an owned saved query and return only its opted-in columns."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Lookup limit is invalid")
    if "lookup_saved_report" not in policy.allowed_tools:
        raise NotAllowedException("Lookup tool is not permitted")
    actor = await session.get(UserEntity, actor_id, populate_existing=True)
    if actor is None or actor.deleted_at is not None:
        raise NotAllowedException("Lookup principal is unavailable")
    report = await ReportService(session).get_owned(report_ref, actor.id)
    if (
        report.version != open_ref_id(report_ref)[1]
        or report.expires_at <= get_datetime_utc()
        or report.status in {"CANCELLED", "EXPIRED"}
    ):
        raise VersionConflictException("Saved lookup query changed or expired")
    definition = get_report_definition(report.definition_key)
    if definition.version != report.definition_version:
        raise VersionConflictException("Saved lookup definition changed")
    lookup = definition.ai_lookup
    if (
        lookup is None
        or not policy.permits_retrieval(f"report.{definition.key}")
        or lookup.classification not in policy.allowed_classifications
    ):
        raise NotAllowedException("Saved query is not an approved retrieval source")
    if limit > lookup.max_rows:
        raise ValueError("Lookup limit exceeds the registered bound")
    permissions = await user_permissions(actor, session)
    if "*" not in permissions and lookup.permission not in permissions:
        raise NotAllowedException("Saved query permission is unavailable")
    query = definition.processor.query_type.model_validate(
        {"filters": report.filters, "sort_orders": report.sort_orders}
    )
    source = (
        definition.processor.build_statement(
            query, ReportActor(id=actor.id, is_superuser=actor.is_superuser)
        )
        .limit(min(limit, report.max_rows))
        .subquery()
    )
    statement = select(*(source.c[field] for field in lookup.fields))
    rows = [dict(row) for row in (await session.exec(statement)).mappings().all()]
    for row in rows:
        for field in policy.redacted_fields & row.keys():
            row[field] = "[REDACTED]"
    if len(json.dumps(rows, ensure_ascii=False).encode()) > 32768:
        raise ValueError("Lookup result exceeds the permitted payload size")
    return rows


async def lookup_saved_report(
    ctx: RunContext[AIQueryContext],
    report_ref: Annotated[str, Field(min_length=1, max_length=1024)],
    limit: Annotated[int, Field(ge=1, le=10)] = 10,
) -> list[dict[str, Any]]:
    """Read bounded approved fields from an owned saved report query."""
    return await execute_saved_lookup(
        ctx.deps.session, ctx.deps.actor_id, ctx.deps.policy, report_ref, limit=limit
    )


register_trusted_tool(
    TrustedAITool(
        key="lookup_saved_report",
        version="1",
        description="Read up to ten approved fields-projected rows from an owned saved report query.",
        function=lookup_saved_report,
    )
)
