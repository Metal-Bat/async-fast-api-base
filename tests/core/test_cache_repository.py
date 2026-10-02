"""Behavior tests for versioned read-through cache entries."""

from unittest.mock import AsyncMock

import pytest
from pydantic import TypeAdapter
from redis.exceptions import ConnectionError as RedisConnectionError

import core.cache_repository as cache_module
from core.cache_repository import BaseCacheRepository


class MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes | str] = {}
        self.expirations: dict[str, int] = {}
        self.available = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, key: str):
        if not self.available:
            raise RedisConnectionError("cache unavailable")
        return self.values.get(key)

    async def set(self, key: str, value: bytes | str, *, ex=None, nx=False):
        if not self.available:
            raise RedisConnectionError("cache unavailable")
        if nx and key in self.values:
            return False
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = ex
        return True


@pytest.mark.anyio
async def test_cache_hit_invalidation_and_ttl(monkeypatch) -> None:
    redis = MemoryRedis()
    monkeypatch.setattr(cache_module.Redis, "from_url", lambda *_a, **_kw: redis)
    cache = BaseCacheRepository("users", ttl_seconds=1800)
    loader = AsyncMock(return_value=["first"])
    adapter = TypeAdapter(list[str])

    assert await cache.get_or_load("page:1", adapter, loader) == ["first"]
    assert await cache.get_or_load("page:1", adapter, loader) == ["first"]
    loader.assert_awaited_once()
    assert 1800 in redis.expirations.values()

    await cache.invalidate()
    loader.return_value = ["updated"]
    assert await cache.get_or_load("page:1", adapter, loader) == ["updated"]
    assert loader.await_count == 2


@pytest.mark.anyio
async def test_cache_outage_falls_back_to_loader(monkeypatch) -> None:
    redis = MemoryRedis()
    redis.available = False
    monkeypatch.setattr(cache_module.Redis, "from_url", lambda *_a, **_kw: redis)
    loader = AsyncMock(return_value="fresh")

    assert (
        await BaseCacheRepository("users").get_or_load("detail:1", TypeAdapter(str), loader)
        == "fresh"
    )
    loader.assert_awaited_once()
