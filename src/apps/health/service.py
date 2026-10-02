from collections.abc import Awaitable, Callable
from time import monotonic
from urllib.parse import urlparse

import anyio
from redis.asyncio import Redis
from sqlalchemy import text

from core.base_dto import BaseDTO
from core.deps import SessionFactory
from core.settings import settings
from utils.s3 import s3_client


class DependencyHealth(BaseDTO):
    """Health status and latency for one internal dependency."""

    status: str
    latency_ms: float
    detail: str | None = None


class HealthReport(BaseDTO):
    """Aggregate application readiness report."""

    status: str
    services: dict[str, DependencyHealth]


async def _timed(check: Callable[[], Awaitable[None]]) -> DependencyHealth:
    started = monotonic()
    try:
        with anyio.fail_after(3):
            await check()
        return DependencyHealth(status="up", latency_ms=(monotonic() - started) * 1000)
    except Exception as exc:  # noqa: BLE001 - health checks must isolate dependency failures
        return DependencyHealth(
            status="down",
            latency_ms=(monotonic() - started) * 1000,
            detail=type(exc).__name__,
        )


async def check_postgres() -> None:
    """Verify a PostgreSQL connection and trivial statement."""
    async with SessionFactory() as session:
        await super(type(session), session).execute(text("SELECT 1"))  # ty:ignore[deprecated]


async def check_cache() -> None:
    """Verify Dragonfly through its Redis-compatible protocol."""
    cache = Redis.from_url(str(settings.CACHE_DSN))
    try:
        await cache.ping()
    finally:
        await cache.aclose()


async def check_broker() -> None:
    """Verify that the configured AMQP listener accepts TCP connections."""
    broker = urlparse(settings.CELERY_BROKER_URL)
    stream = await anyio.connect_tcp(broker.hostname or "localhost", broker.port or 5672)
    await stream.aclose()


async def check_s3() -> None:
    """Verify access to the configured S3 bucket."""
    async with s3_client() as client:
        await client.head_bucket(Bucket=settings.S3_BUCKET)


CHECKS: dict[str, Callable[[], Awaitable[None]]] = {
    "postgres": check_postgres,
    "cache": check_cache,
    "broker": check_broker,
    "s3": check_s3,
}


async def readiness() -> HealthReport:
    """Run internal checks concurrently and return aggregate readiness."""
    results: dict[str, DependencyHealth] = {}

    async def run(name: str, check: Callable[[], Awaitable[None]]) -> None:
        results[name] = await _timed(check)

    async with anyio.create_task_group() as group:
        for name, check in CHECKS.items():
            group.start_soon(run, name, check)
    return HealthReport(
        status="ready" if all(item.status == "up" for item in results.values()) else "not_ready",
        services=results,
    )
