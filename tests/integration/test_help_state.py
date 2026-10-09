"""Real metadata-only help persistence keeps actors, revisions and locales independent."""

import os
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from scripts.bootstrap_application import open_manifest

from apps.users.application.bootstrap import install_accounts
from apps.users.application.help_state import HelpStateService
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.application.preferences import PersonalSettingsService
from apps.users.data.help_release import load_help_release
from apps.users.domain.entity import UserEntity
from apps.users.domain.help_state import HelpAction, HelpReleaseMetadata, HelpStateQuery
from apps.users.domain.preferences import PreferencesPatch
from core.deps import SessionFactory, engine
from main import app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_help_http_requires_an_explicit_action_and_self_ownership(tmp_path):
    metadata = HelpReleaseMetadata(
        release_key="synthetic-http",
        items=[{"help_key": "requests.start", "revision": "1", "locales": ["en", "fa"]}],
    )
    app.dependency_overrides[load_help_release] = lambda: metadata
    try:
        with open_manifest(
            tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
        ) as manifest:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(
                    session, roles=tuple(a.persona for a in manifest.accounts)
                )
                await install_accounts(session, manifest)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                account = manifest.accounts[0]
                login = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": account.username,
                        "password": account.password.get_secret_value(),
                    },
                )
                assert login.status_code == 200
                headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
                read = await client.get("/api/v1/me/help-state", headers=headers)
                assert read.status_code == 200, read.text
                assert read.json()["data"]["states"]["total"] == 0
                action = {"help_key": "requests.start", "revision": "1", "locale": "fa"}
                seen = await client.post("/api/v1/me/help-state/seen", headers=headers, json=action)
                assert seen.status_code == 200 and seen.json()["data"]["saved"]
                assert seen.headers["Cache-Control"] == "private, no-store"
                assert (
                    await client.post(
                        "/api/v1/me/help-state/seen",
                        headers=headers,
                        json=action | {"actor_id": "other"},
                    )
                ).status_code == 422
                assert (
                    await client.post("/api/v1/me/help-state/seen", json=action)
                ).status_code == 401
                reset = await client.post("/api/v1/me/help-state/reset", headers=headers, json={})
                assert reset.status_code == 200 and reset.json()["data"]["deleted_records"] == 1
    finally:
        app.dependency_overrides.pop(load_help_release, None)
        await engine.dispose()


@pytest.mark.anyio
async def test_help_repeat_revision_locale_isolation_and_deliberate_self_reset():
    metadata = HelpReleaseMetadata(
        release_key="synthetic-acceptance",
        items=[{"help_key": "requests.start", "revision": "1", "locales": ["en", "fa"]}],
    )
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(username=f"help-{token}", hashed_password=token)
            other = UserEntity(username=f"help-other-{token}", hashed_password=token)
            session.add_all([actor, other])
            await session.flush()
            service = HelpStateService(session, metadata)
            assert (await service.read(actor, HelpStateQuery())).states.total == 0
            action = HelpAction(help_key="requests.start", revision="1", locale="en")
            first = await service.record(actor, action)
            assert (
                first.saved and first.state is not None and first.state.first_viewed_at is not None
            )
            repeat = await service.record(actor, action)
            assert repeat.state is not None
            assert repeat.state.first_viewed_at == first.state.first_viewed_at
            dismissed = await service.record(actor, action, dismiss=True)
            duplicate = await service.record(actor, action, dismiss=True)
            assert dismissed.state is not None and duplicate.state is not None
            assert duplicate.state.dismissed_at == dismissed.state.dismissed_at
            await service.record(actor, action.model_copy(update={"locale": "fa"}))
            await service.record(other, action)
            assert (await service.read(actor, HelpStateQuery())).states.total == 2
            assert (await service.read(other, HelpStateQuery())).states.total == 1
            assert not (
                await service.record(actor, action.model_copy(update={"revision": "old"}))
            ).saved
            assert (
                await service.record(actor, action.model_copy(update={"help_key": "unknown"}))
            ).reason == "unknown_key"
            assert (
                await HelpStateService(session, None).record(actor, action)
            ).reason == "manifest_unavailable"
            newer = HelpReleaseMetadata(
                release_key="synthetic-v2",
                items=[{"help_key": "requests.start", "revision": "2", "locales": ["en", "fa"]}],
            )
            await HelpStateService(session, newer).record(
                actor, action.model_copy(update={"revision": "2"})
            )
            assert (await service.read(actor, HelpStateQuery())).states.total == 3
            personal = PersonalSettingsService(session)
            defaults = await personal.read(actor)
            await personal.apply(
                actor, PreferencesPatch(ref_id=defaults.ref_id, appearance={"theme_mode": "dark"})
            )
            assert (await service.reset(actor)).deleted_records == 3
            assert (await service.reset(actor)).deleted_records == 0
            assert (await service.read(other, HelpStateQuery())).states.total == 1
            assert (await personal.read(actor)).appearance.theme_mode == "dark"
    finally:
        await engine.dispose()
