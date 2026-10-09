"""Wave-four handoffs use real ordinary identities and their actual HTTP contracts."""

import os
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from scripts.bootstrap_application import open_manifest
from sqlmodel import select

from apps.forms.domain.entity import FormVersionEntity
from apps.requests.application.demo import install_demo
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from main import app
from utils.date_utils import get_datetime_utc

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_wave_four_contracts_use_actual_permissions_and_list_queries(tmp_path):
    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("requester", "reviewer", "designer"))
                await install_accounts(session, manifest)
                await install_demo(session, manifest)
                versions = (await session.exec(select(FormVersionEntity))).all()
                version = next(
                    row
                    for row in versions
                    if (row.template_source or {}).get("installation_id")
                    == str(manifest.installation_id)
                )
                reference = create_ref_id(version.id, version.version)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                headers = {}
                for account in manifest.accounts:
                    login = await client.post(
                        "/api/v1/auth/login",
                        json={
                            "username": account.username,
                            "password": account.password.get_secret_value(),
                        },
                    )
                    assert login.status_code == 200
                    headers[account.persona] = {
                        "Authorization": "Bearer " + login.json()["data"]["access_token"]
                    }
                metadata = await client.get(
                    "/api/v1/designer/inspector-contract", headers=headers["designer"]
                )
                assert metadata.status_code == 200 and len(metadata.json()["data"]["fields"]) == 20
                assert metadata.headers["cache-control"] == "private, no-store"
                assert (
                    await client.get(
                        "/api/v1/designer/inspector-contract", headers=headers["requester"]
                    )
                ).status_code == 403
                validation = await client.post(
                    "/api/v1/designer/config-validation",
                    headers=headers["designer"],
                    json={
                        "handler_key": "human_task",
                        "handler_version": "1",
                        "config": {"form_version_ref": None},
                    },
                )
                assert validation.status_code == 200 and validation.json()["data"]["valid"] is False
                link = await client.post(
                    "/api/v1/resource-links",
                    headers=headers["designer"],
                    json={"kind": "form_versions", "ref_id": reference},
                )
                assert link.status_code == 200
                assert link.json()["data"]["number"] == 1
                locator = link.json()["data"]["locator"]
                resolved = await client.post(
                    "/api/v1/resource-links/resolve",
                    headers=headers["designer"],
                    json={"locator": locator},
                )
                assert (
                    resolved.status_code == 200 and resolved.json()["data"]["ref_id"] == reference
                )
                forbidden = await client.post(
                    "/api/v1/resource-links/resolve",
                    headers=headers["requester"],
                    json={"locator": locator},
                )
                assert forbidden.status_code == 404 and forbidden.json()["data"] is None
                unsafe = await client.post(
                    "/api/v1/resource-links",
                    headers=headers["designer"],
                    json={"kind": "../unsafe", "ref_id": reference},
                )
                assert unsafe.status_code == 422
                today = get_datetime_utc().date()
                metric = await client.post(
                    "/api/v1/analytics/query",
                    headers=headers["requester"],
                    json={
                        "metric_key": "submitted_requests",
                        "start_date": str(today - timedelta(days=1)),
                        "end_date": str(today + timedelta(days=1)),
                        "dimension": "status",
                    },
                )
                assert metric.status_code == 200, metric.text
                data = metric.json()["data"]
                assert data["population_count"] == 4
                listing = await client.post(
                    "/api/v1/business-requests/search",
                    headers=headers["requester"],
                    json=data["drilldown"]["query"],
                )
                assert listing.status_code == 200
                assert listing.json()["result"]["total"] == data["population_count"]
                assert (
                    await client.post(
                        "/api/v1/analytics/query",
                        headers=headers["designer"],
                        json={
                            "metric_key": "submitted_requests",
                            "start_date": str(today),
                            "end_date": str(today + timedelta(days=1)),
                        },
                    )
                ).status_code == 403
        finally:
            await engine.dispose()
