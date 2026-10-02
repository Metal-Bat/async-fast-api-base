"""PostgreSQL client registration, release and authenticated session binding."""

import os
from uuid import uuid7

import pytest
from sqlmodel import select

from apps.clients.application.service import ClientService
from apps.clients.domain.dto import ClientCreateDTO, ClientReleaseCreateDTO
from apps.users.domain.auth_entity import AuthSessionEntity
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from utils.date_utils import get_datetime_utc
from utils.exceptions import InvalidCredentialError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_confidential_client_binding_ignores_forged_presentation_hints() -> None:
    async with SessionFactory() as session:
        service = ClientService(session)
        client, secret = await service.create_client(
            ClientCreateDTO(
                code=f"DESKTOP_{uuid7().hex}",
                name="Desktop",
                kind="DESKTOP",
                platform="linux",
                confidential=True,
            )
        )
        release = await service.create_release(
            client.id,
            ClientReleaseCreateDTO(
                version="2.10",
                api_version="v1",
                renderer_capabilities=["bpms.render/1"],
            ),
        )
        actor = UserEntity(username=f"client-user-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        auth_session = AuthSessionEntity(
            user_id=actor.id,
            family_id=uuid7(),
            refresh_token_hash=uuid7().hex,
            expires_at=get_datetime_utc(),
            client_id=client.id,
            client_release_id=release.id,
        )
        session.add(auth_session)
        await session.flush()
        bound = await service.authenticate(client.code, secret, release.release_version)
        assert bound.client_id == client.id and bound.release_id == release.id
        assert bound.trusted and bound.kind == "DESKTOP"
        resolved = await service.for_session(auth_session)
        assert resolved == bound
        with pytest.raises(InvalidCredentialError):
            await service.authenticate(client.code, "wrong", release.release_version)
        with pytest.raises(InvalidCredentialError):
            await service.authenticate("unknown", secret, release.release_version)
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
async def test_login_and_refresh_keep_server_bound_client_release() -> None:
    from apps.users.application.auth_service import AuthService, hash_secret
    from apps.users.domain.auth_dto import LoginDTO
    from utils.security import hash_password

    async with SessionFactory() as session:
        clients = ClientService(session)
        client, secret = await clients.create_client(
            ClientCreateDTO(
                code=f"B2B_{uuid7().hex}",
                name="Integration",
                kind="B2B",
                platform="server",
                confidential=True,
            )
        )
        release = await clients.create_release(
            client.id, ClientReleaseCreateDTO(version="2.10", api_version="v1")
        )
        actor = UserEntity(
            username=f"client-login-{uuid7().hex}",
            hashed_password=await hash_password("correct-horse-battery-staple"),
        )
        session.add(actor)
        await session.commit()

    async with SessionFactory() as session:
        auth = AuthService(session)
        pair = await auth.login(
            LoginDTO(
                username=actor.username,
                password="correct-horse-battery-staple",
                client_key=client.code,
                client_secret=secret,
                client_release="2.10",
            ),
            request_id=None,
            ip_address=None,
            user_agent="forged-desktop-agent",
        )
        current = await session.exec(
            select(AuthSessionEntity).where(
                AuthSessionEntity.refresh_token_hash == hash_secret(pair.refresh_token)
            )
        )
        bound = current.one()
        assert bound.client_id == client.id and bound.client_release_id == release.id
        rotated = await auth.refresh(pair.refresh_token)
        next_session = await session.exec(
            select(AuthSessionEntity).where(
                AuthSessionEntity.refresh_token_hash == hash_secret(rotated.refresh_token)
            )
        )
        replacement = next_session.one()
        assert replacement.client_id == client.id
        assert replacement.client_release_id == release.id
    await engine.dispose()
