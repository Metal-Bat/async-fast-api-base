"""Durable links refresh references without changing pins or leaking revoked targets."""

import os
from uuid import uuid7

import pytest
from sqlmodel import select

from apps.designer.application.resource_links import ResourceLinkService
from apps.designer.application.service import DesignerService
from apps.designer.domain.dto import DesignerQuery
from apps.designer.domain.resource_links import ResourceReference
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO
from apps.forms.domain.entity import FormDefinitionEntity
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.domain.auth_entity import RoleEntity, UserRoleEntity
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_resource_links_refresh_and_hide_deleted_or_revoked_targets():
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(username=f"links-{token}", hashed_password=token)
            outsider = UserEntity(username=f"links-other-{token}", hashed_password=token)
            session.add_all([actor, outsider])
            await session.flush()
            await reconcile_permissions(session, roles=("designer",))
            role = (
                await session.exec(select(RoleEntity).where(RoleEntity.name == "app.designer.v1"))
            ).one()
            grant = UserRoleEntity(user_id=actor.id, role_id=role.id)
            session.add(grant)
            await session.flush()
            forms = FormService(session)
            root = await forms.create(
                FormCreateDTO(code=f"links.{token}", name="Original synthetic form"), actor.id
            )
            links = ResourceLinkService(session)
            link = await links.mint(
                ResourceReference(kind="forms", ref_id=create_ref_id(root.id, root.version)), actor
            )
            updated = await forms.update(
                link.ref_id, FormCreateDTO(code=root.code, name="Updated synthetic form")
            )
            refreshed = await links.resolve(link.locator, actor)
            assert refreshed.locator == link.locator
            assert refreshed.ref_id != link.ref_id
            assert refreshed.label == updated.name
            assert open_ref_id(refreshed.ref_id)[0] == root.id
            with pytest.raises(NotFoundException):
                await links.resolve(link.locator, outsider)
            root.is_active = False
            root.updated_at = get_datetime_utc()
            await session.flush()
            assert (await links.resolve(link.locator, actor)).available is False
            with pytest.raises(NotFoundException):
                await links.summary(
                    ResourceReference(kind="forms", ref_id=refreshed.ref_id), actor, selection=True
                )
            await session.delete(grant)
            await session.flush()
            with pytest.raises(NotFoundException):
                await links.resolve(link.locator, actor)
            actor.is_superuser = True
            root.deleted_at = get_datetime_utc()
            await session.flush()
            with pytest.raises(NotFoundException):
                await links.resolve(link.locator, actor)
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_selected_summary_is_not_limited_to_first_search_page():
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(
                username=f"selected-{token}", hashed_password=token, is_superuser=True
            )
            session.add(actor)
            await session.flush()
            rows = [
                FormDefinitionEntity(
                    code=f"selected.{token}.{index:02}",
                    name=f"Selected fixture {token} {index:02}",
                    owner_user_id=actor.id,
                )
                for index in range(25)
            ]
            session.add_all(rows)
            await session.flush()
            page = await DesignerService(session).selector(
                "forms", DesignerQuery(search=token, size=2), actor
            )
            selected_ref = create_ref_id(rows[-1].id, rows[-1].version)
            assert page.total == 25
            assert selected_ref not in {item.key for item in page.items}
            summary = await ResourceLinkService(session).summary(
                ResourceReference(kind="forms", ref_id=selected_ref), actor, selection=True
            )
            assert summary.label == rows[-1].name
            assert summary.ref_id == selected_ref
    finally:
        await engine.dispose()
