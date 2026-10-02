"""Public work-group behavior and HTTP contract."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from fastapi import Request
from pydantic import ValidationError

from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from apps.work_groups.application.service import WorkGroupService
from apps.work_groups.domain.dto import WorkGroupQuery, WorkGroupSelectQuery
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.work_groups.presentation.routes import select_groups
from core.ref_id import create_ref_id
from main import app
from utils.exceptions import NotAllowedException, VersionConflictException


def test_work_group_routes_follow_resource_contract() -> None:
    paths = app.openapi()["paths"]
    base = "/api/v1/admin/work-groups"
    assert "post" in paths[base]
    assert "post" in paths[f"{base}/search"]
    assert "post" in paths[f"{base}/report"]
    assert "get" in paths[f"{base}/{{ref_id}}"]
    assert "put" in paths[f"{base}/{{ref_id}}"]
    assert "delete" in paths[f"{base}/{{ref_id}}"]
    assert "post" in paths[f"{base}/{{ref_id}}/history"]
    assert paths[f"{base}/search"]["post"]["security"] == [{"OAuth2PasswordBearer": []}]


@pytest.mark.anyio
async def test_group_management_permission_rejects_ordinary_user() -> None:
    user = UserEntity(id=uuid7(), username="ordinary", hashed_password="hash")
    session = Mock()
    result = Mock()
    result.all.return_value = []
    session.exec = AsyncMock(return_value=result)

    with pytest.raises(NotAllowedException):
        await RequirePermission("admin.work_groups.manage")(user, session)


@pytest.mark.anyio
async def test_group_selector_excludes_deleted_and_inactive_rows() -> None:
    session = Mock()
    items = Mock()
    items.all.return_value = []
    count = Mock()
    count.one.return_value = 0
    session.exec = AsyncMock(side_effect=[items, count])
    request = Request({"type": "http", "headers": []})
    actor = UserEntity(id=uuid7(), username="admin", hashed_password="hash", is_superuser=True)
    await select_groups(request, WorkGroupSelectQuery(), actor, session)
    query = str(session.exec.await_args_list[0].args[0])
    assert '"WORK_GROUP"."DELETED_AT" IS NULL' in query
    assert '"WORK_GROUP"."IS_ACTIVE" IS true' in query
    assert '"WORK_GROUP"."NAME"' in query
    assert "LIMIT" in query


@pytest.mark.anyio
async def test_group_selector_allows_explicit_administrator_lifecycle_override() -> None:
    session = Mock()
    items = Mock()
    items.all.return_value = []
    count = Mock()
    count.one.return_value = 0
    session.exec = AsyncMock(side_effect=[items, count])
    request = Request({"type": "http", "headers": []})
    actor = UserEntity(id=uuid7(), username="admin", hashed_password="hash", is_superuser=True)

    await select_groups(
        request,
        WorkGroupSelectQuery(include_inactive=True, include_deleted=True),
        actor,
        session,
    )

    query = str(session.exec.await_args_list[0].args[0])
    assert '"WORK_GROUP"."DELETED_AT" IS NULL' not in query
    assert '"WORK_GROUP"."IS_ACTIVE" IS true' not in query


def test_group_search_rejects_private_fields_and_unbounded_pages() -> None:
    with pytest.raises(ValidationError):
        WorkGroupQuery.model_validate(
            {"filters": [{"field_name": "id", "operation": "equal", "value": str(uuid7())}]}
        )
    with pytest.raises(ValidationError):
        WorkGroupQuery.model_validate({"size": 101})


@pytest.mark.anyio
async def test_add_member_is_idempotent_and_reactivates() -> None:
    group = WorkGroupEntity(id=uuid7(), code="OPS", name="Operations")
    user = UserEntity(id=uuid7(), username="member", hashed_password="hash")
    existing = WorkGroupMemberEntity(work_group_id=group.id, user_id=user.id, is_active=False)
    session = Mock()
    session.get = AsyncMock(side_effect=[group, user, existing, group, user, existing])
    session.flush = AsyncMock()
    service = WorkGroupService(session)

    first = await service.add_member(create_ref_id(group.id, group.version), user.id)
    second = await service.add_member(create_ref_id(group.id, group.version), user.id)

    assert first is existing and second is existing
    assert existing.is_active is True
    assert existing.left_at is None
    assert session.add.call_count == 1


@pytest.mark.anyio
async def test_group_update_rejects_stale_reference() -> None:
    group = WorkGroupEntity(id=uuid7(), code="OPS", name="Operations")
    session = Mock()
    session.get = AsyncMock(return_value=group)
    service = WorkGroupService(session)
    with pytest.raises(VersionConflictException):
        await service.update_group(create_ref_id(group.id, group.version + 1), name="New")
    session.add.assert_not_called()


@pytest.mark.anyio
async def test_group_delete_is_a_soft_delete_and_disables_routing() -> None:
    group = WorkGroupEntity(id=uuid7(), code="OPS", name="Operations")
    actor_id = uuid7()
    session = Mock()
    session.get = AsyncMock(return_value=group)
    session.flush = AsyncMock()

    await WorkGroupService(session).delete_group(
        create_ref_id(group.id, group.version), actor_id=actor_id
    )

    assert group.deleted_at is not None
    assert group.is_active is False
    session.flush.assert_awaited_once()


@pytest.mark.anyio
async def test_group_select_formats_keep_opaque_keys_and_display_names() -> None:
    group = WorkGroupEntity(id=uuid7(), code="OPS", name="Operations", version=1)
    request = Request({"type": "http", "headers": []})
    actor = UserEntity(username="admin", hashed_password="hash", is_superuser=True)
    results = []
    for response_format in ("page", "items"):
        rows = Mock()
        rows.all.return_value = [group]
        count = Mock()
        count.one.return_value = 1
        session = Mock(exec=AsyncMock(side_effect=[rows, count]))
        result = await select_groups(
            request, WorkGroupSelectQuery(), actor, session, response_format=response_format
        )
        options = result if isinstance(result, list) else result.result.items
        results.append([item.model_dump() for item in options])
    assert (
        results[0]
        == results[1]
        == [{"key": create_ref_id(group.id, group.version), "value": "Operations"}]
    )
