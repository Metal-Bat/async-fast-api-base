"""Demo group repairs preserve deliberate membership revocation."""

import os
from uuid import uuid5

import pytest
from scripts.bootstrap_application import open_manifest
from sqlmodel import select

from apps.requests.application.demo_groups import install_demo_groups
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from core.deps import SessionFactory, engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_demo_groups_are_owned_and_do_not_restore_revoked_members(tmp_path):
    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("requester", "reviewer", "designer"))
                await install_accounts(session, manifest)
                first = await install_demo_groups(session, manifest)
                assert len(first) == 2
                group = await session.get(
                    WorkGroupEntity, uuid5(manifest.installation_id, "group:reviewer")
                )
                assert group is not None
                member = (
                    await session.exec(
                        select(WorkGroupMemberEntity).where(
                            WorkGroupMemberEntity.work_group_id == group.id
                        )
                    )
                ).one()
                member.is_active = False
                group.name = "Operator group title"
                await session.flush()
                repeated = await install_demo_groups(session, manifest)
                assert repeated["reviewer"] != first["reviewer"]
                assert member.is_active is False and group.name == "Operator group title"
        finally:
            await engine.dispose()
