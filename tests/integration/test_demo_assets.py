"""Demo assets use the normal private upload owner and actual storage integrity metadata."""

import os

import pytest
from scripts.bootstrap_application import open_manifest

from apps.requests.application.demo_assets import install_demo_assets
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from core.deps import SessionFactory, engine
from utils.s3 import ensure_bucket

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_PRIVATE_TRANSFERS") != "1",
        reason="requires disposable paired transfer services",
    ),
]


@pytest.mark.anyio
async def test_demo_assets_real_storage_is_idempotent(tmp_path):
    await ensure_bucket()
    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("requester", "reviewer", "designer"))
                await install_accounts(session, manifest)
            first = await install_demo_assets(manifest)
            assert set(first) == {"file", "image"}
            assert await install_demo_assets(manifest) == first
            assert await install_demo_assets(manifest, check_only=True) == first
        finally:
            await engine.dispose()
