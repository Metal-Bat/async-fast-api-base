import json
from dataclasses import dataclass
from datetime import timedelta
from time import time
from typing import Any
from uuid import UUID, uuid7

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, delete, select, update

from apps.tasks.domain.entity import TaskIdempotencyEntity
from core.deps import SessionFactory
from core.settings import settings
from utils.date_utils import get_datetime_utc

logger = structlog.get_logger(__name__)
_RELEASE_CACHE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


@dataclass(frozen=True, slots=True)
class TaskClaim:
    """One attempt's ownership, or the outcome of a previous attempt."""

    key: UUID
    task_id: str
    owner_token: UUID
    acquired: bool
    completed: bool = False
    result: Any = None
    retry_after: int = 1


async def _cache_claim(claim: TaskClaim, ttl_seconds: int, *, release: bool = False) -> None:
    """Mirror leases without allowing a cache outage to override durable ownership."""
    cache = Redis.from_url(
        str(settings.CACHE_DSN),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        cache_key = f"task:idempotency:{claim.key}"
        if release:
            await cache.eval(_RELEASE_CACHE, 1, cache_key, str(claim.owner_token))
        else:
            await cache.set(cache_key, str(claim.owner_token), ex=ttl_seconds, nx=True)
    except (RedisError, OSError, ValueError, TypeError) as exc:
        logger.warning(
            "task.cache_unavailable", task_id=claim.task_id, error_type=type(exc).__name__
        )
    finally:
        try:
            await cache.aclose()
        except (RedisError, OSError, ValueError, TypeError) as exc:
            logger.warning("task.cache_close_failed", error_type=type(exc).__name__)


async def acquire_task(key: UUID, task_id: str, ttl_seconds: int) -> TaskClaim:
    """Atomically acquire an absent/expired lease, including when Redis is unavailable."""
    owner = uuid7()
    cached = await _completed_cache(key)
    if cached is not None:
        return TaskClaim(key, task_id, owner, False, completed=True, result=cached["result"])
    now = get_datetime_utc()
    statement = insert(TaskIdempotencyEntity).values(
        key=key,
        task_id=task_id,
        owner_token=owner,
        status="RUNNING",
        result=None,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    statement = statement.on_conflict_do_update(
        index_elements=["KEY"],
        set_={
            "TASK_ID": task_id,
            "OWNER_TOKEN": owner,
            "STATUS": "RUNNING",
            "RESULT": None,
            "EXPIRES_AT": now + timedelta(seconds=ttl_seconds),
        },
        where=col(TaskIdempotencyEntity.expires_at) <= now,
    ).returning(col(TaskIdempotencyEntity.owner_token))
    try:
        async with SessionFactory() as session:
            acquired = (await session.exec(statement)).first() is not None
            if acquired:
                claim = TaskClaim(key, task_id, owner, True)
            else:
                existing = (
                    await session.exec(
                        select(TaskIdempotencyEntity).where(col(TaskIdempotencyEntity.key) == key)
                    )
                ).one_or_none()
                claim = TaskClaim(
                    key,
                    task_id,
                    owner,
                    False,
                    completed=existing is not None and existing.status == "SUCCESS",
                    result=existing.result if existing else None,
                    retry_after=max(1, int((existing.expires_at - now).total_seconds()) + 1)
                    if existing
                    else 1,
                )
            await session.commit()
        if acquired:
            await _cache_claim(claim, ttl_seconds)
        return claim
    except BaseException:
        # Commit cancellation can be ambiguous; the token makes cleanup safe either way.
        try:
            await release_task(TaskClaim(key, task_id, owner, True))
        except BaseException as exc:  # noqa: BLE001 - preserve acquisition/cancellation failure
            logger.error(
                "task.acquire_release_failed", task_id=task_id, error_type=type(exc).__name__
            )
        raise


async def claim_task(key: UUID, task_id: str, ttl_seconds: int = 1260) -> bool:
    """Acquire a standalone expiring claim; managed tasks use acquire_task instead."""
    return (await acquire_task(key, task_id, ttl_seconds)).acquired


async def complete_task(claim: TaskClaim, result: Any) -> None:
    """Save success only while this attempt still owns an unexpired lease."""
    now = get_datetime_utc()
    expires_at = now + timedelta(seconds=settings.CELERY_IDEMPOTENCY_TTL_SECONDS)
    async with SessionFactory() as session:
        updated = await session.exec(
            update(TaskIdempotencyEntity)
            .where(
                col(TaskIdempotencyEntity.key) == claim.key,
                col(TaskIdempotencyEntity.owner_token) == claim.owner_token,
                col(TaskIdempotencyEntity.status) == "RUNNING",
                col(TaskIdempotencyEntity.expires_at) > now,
            )
            .values(
                status="SUCCESS",
                result=result,
                expires_at=expires_at,
            )
        )
        if updated.rowcount != 1:
            raise RuntimeError("Task lease expired or ownership changed before completion")
        await session.commit()
    await _completed_cache(claim.key, {"result": result, "expires_at": expires_at.timestamp()})


async def _completed_cache(key: UUID, value: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Cache immutable committed results only until their durable expiration deadline."""
    cache = Redis.from_url(
        str(settings.CACHE_DSN),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        cache_key = f"task:completed:{key}"
        if value is not None:
            await cache.set(cache_key, json.dumps(value), exat=int(value["expires_at"]))
        else:
            raw = await cache.get(cache_key)
            if isinstance(raw, str):
                cached = json.loads(raw)
                if (
                    isinstance(cached, dict)
                    and cached.get("expires_at", 0) > time()
                    and "result" in cached
                ):
                    return cached
    except (RedisError, OSError, ValueError, TypeError) as exc:
        logger.warning("task.result_cache_unavailable", error_type=type(exc).__name__)
    finally:
        try:
            await cache.aclose()
        except (RedisError, OSError, ValueError, TypeError) as exc:
            logger.warning("task.cache_close_failed", error_type=type(exc).__name__)
    return None


async def release_task(claim: TaskClaim) -> None:
    """Release a failed attempt without deleting success or a replacement owner's state."""
    try:
        async with SessionFactory() as session:
            await session.exec(
                delete(TaskIdempotencyEntity).where(
                    col(TaskIdempotencyEntity.key) == claim.key,
                    col(TaskIdempotencyEntity.owner_token) == claim.owner_token,
                    col(TaskIdempotencyEntity.status) == "RUNNING",
                )
            )
            await session.commit()
    finally:
        await _cache_claim(claim, 1, release=True)
