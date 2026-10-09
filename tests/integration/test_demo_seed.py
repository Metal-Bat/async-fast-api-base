"""The supported installation uses real PostgreSQL and preserves operator changes."""

import os

import pytest
from scripts.bootstrap_application import open_manifest
from sqlmodel import select

from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.requests.application.demo import install_demo
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.domain.auth_entity import UserRoleEntity
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowVersionEntity
from core.deps import SessionFactory, engine
from utils.exceptions import VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_demo_publishes_two_templates_and_preserves_operator_changes(tmp_path):
    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(
                    session, roles=tuple(a.persona for a in manifest.accounts)
                )
                await install_accounts(session, manifest)
                await StepTypeService(session, get_registry()).reconcile()
                first = await install_demo(session, manifest)
                assert len(first.request_types) == 2
                assert set(first.cases) == {
                    "draft",
                    "waiting",
                    "correction",
                    "rejected",
                    "completed",
                }
            async with SessionFactory() as session, session.begin():
                before = {
                    v.id: v.checksum for v in (await session.exec(select(FormVersionEntity))).all()
                }
                workflows = {
                    v.id: v.graph_checksum
                    for v in (await session.exec(select(WorkflowVersionEntity))).all()
                }
                second = await install_demo(session, manifest)
                assert first == second
                assert before == {
                    v.id: v.checksum for v in (await session.exec(select(FormVersionEntity))).all()
                }
                assert workflows == {
                    v.id: v.graph_checksum
                    for v in (await session.exec(select(WorkflowVersionEntity))).all()
                }
                root = (
                    await session.exec(
                        select(FormDefinitionEntity).where(
                            FormDefinitionEntity.code
                            == f"demo.{manifest.installation_id.hex}.purchase"
                        )
                    )
                ).one()
                from apps.forms.application.service import FormService
                from apps.forms.domain.dto import FormDocuments, FormVersionCreateDTO
                from core.ref_id import create_ref_id

                published = (
                    await session.exec(
                        select(FormVersionEntity).where(
                            FormVersionEntity.form_definition_id == root.id
                        )
                    )
                ).one()
                await FormService(session).create_version(
                    FormVersionCreateDTO(
                        form_ref_id=create_ref_id(root.id, root.version),
                        number=2,
                        **FormDocuments.model_validate(
                            published, from_attributes=True
                        ).model_dump(),
                    )
                )
                with pytest.raises(VersionConflictException):
                    await install_demo(session, manifest, check_only=True)
                root.name = "Operator-owned purchase form"
            with pytest.raises(VersionConflictException):
                async with SessionFactory() as session, session.begin():
                    await install_demo(session, manifest)
            async with SessionFactory() as session:
                root = (
                    await session.exec(
                        select(FormDefinitionEntity).where(
                            FormDefinitionEntity.code
                            == f"demo.{manifest.installation_id.hex}.purchase"
                        )
                    )
                ).one()
                assert root.name == "Operator-owned purchase form"
        finally:
            await engine.dispose()


@pytest.mark.anyio
async def test_installation_converges_and_does_not_regrant_revoked_access(tmp_path):
    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(
                    session, roles=tuple(a.persona for a in manifest.accounts)
                )
                first = await install_accounts(session, manifest)
                assert len(first.created_users) == 3
            async with SessionFactory() as session, session.begin():
                repeat = await install_accounts(session, manifest)
                assert not repeat.created_users
                user = (
                    await session.exec(
                        select(UserEntity).where(
                            UserEntity.username == manifest.accounts[0].username
                        )
                    )
                ).one()
                assert not user.is_superuser
                assignment = (
                    await session.exec(
                        select(UserRoleEntity).where(UserRoleEntity.user_id == user.id)
                    )
                ).one()
                await session.delete(assignment)
                user.first_name = "Operator edit"
            async with SessionFactory() as session, session.begin():
                await install_accounts(session, manifest)
                user = (
                    await session.exec(
                        select(UserEntity).where(
                            UserEntity.username == manifest.accounts[0].username
                        )
                    )
                ).one()
                assert user.first_name == "Operator edit"
                assert not (
                    await session.exec(
                        select(UserRoleEntity).where(UserRoleEntity.user_id == user.id)
                    )
                ).all()
        finally:
            await engine.dispose()


@pytest.mark.anyio
async def test_failed_installation_rolls_back_and_can_be_repaired(tmp_path):
    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            with pytest.raises(RuntimeError, match="interrupt"):
                async with SessionFactory() as session, session.begin():
                    await reconcile_permissions(
                        session, roles=tuple(a.persona for a in manifest.accounts)
                    )
                    await install_accounts(session, manifest)
                    raise RuntimeError("interrupt")
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(
                    session, roles=tuple(a.persona for a in manifest.accounts)
                )
                checked = await install_accounts(session, manifest, check_only=True)
                assert len(checked.missing_users) == 3
                repaired = await install_accounts(session, manifest)
                assert len(repaired.created_users) == 3
        finally:
            await engine.dispose()
