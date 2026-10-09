"""Personal settings remain private, persistent and safe under stale concurrent writes."""

import os
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from scripts.bootstrap_application import open_manifest
from sqlmodel import select

from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.application.preferences import PersonalSettingsService
from apps.users.domain.entity import UserEntity
from apps.users.domain.preferences import PreferencesPatch, ProfilePatch
from apps.users.domain.preferences_entity import UserPreferencesEntity
from core.deps import SessionFactory, engine
from main import app
from utils.exceptions import NotFoundException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_self_settings_http_contract_and_avatar_ownership(tmp_path):
    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
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
                read = await client.get("/api/v1/me/preferences", headers=headers)
                assert read.status_code == 200, read.text
                assert read.headers["Cache-Control"] == "private, no-store"
                current = read.json()["data"]
                changed = await client.patch(
                    "/api/v1/me/preferences",
                    headers=headers,
                    json={"ref_id": current["ref_id"], "locale": {"language": "fa"}},
                )
                assert (
                    changed.status_code == 200
                    and changed.json()["data"]["locale"]["language"] == "fa"
                )
                stale = await client.patch(
                    "/api/v1/me/preferences",
                    headers=headers,
                    json={"ref_id": current["ref_id"], "appearance": {"theme_mode": "dark"}},
                )
                assert stale.status_code == 409
                privileged = await client.patch(
                    "/api/v1/me/preferences",
                    headers=headers,
                    json={"ref_id": changed.json()["data"]["ref_id"], "is_superuser": True},
                )
                assert privileged.status_code == 422
                profile = await client.get("/api/v1/me/profile", headers=headers)
                assert profile.status_code == 200
                cleared = await client.patch(
                    "/api/v1/me/profile",
                    headers=headers,
                    json={
                        "ref_id": profile.json()["data"]["ref_id"],
                        "avatar_ref_id": None,
                        "first_name": "Synthetic",
                    },
                )
                assert (
                    cleared.status_code == 200 and cleared.json()["data"]["avatar_ref_id"] is None
                )
                assert (await client.get("/api/v1/me/preferences")).status_code == 401
        finally:
            await engine.dispose()


@pytest.mark.anyio
async def test_settings_persist_conflict_and_isolate_self():
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            first = UserEntity(username=f"settings-{token}", hashed_password=token)
            other = UserEntity(username=f"outsider-{token}", hashed_password=token)
            session.add_all([first, other])
            await session.flush()
            first_id, other_id = first.id, other.id
            service = PersonalSettingsService(session)
            defaults = await service.read(first)
            assert not (
                await session.exec(
                    select(UserPreferencesEntity).where(UserPreferencesEntity.user_id == first.id)
                )
            ).all()
            changed = await service.apply(
                first,
                PreferencesPatch(
                    ref_id=defaults.ref_id,
                    appearance={"theme_mode": "dark"},
                    locale={"language": "fa", "timezone": "Asia/Tehran"},
                ),
            )
            assert changed.ref_id != defaults.ref_id
        async with SessionFactory() as session, session.begin():
            first = await session.get(UserEntity, first_id)
            other = await session.get(UserEntity, other_id)
            assert first is not None and other is not None
            service = PersonalSettingsService(session)
            read = await service.read(first)
            assert read.appearance.theme_mode == "dark" and read.locale.language == "fa"
            assert (await service.read(other)).appearance.theme_mode == "system"
            with pytest.raises(NotFoundException):
                await service.apply(
                    other, PreferencesPatch(ref_id=read.ref_id, workspace={"page_size": 30})
                )
            updated = await service.apply(
                first, PreferencesPatch(ref_id=read.ref_id, workspace={"page_size": 30})
            )
            with pytest.raises(VersionConflictException):
                await service.apply(
                    first, PreferencesPatch(ref_id=read.ref_id, locale={"language": "en"})
                )
            assert updated.locale.language == "fa"
            unchanged = await service.apply(first, PreferencesPatch(ref_id=updated.ref_id))
            assert unchanged.ref_id == updated.ref_id
            reset = await service.apply(
                first, PreferencesPatch(ref_id=updated.ref_id, appearance=None)
            )
            assert reset.appearance.theme_mode == "system" and reset.locale.language == "fa"
            profile = await service.profile(first)
            new_profile = await service.update_profile(
                first,
                ProfilePatch(
                    ref_id=profile.ref_id,
                    first_name="Synthetic",
                    last_name="Person",
                    avatar_ref_id=None,
                ),
            )
            assert new_profile.first_name == "Synthetic"
            assert (await service.read(first)).workspace.page_size == 30
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_setting_edits_have_one_explicit_conflict():
    from anyio import create_task_group

    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(username=f"concurrent-settings-{token}", hashed_password=token)
            session.add(actor)
            await session.flush()
            actor_id = actor.id
            original = await PersonalSettingsService(session).read(actor)

        results = []

        async def edit(appearance):
            async with SessionFactory() as session, session.begin():
                actor = await session.get(UserEntity, actor_id)
                assert actor is not None
                data = (
                    PreferencesPatch(ref_id=original.ref_id, appearance={"theme_mode": "dark"})
                    if appearance
                    else PreferencesPatch(ref_id=original.ref_id, locale={"language": "fa"})
                )
                try:
                    await PersonalSettingsService(session).apply(actor, data)
                except VersionConflictException:
                    results.append("conflict")
                    return
                results.append("updated")

        async with create_task_group() as tasks:
            tasks.start_soon(edit, True)
            tasks.start_soon(edit, False)
        assert sorted(results) == ["conflict", "updated"]
        async with SessionFactory() as session:
            actor = await session.get(UserEntity, actor_id)
            assert actor is not None
            current = await PersonalSettingsService(session).read(actor)
            assert (current.appearance.theme_mode == "dark") != (current.locale.language == "fa")
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_avatar_binding_is_self_owned_and_removal_preserves_private_media():
    """Authorization uses real media metadata; full object transfers are tested separately."""
    from apps.media.domain.entity import UserUploadEntity
    from core.ref_id import create_ref_id
    from utils.date_utils import get_datetime_utc

    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(username=f"avatar-{token}", hashed_password=token)
            other = UserEntity(username=f"avatar-outsider-{token}", hashed_password=token)
            session.add_all([actor, other])
            await session.flush()
            image = UserUploadEntity(
                user_id=actor.id,
                kind="image",
                object_key=f"metadata-only/{token}",
                original_filename="synthetic.webp",
                content_type="image/webp",
                size_bytes=8,
                sha256="0" * 64,
            )
            session.add(image)
            await session.flush()
            service = PersonalSettingsService(session)
            outsider = await service.profile(other)
            image_ref = create_ref_id(image.id, image.version)
            with pytest.raises(NotFoundException):
                await service.update_profile(
                    other,
                    ProfilePatch(
                        ref_id=outsider.ref_id,
                        first_name="Must not persist",
                        avatar_ref_id=image_ref,
                    ),
                )
            assert (await service.profile(other)).first_name is None
            own = await service.profile(actor)
            bound = await service.update_profile(
                actor, ProfilePatch(ref_id=own.ref_id, avatar_ref_id=image_ref)
            )
            assert bound.avatar_ref_id == image_ref
            detached = await service.update_profile(
                actor, ProfilePatch(ref_id=bound.ref_id, avatar_ref_id=None)
            )
            assert detached.avatar_ref_id is None and image.deleted_at is None
            actor.deleted_at = get_datetime_utc()
            await session.flush()
            with pytest.raises(NotFoundException):
                await service.read(actor)
    finally:
        await engine.dispose()
