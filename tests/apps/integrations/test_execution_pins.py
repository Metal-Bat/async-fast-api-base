"""Registered execution cannot substitute current credentials for an old pin."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.contracts import AdapterResult
from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.users.domain.entity import UserEntity
from utils.exceptions import VersionConflictException

CONNECTION_CODE = "test"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change", ["version", "secret_ref", "secret_version", "verification_status"]
)
async def test_service_execution_rejects_changed_exact_connection_pin(change):
    actor = UserEntity(id=uuid7(), username="publisher", hashed_password="hash")
    row = IntegrationConnectionEntity(
        id=uuid7(),
        code="test",
        name="Test connection",
        provider="https_status",
        kind="SERVICE",
        owner_user_id=actor.id,
        secret_ref=CONNECTION_CODE,
        secret_version="1",
        verification_status="VERIFIED",
        non_secret_config={"endpoint_key": "test"},
    )
    provider = Mock(invoke=AsyncMock(return_value=AdapterResult(status_code=200)))
    service = ConnectionService(Mock(), provider)
    pin = service._pin(row)
    service.get = AsyncMock(return_value=row)
    setattr(row, change, row.version + 1 if change == "version" else "changed")
    with pytest.raises(VersionConflictException, match="changed|revoked"):
        await service.execute(pin, actor)
    provider.invoke.assert_not_called()
