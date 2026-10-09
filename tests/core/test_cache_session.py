"""Committed user changes invalidate read caches after ORM flushes."""

from unittest.mock import AsyncMock
from uuid import uuid7

import pytest
from sqlalchemy import event, update
from sqlmodel import Session as SQLModelSession
from sqlmodel import create_engine

from apps.users.data.cache_repository import UserCacheRepository
from apps.users.domain.entity import UserEntity, UserHistoryTable
from core.cache_session import CacheInvalidatingSession, CacheTrackingSession, _pending_namespaces


def test_cache_tracking_session_preserves_sqlmodel_exec_api() -> None:
    assert issubclass(CacheTrackingSession, SQLModelSession)
    assert callable(CacheTrackingSession.exec)


def test_cache_tracking_rejects_corrupted_pending_state() -> None:
    session = CacheTrackingSession()
    session.info["read_cache_pending_namespaces"] = ["users"]

    with pytest.raises(TypeError, match="pending namespace state"):
        _pending_namespaces(session)

    session.close()


def test_user_create_update_and_delete_mark_cache_namespace() -> None:
    assert UserCacheRepository().namespace == "users"
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_uuidv7(connection, _record):
        connection.create_function("uuidv7", 0, lambda: str(uuid7()))

    try:
        getattr(UserEntity, "__table__").create(engine)  # noqa: B009
        UserHistoryTable.create(engine)
        with CacheTrackingSession(engine) as session:
            user = UserEntity(id=uuid7(), username="cached", hashed_password="hash")
            session.add(user)
            session.flush()
            assert session.info.pop("read_cache_pending_namespaces") == {"users"}

            user.first_name = "Updated"
            session.flush()
            assert session.info.pop("read_cache_pending_namespaces") == {"users"}

            session.delete(user)
            session.flush()
            assert session.info.pop("read_cache_pending_namespaces") == {"users"}

            session.exec(update(UserEntity).values(first_name="Bulk"))
            assert session.info.pop("read_cache_pending_namespaces") == {"users"}

    finally:
        engine.dispose()


@pytest.mark.anyio
async def test_cache_invalidates_only_after_successful_commit(monkeypatch) -> None:
    invalidate = AsyncMock(return_value=True)
    monkeypatch.setattr("core.cache_session.BaseCacheRepository.invalidate", invalidate)
    session = CacheInvalidatingSession()
    session.sync_session.info["read_cache_pending_namespaces"] = {"users"}

    await session.commit()
    invalidate.assert_awaited_once()
    assert "read_cache_pending_namespaces" not in session.sync_session.info

    invalidate.reset_mock()
    session.sync_session.info["read_cache_pending_namespaces"] = {"users"}
    await session.rollback()
    invalidate.assert_not_awaited()
    assert "read_cache_pending_namespaces" not in session.sync_session.info
    await session.close()


@pytest.mark.anyio
async def test_cache_commit_rejects_corrupted_pending_state() -> None:
    session = CacheInvalidatingSession()
    session.sync_session.info["read_cache_pending_namespaces"] = ["users"]

    with pytest.raises(TypeError, match="pending namespace state"):
        await session.commit()

    await session.close()
