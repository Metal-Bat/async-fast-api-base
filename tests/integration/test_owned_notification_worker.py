"""The actual existing Celery worker sends through a verified HTTPS email gateway."""

import asyncio
import json
import os
import ssl
from uuid import uuid7

import httpx
import pytest
from sqlmodel import select

from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.notifications.application.delivery import deliver_notification
from apps.notifications.application.events import stage_notice
from apps.notifications.domain.entity import NotificationDeliveryEntity
from apps.tasks.application.outbox import dispatch_outbox
from apps.users.domain.entity import UserEntity
from core.celery_app import celery_app
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from core.settings import settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_NOTIFICATION_WORKER") != "1",
        reason="requires owned worker and HTTPS email gateway",
    ),
]


@pytest.mark.anyio
async def test_owned_worker_notification_receipt_and_duplicate(monkeypatch):
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            actor = UserEntity(
                username="email-" + token,
                hashed_password=token,
                email="notice-" + token + "@example.com",
            )
            session.add(actor)
            await session.flush()
            connection = IntegrationConnectionEntity(
                code="email-" + token,
                name="Owned test email",
                provider="https_notification",
                kind="NOTIFICATION",
                owner_user_id=actor.id,
                secret_ref="owned-email",
                secret_version="1",
                verification_status="VERIFIED",
                non_secret_config={"endpoint_key": "owned_email"},
            )
            session.add(connection)
            await session.flush()
            monkeypatch.setattr(
                settings,
                "APPLICATION_NOTIFICATION_CONNECTION_REF",
                create_ref_id(connection.id, connection.version),
            )
            row = await stage_notice(
                session,
                map_id="MAP-14",
                event_id=uuid7(),
                recipient_id=actor.id,
                target_kind="account",
                target_id=actor.id,
            )
            assert row is not None
            delivery = (
                await session.exec(
                    select(NotificationDeliveryEntity).where(
                        NotificationDeliveryEntity.notification_id == row.id
                    )
                )
            ).one()
            identity = delivery.id
        await dispatch_outbox(celery_app)
        for _ in range(100):
            async with SessionFactory() as session:
                delivery = await session.get(NotificationDeliveryEntity, identity)
                assert delivery is not None and delivery.status not in {"FAILED", "CANCELLED"}
                if delivery.status == "DELIVERED":
                    break
            await asyncio.sleep(0.2)
        assert delivery.status == "DELIVERED" and delivery.attempt_count == 1
        assert await deliver_notification(identity) == "duplicate"
        async with httpx.AsyncClient(
            verify=ssl.create_default_context(cafile=str(settings.INTEGRATION_TLS_CA_FILE)),
            trust_env=False,
        ) as client:
            response = await client.get(
                os.environ["NOTIFICATION_TEST_RECEIPTS"],
                headers={"Authorization": "Bearer " + os.environ["NOTIFICATION_TEST_BEARER"]},
            )
            assert response.status_code == 200
            receipts = json.loads(response.content)
            assert str(identity) in receipts
            assert receipts[str(identity)]["channel"] == "email"
            assert receipts[str(identity)]["destination"] == actor.email
    finally:
        await engine.dispose()
