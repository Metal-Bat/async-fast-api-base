"""Public user reads use the cache without storing password hashes."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.users.application.service import UserService
from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from core.ref_id import create_ref_id
from utils.pagination import Page


@pytest.mark.anyio
async def test_user_service_caches_public_page_and_detail() -> None:
    user = UserEntity(id=uuid7(), username="alice", hashed_password="secret-hash")
    repo = Mock(model=UserEntity)
    repo.list = AsyncMock(return_value=[user])
    repo.count = AsyncMock(return_value=1)
    repo.get_by_id = AsyncMock(return_value=user)
    cache = Mock()
    saved = {}

    async def get_or_load(key, adapter, loader):
        if key not in saved:
            saved[key] = adapter.dump_json(await loader())
        assert b"secret-hash" not in saved[key]
        return adapter.validate_json(saved[key])

    cache.get_or_load = AsyncMock(side_effect=get_or_load)
    service = UserService(repo, cache)
    query = UserQuery(page=1, size=10)
    ref_id = create_ref_id(user.id, user.version)

    first_page = await service.list_public(query)
    second_page = await service.list_public(query)
    assert isinstance(first_page, Page)
    assert second_page.items[0].username == "alice"
    assert repo.list.await_count == 1
    assert repo.count.await_count == 1

    assert (await service.get_public_by_id(ref_id)).username == "alice"
    assert (await service.get_public_by_id(ref_id)).username == "alice"
    repo.get_by_id.assert_awaited_once()
