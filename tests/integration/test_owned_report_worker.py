"""Prove owned artifacts through the real worker and private object storage."""

import asyncio
import os
from urllib.parse import quote

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from apps.reporting.application.service import ReportService
from apps.reporting.domain.entity import ReportEntity, ReportStatus
from apps.tasks.application.outbox import dispatch_outbox
from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from core.celery_app import celery_app
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from main import app
from tests.integration.test_frontend_journey import _prepare_journey
from utils.s3 import ensure_bucket

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_REPORT_WORKER") != "1",
        reason="requires disposable reporting worker and storage",
    ),
]


@pytest.mark.anyio
async def test_actual_worker_owned_report_download_and_delete():
    await ensure_bucket()
    users, password, _ = await _prepare_journey()
    async with SessionFactory() as session:
        owner = (
            await session.exec(select(UserEntity).where(UserEntity.username == users[0]))
        ).one()
        # Fixture setup creates one narrowly filtered report; it grants no admin API entitlement.
        report = await ReportService(session).create(
            "users",
            owner,
            UserQuery.model_validate(
                {"filters": [{"field_name": "username", "operation": "equal", "value": users[0]}]}
            ),
            "en",
        )
        report_id = report.id
        await dispatch_outbox(celery_app)
    ready = None
    for _ in range(100):
        async with SessionFactory() as session:
            ready = await session.get(ReportEntity, report_id)
            assert ready is not None
            assert ready.status != ReportStatus.FAILED, "Worker generation failed"
            if ready.status == ReportStatus.READY:
                break
        await asyncio.sleep(0.5)
    assert ready is not None and ready.status == ReportStatus.READY
    ref = quote(create_ref_id(ready.id, ready.version), safe="")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        async def login(username):
            response = await client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            assert response.status_code == 200
            return {"Authorization": "Bearer " + response.json()["data"]["access_token"]}

        owner_headers = await login(users[0])
        other_headers = await login(users[2])
        detail = await client.get("/api/v1/reports/" + ref, headers=owner_headers)
        assert detail.status_code == 200
        assert detail.json()["data"]["status"] == "READY"
        assert detail.json()["data"]["zip_password"]
        for suffix in ("", "/download"):
            assert (
                await client.get("/api/v1/reports/" + ref + suffix, headers=other_headers)
            ).status_code == 404
        download = await client.get("/api/v1/reports/" + ref + "/download", headers=owner_headers)
        assert download.status_code == 200 and download.content.startswith(b"PK")
        assert download.headers["cache-control"] == "private, no-store"
        assert download.headers["x-content-type-options"] == "nosniff"
        deleted = await client.delete("/api/v1/reports/" + ref, headers=owner_headers)
        assert deleted.status_code == 200 and deleted.json()["code"] == 204
        assert (
            await client.get("/api/v1/reports/" + ref, headers=owner_headers)
        ).status_code == 404
    await engine.dispose()
