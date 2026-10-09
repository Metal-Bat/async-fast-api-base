"""Tests for shared CRUD repository behavior."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from core.base_repository import BaseCrudRepository
from utils.exceptions import VersionConflictException


@pytest.mark.anyio
async def test_live_list_and_count_cannot_be_bypassed_by_deleted_filter() -> None:
    result = Mock()
    result.all.return_value = []
    result.one.return_value = 0
    session = Mock(exec=AsyncMock(return_value=result))
    repo = BaseCrudRepository(session, UserEntity)
    query = UserQuery.model_validate(
        {"filters": [{"field_name": "deleted_at", "operation": "isNotNull"}], "page": 3}
    )
    assert await repo.list(query) == []
    assert await repo.count(query) == 0
    for call in session.exec.await_args_list:
        statement = str(call.args[0])
        assert '"USER"."DELETED_AT" IS NULL' in statement
        assert '"USER"."DELETED_AT" IS NOT NULL' in statement


def user() -> UserEntity:
    return UserEntity(id=uuid7(), username="tester", hashed_password="hash")


@pytest.mark.anyio
async def test_repository_crud_and_count() -> None:
    item = user()
    result = Mock()
    result.all.return_value = [item]
    result.one.return_value = 1
    session = Mock()
    session.add = Mock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock(return_value=item)
    session.exec = AsyncMock(return_value=result)
    repo = BaseCrudRepository(session, UserEntity)

    assert await repo.create(item) is item
    assert await repo.list(UserQuery()) == [item]
    assert await repo.count(UserQuery()) == 1
    assert await repo.get_by_id(item.id) is item
    assert (await repo.update(item, {"first_name": "Ada", "version": 1})).first_name == "Ada"
    assert item.updated_at is not None
    await repo.delete(item, expected_version=1)
    assert item.deleted_at is not None
    assert session.flush.await_count == 3


@pytest.mark.anyio
async def test_repository_rejects_stale_versions() -> None:
    item = user()
    repo = BaseCrudRepository(Mock(), UserEntity)
    with pytest.raises(VersionConflictException):
        await repo.update(item, {"version": 2})
    with pytest.raises(VersionConflictException):
        await repo.delete(item, expected_version=2)
