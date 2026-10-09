"""Mapped templates and unified targets preserve the legacy case contract."""

import json
from pathlib import Path

import pytest

from apps.notifications.application.service import NotificationService
from apps.notifications.application.templates import NotificationTemplateRegistry
from apps.notifications.domain.dto import NotificationDTO
from apps.notifications.domain.inbox import InboxDTO
from main import app


def test_every_map_template_renders_en_fa_and_bounds_variables():
    manifest = json.loads(Path("docs/delivery/notification-map.json").read_text())
    registry = NotificationTemplateRegistry()
    for row in manifest["events"]:
        for locale in ("en", "fa"):
            rendered = registry.render(
                row["template_key"], "1", locale, {"resource_name": "<private>"}
            )
            assert "<private>" not in rendered.content
        with pytest.raises(ValueError):
            registry.render(row["template_key"], "1", "en", {"resource_name": "x" * 121})


def test_unified_inbox_does_not_fabricate_case_context():
    assert NotificationDTO.model_fields["request_ref_id"].is_required()
    assert NotificationDTO.model_fields["process_ref_id"].is_required()
    assert InboxDTO.model_fields["target"].is_required()
    for path, method in (
        ("/api/v1/inbox/search", "post"),
        ("/api/v1/inbox/unread", "get"),
        ("/api/v1/inbox/{ref_id}/read", "post"),
    ):
        assert app.openapi()["paths"][path][method]["security"]


@pytest.mark.anyio
async def test_legacy_serializer_redacts_revoked_case_content(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid7

    from apps.notifications.domain.entity import NotificationEntity
    from apps.notifications.domain.inbox import CaseTarget
    from apps.notifications.presentation.routes import notification_dto
    from apps.users.domain.entity import UserEntity

    row = NotificationEntity(
        id=uuid7(),
        recipient_user_id=uuid7(),
        business_request_id=uuid7(),
        process_instance_id=uuid7(),
        step_execution_id=uuid7(),
        template_key="workflow.notice",
        template_version="1",
        locale="en",
        subject="Private subject",
        content="Private content",
    )
    recipient = UserEntity(
        id=row.recipient_user_id, username="synthetic", hashed_password="synthetic"
    )
    session = SimpleNamespace(
        get=AsyncMock(
            side_effect=lambda model, identity: (
                recipient if model is UserEntity else SimpleNamespace(id=identity, version=1)
            )
        )
    )
    application = Mock(
        spec=NotificationService, session=session, deliveries=AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        "apps.notifications.application.inbox.InboxService.target",
        AsyncMock(return_value=CaseTarget(available=False)),
    )
    result = await notification_dto(row, application)
    assert result.content is None and result.subject != "Private subject"
    assert result.request_ref_id and result.process_ref_id
