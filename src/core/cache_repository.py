"""Redis read-through cache with versioned keys and bounded entry lifetimes."""

import hashlib
from collections.abc import Awaitable, Callable
from uuid import uuid7

from pydantic import TypeAdapter, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from core.settings import settings


class BaseCacheRepository:
    """Cache validated public read models for one resource namespace."""

    def __init__(self, namespace: str, *, ttl_seconds: int = 30 * 60) -> None:
        self.namespace = namespace
        self.ttl_seconds = ttl_seconds

    def _client(self) -> Redis:
        """Build a short-timeout client so cache trouble cannot stall database reads."""
        return Redis.from_url(
            str(settings.CACHE_DSN),
            socket_connect_timeout=1,
            socket_timeout=1,
        )

    @property
    def _epoch_key(self) -> str:
        return f"read-cache:{self.namespace}:epoch"

    async def get_or_load[T](
        self, identity: str, adapter: TypeAdapter[T], loader: Callable[[], Awaitable[T]]
    ) -> T:
        """Return a cached read model, or load and cache it for this epoch."""
        try:
            async with self._client() as cache:
                epoch = await cache.get(self._epoch_key)
                if epoch is None:
                    await cache.set(self._epoch_key, str(uuid7()), nx=True)
                    epoch = await cache.get(self._epoch_key)
                token = epoch.decode() if isinstance(epoch, bytes) else str(epoch)
                digest = hashlib.sha256(identity.encode()).hexdigest()
                key = f"read-cache:{self.namespace}:{token}:{digest}"
                payload = await cache.get(key)
                if payload is not None:
                    try:
                        return adapter.validate_json(payload)
                    except ValidationError:
                        pass
        except RedisError, OSError:
            return await loader()

        value = await loader()
        try:
            async with self._client() as cache:
                await cache.set(key, adapter.dump_json(value), ex=self.ttl_seconds)
        except RedisError, OSError:
            pass
        return value

    async def invalidate(self) -> bool:
        """Move later reads to a new epoch; old entries expire naturally."""
        try:
            async with self._client() as cache:
                await cache.set(self._epoch_key, str(uuid7()))
            return True
        except RedisError, OSError:
            return False
