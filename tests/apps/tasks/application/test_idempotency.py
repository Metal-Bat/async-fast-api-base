"""Tests for durable task idempotency claims."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid7

import pytest

import apps.tasks.application.idempotency as idem
from apps.tasks.domain.entity import TaskIdempotencyEntity
from utils.date_utils import get_datetime_utc


def test_idempotency_key_is_stored_as_uuid() -> None:
    assert TaskIdempotencyEntity.__annotations__["key"] is UUID


@pytest.fixture
def storage(monkeypatch):
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.exec.return_value = Mock(first=Mock(return_value=(uuid7(),)))
    monkeypatch.setattr(idem, "SessionFactory", Mock(return_value=session))
    cache = AsyncMock()
    cache.get.return_value = None
    monkeypatch.setattr(idem.Redis, "from_url", Mock(return_value=cache))
    return session, cache


@pytest.mark.anyio
async def test_cache_outage_does_not_prevent_durable_claim(storage) -> None:
    session, cache = storage
    cache.set.side_effect = ConnectionError("cache down")
    claim = await idem.acquire_task(uuid7(), "task", 1260)
    assert claim.acquired
    session.commit.assert_awaited_once()
    assert cache.aclose.await_count >= 1


@pytest.mark.anyio
async def test_cached_lease_cannot_override_expired_database_lease(storage) -> None:
    _, cache = storage
    cache.set.return_value = False
    assert (await idem.acquire_task(uuid7(), "task", 1260)).acquired


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["RUNNING", "SUCCESS"])
async def test_existing_claim_distinguishes_running_and_completed(storage, status) -> None:
    session, cache = storage
    key = uuid7()
    existing = TaskIdempotencyEntity(
        key=key,
        task_id="original",
        status=status,
        expires_at=get_datetime_utc() + timedelta(seconds=1200),
        result={"saved": True},
    )
    session.exec.side_effect = [
        Mock(first=Mock(return_value=None)),
        Mock(one_or_none=Mock(return_value=existing)),
    ]
    claim = await idem.acquire_task(key, "duplicate", 1260)
    assert not claim.acquired
    assert claim.completed == (status == "SUCCESS")
    assert claim.result == {"saved": True}
    assert claim.retry_after > 0
    cache.set.assert_not_awaited()


@pytest.mark.anyio
async def test_database_failure_never_leaves_a_new_cache_claim(storage) -> None:
    session, cache = storage
    session.commit.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        await idem.acquire_task(uuid7(), "task", 1260)
    cache.set.assert_not_awaited()


@pytest.mark.anyio
async def test_release_attempts_cache_cleanup_even_when_database_fails(storage) -> None:
    session, cache = storage
    session.exec.side_effect = RuntimeError("database down")
    key = uuid7()
    claim = idem.TaskClaim(key, "task", uuid7(), True)
    with pytest.raises(RuntimeError, match="database down"):
        await idem.release_task(claim)
    cache.eval.assert_awaited_once_with(
        idem._RELEASE_CACHE, 1, f"task:idempotency:{key}", str(claim.owner_token)
    )
    assert cache.aclose.await_count >= 1


@pytest.mark.anyio
async def test_completion_refuses_lost_ownership(storage) -> None:
    session, _ = storage
    session.exec.return_value = Mock(rowcount=0)
    with pytest.raises(RuntimeError, match="ownership changed"):
        await idem.complete_task(idem.TaskClaim(uuid7(), "task", uuid7(), True), {"ok": True})
    session.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_cancelled_acquisition_releases_committed_ownership(storage, monkeypatch) -> None:
    import asyncio

    _, _cache = storage
    release = AsyncMock()
    monkeypatch.setattr(idem, "release_task", release)
    monkeypatch.setattr(idem, "_cache_claim", AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await idem.acquire_task(uuid7(), "task", 1260)
    released = release.call_args.args[0]
    assert released.key.version == 7 and released.task_id == "task"
    assert released.acquired
