"""Ephemeral cross-process signals and expiring admission leases in the existing cache."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID, uuid7

import anyio
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError

from apps.notifications.domain.live import (
    LIFETIME_SECONDS,
    MAX_CONNECTIONS,
    MAX_RECIPIENT_CONNECTIONS,
)
from core.settings import settings
from utils.exceptions import RateLimitedException, ServiceUnavailableException

_ADMIT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1])
for i = 1, 2 do redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now) end
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) or
   redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[3]) then return 0 end
for i = 1, 2 do
    redis.call('ZADD', KEYS[i], now + tonumber(ARGV[4]), ARGV[1])
    redis.call('EXPIRE', KEYS[i], tonumber(ARGV[4]))
end
return 1
"""


def signal_client() -> Redis:
    """Use the configured cache, with short connection/command timeouts."""
    return Redis.from_url(str(settings.CACHE_DSN), socket_connect_timeout=1, socket_timeout=1)


def recipient_channel(recipient_id: UUID) -> str:
    """Only authenticated server-derived identities select a channel."""
    return f"inbox-live:recipient:{recipient_id}"


@dataclass
class LiveSubscription:
    pubsub: PubSub

    async def receive(self, timeout: float) -> bytes | None:
        """Read at most one signal; no application queue accumulates behind a slow client."""
        message = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout)
        if message is None or message["type"] != "message":
            return None
        data = message["data"]
        if isinstance(data, str):
            return data.encode("utf-8")
        return data if isinstance(data, bytes) else None


@asynccontextmanager
async def subscribe(recipient_id: UUID) -> AsyncGenerator[LiveSubscription]:
    """Admit across processes, subscribe before resync and release resources on cancellation."""
    cache = signal_client()
    pubsub = cache.pubsub()
    token = str(uuid7())
    keys = ("inbox-live:connections", f"inbox-live:connections:{recipient_id}")
    try:
        if not await cache.eval(
            _ADMIT,
            2,
            *keys,
            token,
            MAX_CONNECTIONS,
            MAX_RECIPIENT_CONNECTIONS,
            LIFETIME_SECONDS + 30,
        ):
            raise RateLimitedException()
        await pubsub.subscribe(recipient_channel(recipient_id))
        ack = await pubsub.get_message(timeout=1)
        if ack is None or ack["type"] != "subscribe":
            raise ServiceUnavailableException()
        yield LiveSubscription(pubsub)
    except RedisError, OSError:
        raise ServiceUnavailableException() from None
    finally:
        with anyio.move_on_after(3, shield=True):
            try:
                await pubsub.aclose()
                await cache.zrem(keys[0], token)
                await cache.zrem(keys[1], token)
            except RedisError, OSError:
                pass  # A crashed/unreachable lease expires without granting extra admission.
            finally:
                await cache.aclose()
