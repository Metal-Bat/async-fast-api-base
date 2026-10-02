"""Authorized authoring pickers use exact published resource references."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.designer.application.service import DesignerService
from apps.designer.domain.dto import DesignerQuery
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.users.domain.entity import UserEntity
from core.ref_id import create_ref_id
from main import app
from utils.select import SelectQuery


@pytest.mark.anyio
async def test_form_version_selector_returns_published_exact_ref():
    definition = FormDefinitionEntity(
        id=uuid7(), code="purchase", name="Purchase form", owner_user_id=uuid7(), is_active=True
    )
    version = FormVersionEntity(
        id=uuid7(),
        form_definition_id=definition.id,
        number=3,
        status="PUBLISHED",
        data_dialect="https://json-schema.org/draft/2020-12/schema",
        render_dialect="bpms.render/1",
        data_schema={},
        render_schema={},
    )
    session = Mock()
    session.exec = AsyncMock(
        side_effect=[
            Mock(one=Mock(return_value=1)),
            Mock(all=Mock(return_value=[(version, definition)])),
        ]
    )
    actor = UserEntity(
        id=uuid7(), username="selector-admin", hashed_password="hash", is_superuser=True
    )
    page = await DesignerService(session).selector(
        "form_versions", DesignerQuery(search="purchase", page=1, size=10), actor
    )
    assert page.total == 1
    assert [(item.key, item.value) for item in page.items] == [
        (create_ref_id(version.id, version.version), "Purchase form · v3")
    ]
    sql = str(session.exec.call_args_list[1].args[0])
    assert "FORM_VERSION" in sql and "STATUS" in sql
    assert "PUBLISHED" in session.exec.call_args_list[1].args[0].compile().params.values()


@pytest.mark.anyio
async def test_connection_selector_excludes_unusable_rows_before_paging():
    row = IntegrationConnectionEntity(
        id=uuid7(),
        code="erp",
        name="ERP order",
        provider="http",
        kind="SERVICE",
        non_secret_config={},
        secret_ref="local",
        secret_version="v1",
        owner_user_id=uuid7(),
        status="ACTIVE",
        verification_status="VERIFIED",
    )
    session = Mock()
    session.exec = AsyncMock(
        side_effect=[Mock(one=Mock(return_value=1)), Mock(all=Mock(return_value=[row]))]
    )
    service = ConnectionService(session, Mock())
    actor = UserEntity(
        id=uuid7(), username="connection-admin", hashed_password="hash", is_superuser=True
    )
    page = await service.select_for_workflow("SERVICE", SelectQuery(search="ERP", size=5), actor)
    assert page.total == 1
    assert [(item.key, item.value) for item in page.items] == [
        (create_ref_id(row.id, row.version), "ERP order")
    ]
    statement = session.exec.call_args_list[1].args[0]
    sql = str(statement)
    assert "INTEGRATION_CONNECTION" in sql
    assert "VERIFICATION_STATUS" in sql and "DELETED_AT" in sql
    assert "lower" in sql.lower()  # case-insensitive search


def test_authoring_selectors_are_protected_and_typed():
    schema = app.openapi()
    designer = schema["paths"]["/api/v1/designer/selectors/{kind}"]["post"]
    connections = schema["paths"]["/api/v1/integration-connections/select"]["post"]
    assert designer["security"] and connections["security"]
    assert "form_versions" in str(designer["parameters"])
    assert "workflow_versions" in str(designer["parameters"])
    assert "items" in str(connections["parameters"])
