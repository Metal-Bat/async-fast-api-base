"""Demo personal projections use actual owners and converge without duplicate records."""

import os

import pytest
from scripts.bootstrap_application import open_manifest

from apps.requests.application.demo import install_demo
from apps.requests.application.demo_personal import install_personal_demo
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from core.deps import SessionFactory, engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_demo_personal_service_seeding_is_repeatable(tmp_path):
    try:
        with open_manifest(
            tmp_path / "accounts.json", database=os.environ["POSTGRES_DB"], create=True
        ) as manifest:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("requester", "reviewer", "designer"))
                await install_accounts(session, manifest)
                demo = await install_demo(session, manifest)
                first = await install_personal_demo(session, manifest, demo)
            async with SessionFactory() as session, session.begin():
                assert await install_personal_demo(session, manifest, demo) == first
                assert first == {
                    "actors": 3,
                    "calendars": 3,
                    "saved_views": 3,
                    "favorites": 1,
                    "notices": 3,
                    "help_states": 3,
                }
    finally:
        await engine.dispose()
