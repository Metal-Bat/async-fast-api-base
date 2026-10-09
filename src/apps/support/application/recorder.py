"""Independent rollback-safe recording with sanitized non-recursive fallback."""

from contextlib import AsyncExitStack
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

import structlog
from anyio import fail_after
from sqlmodel import col, func, select, update

from apps.support.domain.dto import Category
from apps.support.domain.entity import SupportIncidentEntity
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory
from core.history import audit_context
from utils.date_utils import get_datetime_utc
from utils.exceptions import RateLimitedException

logger = structlog.get_logger(__name__)
RETENTION_DAYS = 30
CLIENT_CODES = {
    "client.render_failed": 1099,
    "client.network_failed": 1098,
    "client.unexpected_error": 1099,
}


async def _persist(
    *,
    category: Category,
    error_code: int,
    operation: str,
    request_id: UUID,
    actor_id: UUID | None = None,
    build: str | None = None,
) -> UUID:
    now = get_datetime_utc()
    minute = now.replace(second=0, microsecond=0)
    fingerprint = sha256(
        f"{category}:{error_code}:{operation}:{actor_id}:{build}".encode()
    ).hexdigest()
    async with AsyncExitStack() as stack:
        stack.enter_context(audit_context(reason=None, user_agent=None, source_ip=None))
        session = await stack.enter_async_context(SessionFactory())
        await stack.enter_async_context(session.begin())
        if category == "client":
            user = await session.get(UserEntity, actor_id, with_for_update=True)
            if user is None or user.deleted_at is not None:
                raise ValueError("Inactive incident actor")
        await session.exec(
            select(
                func.pg_advisory_xact_lock(
                    int.from_bytes(bytes.fromhex(fingerprint[:16]), signed=True)
                )
            )
        )
        row = (
            await session.exec(
                select(SupportIncidentEntity)
                .where(SupportIncidentEntity.fingerprint == fingerprint)
                .order_by(col(SupportIncidentEntity.episode).desc())
                .limit(1)
            )
        ).first()
        if row is not None and str(request_id) in row.recent_request_ids:
            return row.id
        if category == "client":
            rate = (
                await session.exec(
                    select(func.coalesce(func.sum(SupportIncidentEntity.rate_count), 0)).where(
                        SupportIncidentEntity.actor_id == actor_id,
                        SupportIncidentEntity.category == "client",
                        col(SupportIncidentEntity.rate_window_at) >= minute,
                    )
                )
            ).one()
            if rate >= 10:
                raise RateLimitedException()
        if (
            row is None
            or row.state == "RESOLVED"
            or row.expires_at <= now
            or row.created_at < now - timedelta(days=1)
        ):
            row = SupportIncidentEntity(
                fingerprint=fingerprint,
                created_at=now,
                last_seen_at=now,
                rate_window_at=minute,
                episode=1 if row is None else row.episode + 1,
                category=category,
                error_code=error_code,
                operation=operation,
                request_id=request_id,
                actor_id=actor_id,
                build=build,
                expires_at=now + timedelta(days=RETENTION_DAYS),
                recent_request_ids=[str(request_id)],
            )
            session.add(row)
            await session.flush()
            if category != "notification":
                from apps.support.application.alerts import stage_incident_alert

                await stage_incident_alert(session, row)
        else:
            if row.occurrence_count >= 1000000:
                return row.id
            reset_rate = row.rate_window_at < minute
            # Occurrence counters are not audit transitions: avoid one retained snapshot per retry.
            await session.exec(
                update(SupportIncidentEntity)
                .where(col(SupportIncidentEntity.id) == row.id)
                .values(
                    occurrence_count=row.occurrence_count + 1,
                    last_seen_at=now,
                    request_id=request_id,
                    recent_request_ids=[*row.recent_request_ids[-99:], str(request_id)],
                    rate_window_at=minute if reset_rate else row.rate_window_at,
                    rate_count=1 if reset_rate else row.rate_count + 1,
                    version=row.version + 1,
                )
                .execution_options(synchronize_session=False)
            )
        return row.id


async def record_failure(
    *,
    category: Category,
    error_code: int,
    operation: str,
    request_id: UUID,
    actor_id: UUID | None = None,
    build: str | None = None,
) -> UUID | None:
    """Return a durable identity only after commit; never call the business session."""
    try:
        with fail_after(2):
            return await _persist(
                category=category,
                error_code=error_code,
                operation=operation[:80],
                request_id=request_id,
                actor_id=actor_id,
                build=build,
            )
    except RateLimitedException:
        raise
    except Exception:  # noqa: BLE001 - independent sink must never hide the original outcome
        logger.error("support.recording_unavailable", durable=False, code=error_code)
        return None


async def record_request_failure(
    request, *, category: Category, error_code: int
) -> dict[str, object]:
    """Use server route metadata, never raw path/query/body/exception text."""
    from utils.presenter import request_id

    route = request.scope.get("route")
    operation = getattr(route, "name", "http.unhandled")
    identity = await record_failure(
        category=category,
        error_code=error_code,
        operation=operation,
        request_id=UUID(request_id(request)),
    )
    return {
        "support_persisted": identity is not None,
        "support_ref": str(identity) if identity else None,
    }
