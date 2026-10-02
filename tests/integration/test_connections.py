import os
from typing import override
from uuid import uuid7

import pytest

from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.contracts import AdapterResult
from apps.integrations.domain.dto import (
    ConnectionConfig,
    ConnectionCreateDTO,
    GrantDTO,
    SecretRotationDTO,
)
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotAllowedException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


class FakeProvider:
    def __init__(self) -> None:
        self.versions = []

    def validate(self, provider, kind, config) -> None:
        assert provider == "https_status" and kind == "SERVICE"

    async def invoke(self, pin):
        self.versions.append(pin.secret_version)
        return AdapterResult(status_code=200)


@pytest.mark.anyio
async def test_grants_rotation_pin_and_revocation() -> None:
    provider = FakeProvider()
    async with SessionFactory() as session:
        owner = UserEntity(username=f"owner-{uuid7()}", hashed_password="hash")
        candidate = UserEntity(username=f"candidate-{uuid7()}", hashed_password="hash")
        outsider = UserEntity(username=f"outsider-{uuid7()}", hashed_password="hash")
        session.add_all([owner, candidate, outsider])
        await session.flush()
        service = ConnectionService(session, provider)
        row = await service.create(
            ConnectionCreateDTO(
                code=f"C{uuid7().hex}",
                name="Connection",
                provider="https_status",
                kind="SERVICE",
                non_secret_config=ConnectionConfig(endpoint_key="approved"),
                secret_ref="credential",
                secret_version="1",
            ),
            owner,
        )
        ref = create_ref_id(row.id, row.version)
        with pytest.raises(NotAllowedException):
            await service.get(ref, outsider)
        await service.grant(
            ref, GrantDTO(user_ref_id=create_ref_id(candidate.id, candidate.version)), owner
        )
        await service.verify(create_ref_id(row.id, row.version), owner)
        pin = await service.pin(
            create_ref_id(row.id, row.version),
            candidate,
            handler_key="service_task",
            handler_version="1",
        )
        await service.rotate(
            create_ref_id(row.id, row.version),
            SecretRotationDTO(secret_ref="credential", secret_version="2"),
            owner,
        )
        await service.execute(pin, candidate)
        assert provider.versions[-1] == "1"
        with pytest.raises(VersionConflictException):
            await service.pin(
                create_ref_id(row.id, row.version),
                candidate,
                handler_key="service_task",
                handler_version="1",
            )
        await service.revoke(create_ref_id(row.id, row.version), owner)
        with pytest.raises(VersionConflictException):
            await service.execute(pin, candidate)
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_group_membership_and_provider_failure_are_rechecked_and_redacted() -> None:

    from apps.integrations.domain.dto import ConnectionQuery
    from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
    from core.history import history_tables
    from utils.exceptions import ServiceUnavailableException

    class FailingProvider(FakeProvider):
        fail = False

        @override
        async def invoke(self, pin):
            if self.fail:
                raise RuntimeError("private-value provider exception")
            return await super().invoke(pin)

    provider = FailingProvider()
    async with SessionFactory() as session:
        owner = UserEntity(username=f"owner-{uuid7()}", hashed_password="hash")
        member = UserEntity(username=f"member-{uuid7()}", hashed_password="hash")
        group = WorkGroupEntity(code=f"G{uuid7().hex}", name="Ops")
        session.add_all([owner, member, group])
        await session.flush()
        membership = WorkGroupMemberEntity(work_group_id=group.id, user_id=member.id)
        session.add(membership)
        await session.flush()
        service = ConnectionService(session, provider)
        row = await service.create(
            ConnectionCreateDTO(
                code=f"C{uuid7().hex}",
                name="Connection",
                provider="https_status",
                kind="SERVICE",
                non_secret_config=ConnectionConfig(endpoint_key="approved"),
                secret_ref="credential",
                secret_version="1",
            ),
            owner,
        )
        grant = await service.grant(
            create_ref_id(row.id, row.version),
            GrantDTO(work_group_ref_id=create_ref_id(group.id, group.version)),
            owner,
        )
        await service.verify(create_ref_id(row.id, row.version), owner)
        pin = await service.pin(
            create_ref_id(row.id, row.version),
            member,
            handler_key="service_task",
            handler_version="1",
        )
        assert (await service.search(ConnectionQuery(), member)).total == 1
        provider.fail = True
        with pytest.raises(ServiceUnavailableException) as error:
            await service.execute(pin, member)
        assert "private-value" not in str(error.value)
        await service.verify(create_ref_id(row.id, row.version), owner)
        assert row.verification_status == "FAILED"
        membership.is_active = False
        await session.flush()
        with pytest.raises(NotAllowedException):
            await service.execute(pin, member)
        assert (await service.search(ConnectionQuery(), member)).total == 0
        history = history_tables()["integration_connection"]
        rows = (
            await (await session.connection()).execute(
                history.select().where(history.c.ENTITY_ID == row.id)
            )
        ).all()
        assert "private-value" not in repr(rows) and "credential" not in repr(rows)
        await service.remove_grant(
            create_ref_id(row.id, row.version), create_ref_id(grant.id, grant.version), owner
        )
        await session.rollback()
    await engine.dispose()
