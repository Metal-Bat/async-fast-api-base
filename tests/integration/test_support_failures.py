"""Real rollback, durable episodes, authority, retention and bounded intake evidence."""

import os
from datetime import timedelta
from uuid import uuid7

import pytest
from sqlmodel import col, select

from apps.notifications.domain.entity import NotificationEntity
from apps.support.application.alerts import fanout_incident
from apps.support.application.recorder import record_failure
from apps.support.application.service import IncidentService, prune_incidents
from apps.support.domain.dto import IncidentQuery
from apps.support.domain.entity import SupportIncidentEntity, SupportIncidentHistory
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, RateLimitedException, VersionConflictException
from utils.pagination import PageRequest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_business_rollback_persists_only_safe_incident_and_episodes():
    token = uuid7().hex
    try:
        async with SessionFactory() as session, session.begin():
            manager = UserEntity(
                username="support-admin-" + token, hashed_password=token, is_superuser=True
            )
            outsider = UserEntity(username="support-other-" + token, hashed_password=token)
            session.add_all([manager, outsider])
            await session.flush()
            manager_id, outsider_id = manager.id, outsider.id
        with pytest.raises(RuntimeError):
            async with SessionFactory() as session, session.begin():
                session.add(UserEntity(username="rollback-" + token, hashed_password=token))
                await session.flush()
                raise RuntimeError("private form and provider material")
        correlation = uuid7()
        identity = await record_failure(
            category="technical", error_code=1099, operation="test.rollback", request_id=correlation
        )
        assert identity is not None
        assert (
            await record_failure(
                category="technical",
                error_code=1099,
                operation="test.rollback",
                request_id=correlation,
            )
            == identity
        )
        assert (
            await record_failure(
                category="technical", error_code=1099, operation="test.rollback", request_id=uuid7()
            )
            == identity
        )
        async with SessionFactory() as session, session.begin():
            assert (
                await session.exec(
                    select(UserEntity).where(UserEntity.username == "rollback-" + token)
                )
            ).first() is None
            row = await session.get(SupportIncidentEntity, identity)
            assert row is not None and row.occurrence_count == 2
            assert "private" not in str(row.model_dump())
            history_rows = (
                await session.exec(
                    select(SupportIncidentHistory.c.ID).where(
                        SupportIncidentHistory.c.ENTITY_ID == identity
                    )
                )
            ).all()
            assert len(history_rows) == 1
            manager = await session.get(UserEntity, manager_id)
            outsider = await session.get(UserEntity, outsider_id)
            assert manager is not None and outsider is not None
            service = IncidentService(session)
            with pytest.raises(NotAllowedException):
                await service.search(IncidentQuery(), outsider)
            reference = create_ref_id(row.id, row.version)
            acknowledged = await service.transition(reference, manager, "ACKNOWLEDGED")
            with pytest.raises(VersionConflictException):
                await service.transition(reference, manager, "RESOLVED")
            await service.transition(acknowledged.ref_id, manager, "RESOLVED")
            assert (await service.history(acknowledged.ref_id, manager, PageRequest())).total == 3
        recurrence = await record_failure(
            category="technical", error_code=1099, operation="test.rollback", request_id=uuid7()
        )
        assert recurrence is not None and recurrence != identity
        assert await fanout_incident(recurrence) >= 1
        await fanout_incident(recurrence)
        async with SessionFactory() as session, session.begin():
            notices = (
                await session.exec(
                    select(NotificationEntity).where(
                        NotificationEntity.event_id == recurrence,
                        NotificationEntity.recipient_user_id == manager_id,
                    )
                )
            ).all()
            assert len(notices) == 1 and notices[0].target_kind == "support"
            row = await session.get(SupportIncidentEntity, recurrence)
            assert row is not None and row.episode == 2
            row.expires_at = get_datetime_utc() - timedelta(seconds=1)
            await session.flush()
            assert await prune_incidents(session) >= 1
        async with SessionFactory() as session:
            assert await session.get(SupportIncidentEntity, recurrence) is None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_http_failure_rolls_back_then_returns_the_durable_correlation():
    import httpx
    from fastapi import FastAPI

    from core.deps import SessionDep
    from utils.exception_handlers import configure_exception_handlers
    from utils.exceptions import ValidationDetailsException

    app = FastAPI()
    configure_exception_handlers(app)
    token = uuid7().hex

    @app.post("/failure-probe")
    async def owned_failure_probe(session: SessionDep):
        session.add(
            UserEntity(
                username="http-rollback-" + token,
                hashed_password=uuid7().hex,
            )
        )
        await session.flush()
        raise RuntimeError("private form, prompt and provider text")

    @app.post("/business-probe")
    async def owned_business_probe():
        raise ValidationDetailsException([{"pointer": "/data", "code": "data.type"}])

    try:
        correlation = uuid7()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            failed = await client.post("/failure-probe", headers={"X-Request-ID": str(correlation)})
            expected = await client.post("/business-probe")
        assert failed.status_code == 500 and expected.status_code == 422
        assert failed.json()["request_id"] == str(correlation)
        metadata = failed.json()["data"]
        assert metadata["support_persisted"] is True and metadata["support_ref"]
        assert "private" not in failed.text
        async with SessionFactory() as session:
            assert not (
                await session.exec(
                    select(UserEntity).where(UserEntity.username == "http-rollback-" + token)
                )
            ).all()
            incidents = (
                await session.exec(
                    select(SupportIncidentEntity).where(
                        col(SupportIncidentEntity.operation).in_(
                            ["owned_failure_probe", "owned_business_probe"]
                        )
                    )
                )
            ).all()
            assert len(incidents) == 1 and incidents[0].operation == "owned_failure_probe"
            assert incidents[0].request_id == correlation
            assert str(incidents[0].id) == metadata["support_ref"]
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_client_intake_dedupe_and_rate_limit_are_durable(monkeypatch):
    frozen = get_datetime_utc().replace(second=30, microsecond=0)
    monkeypatch.setattr("apps.support.application.recorder.get_datetime_utc", lambda: frozen)
    try:
        async with SessionFactory() as session, session.begin():
            user = UserEntity(username="client-support-" + uuid7().hex, hashed_password=uuid7().hex)
            session.add(user)
            await session.flush()
            actor_id = user.id
        correlation = uuid7()

        async def intake(request_id):
            return await record_failure(
                category="client",
                error_code=1099,
                operation="calendar:client.render_failed",
                actor_id=actor_id,
                build="test.1",
                request_id=request_id,
            )

        first = await intake(correlation)
        assert first is not None
        assert await intake(correlation) == first
        for _ in range(9):
            assert await intake(uuid7()) == first
        with pytest.raises(RateLimitedException):
            await intake(uuid7())
        async with SessionFactory() as session:
            row = await session.get(SupportIncidentEntity, first)
            assert row is not None and row.occurrence_count == 10
    finally:
        await engine.dispose()
