"""Tests for shared CRUD service behavior."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from core.base_service import BaseCrudService
from core.ref_id import create_ref_id
from utils.exceptions import NotFoundException


@pytest.mark.anyio
async def test_service_crud_and_not_found() -> None:
    item = UserEntity(id=uuid7(), username="tester", hashed_password="hash")
    repo = Mock(model=UserEntity)
    repo.create = AsyncMock(return_value=item)
    repo.list = AsyncMock(return_value=[item])
    repo.count = AsyncMock(return_value=1)
    repo.get_by_id = AsyncMock(return_value=item)
    repo.update = AsyncMock(return_value=item)
    repo.delete = AsyncMock()
    service = BaseCrudService(repo)
    ref_id = create_ref_id(item.id, item.version)

    assert await service.create(item) is item
    page = await service.list(UserQuery())
    assert page.total == 1 and page.items == [item]
    assert await service.get_by_id(ref_id) is item
    assert await service.update(ref_id, {"ref_id": ref_id, "first_name": "Ada"}) is item
    await service.delete(ref_id)
    repo.update.assert_awaited_once_with(item, {"first_name": "Ada", "version": 1})
    repo.delete.assert_awaited_once_with(item, expected_version=1)

    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundException):
        await service.get_by_id(create_ref_id(uuid7(), 1))
