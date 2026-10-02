"""Tests for user authorization policies."""

from unittest.mock import AsyncMock, Mock

import pytest

from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from utils.exceptions import NotAllowedException


@pytest.mark.anyio
async def test_permission_dependency_allows_superuser_and_denies_ungranted_user() -> None:
    """The central policy treats superusers as wildcard holders."""
    policy = RequirePermission("admin.users.manage")
    session = Mock()
    session.exec = AsyncMock()
    admin = UserEntity(username="admin-policy", hashed_password="hash", is_superuser=True)
    assert await policy(admin, session) is admin
    result = Mock()
    result.all.return_value = []
    session.exec.return_value = result
    with pytest.raises(NotAllowedException):
        await policy(UserEntity(username="plain-policy", hashed_password="hash"), session)
