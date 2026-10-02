"""PostgreSQL authorization and revocation of governed AI model connections."""

import os
from uuid import uuid7

import pytest
from pydantic import SecretStr

from apps.integrations.application.providers import StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.dto import AIConnectionConfig, ConnectionCreateDTO, SecretRotationDTO
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotAllowedException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


class FakeSecrets:
    def resolve(self, reference: str, version: str) -> SecretStr:
        if (reference, version) != ("credential", "1"):
            raise ValueError("Unavailable")
        return SecretStr("fake-key")


@pytest.mark.anyio
async def test_ai_connection_model_allowlist_and_rotation_are_rechecked() -> None:
    provider = StatusProvider(FakeSecrets(), {"approved": "https://models.example.invalid/v1"})
    async with SessionFactory() as session:
        owner = UserEntity(username=f"ai-owner-{uuid7()}", hashed_password="hash")
        outsider = UserEntity(username=f"ai-outsider-{uuid7()}", hashed_password="hash")
        session.add_all([owner, outsider])
        await session.flush()
        service = ConnectionService(session, provider)
        row = await service.create(
            ConnectionCreateDTO(
                code=f"AI{uuid7().hex}",
                name="AI models",
                provider="typesafe",
                kind="AI",
                non_secret_config=AIConnectionConfig(
                    endpoint_key="hosted",
                    models=["jev-1.13.0"],
                    provider_retention="Contract checked by operator",
                ),
                secret_ref="credential",
                secret_version="1",
            ),
            owner,
        )
        ref = create_ref_id(row.id, row.version)
        with pytest.raises(NotAllowedException):
            await service.pin_ai(ref, outsider, "jev-1.13.0")
        await service.verify(ref, owner)
        pin, policy = await service.pin_ai(create_ref_id(row.id, row.version), owner, "jev-1.13.0")
        assert policy.models == ["jev-1.13.0"]
        with pytest.raises(NotAllowedException):
            await service.pin_ai(create_ref_id(row.id, row.version), owner, "unlisted")
        await service.recheck_ai(pin, "jev-1.13.0", owner)
        await service.rotate(
            create_ref_id(row.id, row.version),
            SecretRotationDTO(secret_ref="credential", secret_version="2"),
            owner,
        )
        with pytest.raises(VersionConflictException):
            await service.recheck_ai(pin, "jev-1.13.0", owner)
        await session.rollback()
    await engine.dispose()
