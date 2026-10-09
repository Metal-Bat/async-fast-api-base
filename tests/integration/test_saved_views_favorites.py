"""Actual persisted self state obeys replay, concurrency, visibility and schema recovery."""

import os
from uuid import uuid7

import anyio
import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.application.personal_collections import PersonalCollectionsService
from apps.users.domain.auth_entity import RoleEntity, UserRoleEntity
from apps.users.domain.entity import UserEntity
from apps.users.domain.personal_entity import PersonalItemEntity
from apps.users.domain.saved_views import FavoriteInput, PersonalItemQuery, SavedViewInput
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id, open_ref_id
from main import app
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_saved_view_http_contract_is_private_and_strict(tmp_path):
    from scripts.bootstrap_application import open_manifest

    from apps.users.application.bootstrap import install_accounts
    from apps.users.application.permission_catalog import reconcile_permissions

    with open_manifest(
        tmp_path / "manifest.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("requester", "reviewer", "designer"))
                await install_accounts(session, manifest)
            account = next(item for item in manifest.accounts if item.persona == "designer")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                login = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "username": account.username,
                        "password": account.password.get_secret_value(),
                    },
                )
                headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
                data = {
                    "name": "My forms",
                    "resource_kind": "forms",
                    "command_key": "http-one",
                    "column_keys": ["name"],
                    "query": {},
                }
                created = await client.post("/api/v1/me/saved-views", headers=headers, json=data)
                assert created.status_code == 200, created.text
                assert created.headers["cache-control"] == "private, no-store"
                reference = created.json()["data"]["ref_id"]
                applied = await client.post(
                    f"/api/v1/me/saved-views/{reference}/apply", headers=headers, json={}
                )
                assert applied.status_code == 200 and applied.json()["data"]["query"]["page"] == 1
                listing = await client.post(
                    "/api/v1/me/saved-views/search", headers=headers, json={}
                )
                assert listing.json()["result"]["total"] == 1
                invalid = await client.post(
                    "/api/v1/me/saved-views", headers=headers, json=data | {"user_id": "outsider"}
                )
                assert invalid.status_code == 422
                assert (await client.get(f"/api/v1/me/saved-views/{reference}")).status_code == 401
                history = await client.post(
                    f"/api/v1/me/saved-views/{reference}/history", headers=headers, json={}
                )
                assert history.status_code == 200 and history.json()["result"]["total"] >= 1
        finally:
            await engine.dispose()


@pytest.mark.anyio
async def test_presets_replay_roundtrip_isolation_schema_drift_and_favorite_refresh():
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(
                username=f"presets-{token}", hashed_password=token, is_superuser=True
            )
            outsider = UserEntity(
                username=f"presets-other-{token}", hashed_password=token, is_superuser=True
            )
            session.add_all([actor, outsider])
            await session.flush()
            service = PersonalCollectionsService(session)
            data = SavedViewInput(
                name="Private list",
                resource_kind="forms",
                command_key="one",
                column_keys=["name"],
                query={
                    "filters": [
                        {
                            "field_name": "name",
                            "operation": "contains",
                            "value": "confidential filter",
                        }
                    ]
                },
                page_size=40,
            )
            view = await service.create_view(actor, data)
            assert (await service.create_view(actor, data)).ref_id == view.ref_id
            assert view.query["filters"] == [
                {"field_name": "name", "operation": "contains", "value": "confidential filter"}
            ]
            assert view.page_size == 40
            updated_data = data.model_copy(
                update={"name": "Repaired private list", "command_key": "update-one"}
            )
            updated = await service.update_view(actor, view.ref_id, updated_data)
            assert updated.ref_id != view.ref_id
            assert (
                await service.update_view(actor, view.ref_id, updated_data)
            ).ref_id == updated.ref_id
            with pytest.raises(VersionConflictException):
                await service.update_view(
                    actor,
                    view.ref_id,
                    updated_data.model_copy(update={"command_key": "stale-update"}),
                )
            view = updated
            with pytest.raises(VersionConflictException):
                await service.create_view(actor, data.model_copy(update={"name": "Changed replay"}))
            with pytest.raises(NotFoundException):
                await service.get_view(outsider, view.ref_id)
            assert (await service.search_views(outsider, PersonalItemQuery())).total == 0
            root = await FormService(session).create(
                FormCreateDTO(code=f"preset.{token}", name="Original target"), actor.id
            )
            favorite = await service.create_favorite(
                actor, FavoriteInput(kind="forms", ref_id=create_ref_id(root.id, root.version))
            )
            again = await service.create_favorite(
                actor, FavoriteInput(kind="forms", ref_id=create_ref_id(root.id, root.version))
            )
            assert favorite.ref_id == again.ref_id
            await FormService(session).update(
                favorite.target.ref_id, FormCreateDTO(code=root.code, name="Renamed target")
            )
            page = await service.search_favorites(actor, PersonalItemQuery())
            assert page.total == 1 and page.items[0].target.label == "Renamed target"
            assert page.items[0].target.locator == favorite.target.locator
            actor.is_superuser = False
            await session.flush()
            assert (await service.search_favorites(actor, PersonalItemQuery())).total == 0
            assert (await service.search_views(actor, PersonalItemQuery())).total == 0
            actor.is_superuser = True
            await session.flush()
            root.deleted_at = get_datetime_utc()
            await session.flush()
            assert (await service.search_favorites(actor, PersonalItemQuery())).total == 0
            await service.delete(actor, favorite.ref_id, "favorite")
            row = await session.get(PersonalItemEntity, open_ref_id(view.ref_id)[0])
            assert row is not None
            doc = dict(row.document)
            doc["current"] = dict(doc["current"], schema_version=99)
            row.document = doc
            await session.flush()
            incompatible = await service.get_view(actor, create_ref_id(row.id, row.version))
            assert incompatible.compatible is False and incompatible.query == view.query
            applied = await service.apply_view(actor, incompatible.ref_id)
            assert applied.compatible is False and applied.query is None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_concurrent_default_selection_leaves_one_default():
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(username=f"defaults-{token}", hashed_password=token)
            session.add(actor)
            await session.flush()
            await reconcile_permissions(session, roles=("designer",))
            role = (
                await session.exec(select(RoleEntity).where(RoleEntity.name == "app.designer.v1"))
            ).one()
            session.add(UserRoleEntity(user_id=actor.id, role_id=role.id))
            await session.flush()
            identity = actor.id
            service = PersonalCollectionsService(session)
            views = [
                await service.create_view(
                    actor,
                    SavedViewInput(
                        name=f"View {index}", resource_kind="forms", command_key=str(index)
                    ),
                )
                for index in range(2)
            ]
            root = await FormService(session).create(
                FormCreateDTO(code=f"default.{token}", name="Concurrent favorite"), actor.id
            )
            target_ref = create_ref_id(root.id, root.version)

        async def choose(reference):
            async with SessionFactory() as session, session.begin():
                actor = await session.get(UserEntity, identity)
                assert actor is not None
                service = PersonalCollectionsService(session)
                await service.create_favorite(actor, FavoriteInput(kind="forms", ref_id=target_ref))
                await service.set_default(actor, reference)

        async with anyio.create_task_group() as group:
            for view in views:
                group.start_soon(choose, view.ref_id)
        async with SessionFactory() as session:
            defaults = (
                await session.exec(
                    select(PersonalItemEntity).where(
                        PersonalItemEntity.user_id == identity,
                        PersonalItemEntity.is_default == True,
                    )
                )
            ).all()
            assert len(defaults) == 1
            favorite_rows = (
                await session.exec(
                    select(PersonalItemEntity).where(
                        PersonalItemEntity.user_id == identity,
                        PersonalItemEntity.kind == "favorite",
                    )
                )
            ).all()
            assert len(favorite_rows) == 1
    finally:
        await engine.dispose()
