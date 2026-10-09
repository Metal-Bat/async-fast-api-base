"""Live database pages exclude deletion without hiding retained historical rows."""

import os
from uuid import uuid7

import pytest
from sqlmodel import col, select

from apps.forms.domain.dto import FormQuery
from apps.forms.domain.entity import FormDefinitionEntity
from apps.requests.domain.dto import RequestTypeQuery
from apps.requests.domain.entity import RequestTypeEntity
from apps.users.domain.auth_dto import RoleQuery
from apps.users.domain.auth_entity import RoleEntity
from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.dto import WorkGroupQuery
from apps.work_groups.domain.entity import WorkGroupEntity
from apps.workflows.domain.dto import WorkflowQuery
from apps.workflows.domain.entity import WorkflowDefinitionEntity
from core.deps import SessionFactory, engine
from utils.date_utils import get_datetime_utc
from utils.pagination import paginate_entities

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "model,query_model,field",
    [
        (UserEntity, UserQuery, "username"),
        (RoleEntity, RoleQuery, "name"),
        (WorkGroupEntity, WorkGroupQuery, "code"),
        (FormDefinitionEntity, FormQuery, "code"),
        (WorkflowDefinitionEntity, WorkflowQuery, "code"),
        (RequestTypeEntity, RequestTypeQuery, "code"),
    ],
)
async def test_normal_pages_and_counts_exclude_deleted_entities(model, query_model, field):
    token = "sample-" + uuid7().hex
    try:
        async with SessionFactory() as session:
            owner = UserEntity(username=f"owner-{uuid7().hex}", hashed_password="synthetic-hash")
            session.add(owner)
            await session.flush()
            form = FormDefinitionEntity(
                code=f"form-{uuid7().hex}", name="Form", owner_user_id=owner.id
            )
            workflow = WorkflowDefinitionEntity(
                code=f"workflow-{uuid7().hex}", name="Workflow", owner_user_id=owner.id
            )
            session.add_all([form, workflow])
            await session.flush()
            values = {field: f"live-{token}"}
            if model is UserEntity:
                values["hashed_password"] = owner.hashed_password
            elif model in {FormDefinitionEntity, WorkflowDefinitionEntity}:
                values.update(name="Live", owner_user_id=owner.id)
            elif model is WorkGroupEntity:
                values["name"] = "Live"
            elif model is RequestTypeEntity:
                values.update(
                    name="Live", workflow_definition_id=workflow.id, form_definition_id=form.id
                )
            live = model(**values)
            deleted = model(
                **(values | {field: f"deleted-{token}", "deleted_at": get_datetime_utc()})
            )
            session.add_all([live, deleted])
            await session.flush()
            query = query_model.model_validate(
                {
                    "filters": [{"field_name": field, "operation": "contains", "value": token}],
                    "size": 1,
                }
            )
            page = await paginate_entities(session, model, query)
            assert page.total == 1 and [row.id for row in page.items] == [live.id]
            query.page = 2
            page = await paginate_entities(session, model, query)
            assert page.total == 1 and page.items == []
            assert await session.get(model, deleted.id) is deleted
            retained = (
                await session.exec(select(model).where(col(model.id).in_([live.id, deleted.id])))
            ).all()
            assert len(retained) == 2
            if model in {UserEntity, WorkGroupEntity}:
                from starlette.requests import Request

                from apps.work_groups.domain.dto import UserSelectQuery, WorkGroupSelectQuery
                from apps.work_groups.presentation.routes import select_groups, select_users
                from core.ref_id import open_ref_id

                request = Request({"type": "http", "headers": []})
                selector_data = query.model_dump() | {"page": 1}
                if model is UserEntity:
                    options = await select_users(
                        request,
                        UserSelectQuery.model_validate(selector_data),
                        owner,
                        session,
                        "items",
                    )
                else:
                    options = await select_groups(
                        request,
                        WorkGroupSelectQuery.model_validate(selector_data),
                        owner,
                        session,
                        "items",
                    )
                assert isinstance(options, list) and [
                    open_ref_id(row.key)[0] for row in options
                ] == [live.id]
            deleted.deleted_at = None
            await session.flush()
            query.page = 1
            restored = await paginate_entities(session, model, query)
            assert restored.total == 2
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_real_cache_refreshes_after_authorized_delete_and_restore(monkeypatch):
    """Use an owned Redis container/namespace and the existing commit-owning routes."""
    import anyio
    from pydantic import RedisDsn
    from redis.exceptions import RedisError
    from starlette.requests import Request

    from apps.users.application.service import UserService
    from apps.users.data.cache_repository import UserCacheRepository
    from apps.users.data.repository import UserRepository
    from apps.users.presentation.admin import delete_user, restore_user
    from core.cache_session import register_cached_model
    from core.ref_id import create_ref_id
    from core.settings import settings

    token = uuid7().hex
    container = f"app-be-cache-{token}"
    namespace = f"wave-three-{token}"
    await anyio.run_process(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            container,
            "-p",
            "127.0.0.1::6379",
            "--entrypoint",
            "dragonfly",
            "sample_cache",
            "--proactor_threads=1",
            "--logtostderr",
        ]
    )
    try:
        port = await anyio.run_process(["docker", "port", container, "6379/tcp"])
        address = port.stdout.decode().strip()
        monkeypatch.setattr(settings, "CACHE_DSN", RedisDsn(f"redis://{address}/0"))
        cache = UserCacheRepository()
        cache.namespace = namespace
        register_cached_model(UserEntity, namespace)
        for attempt in range(30):
            try:
                async with cache._client() as redis:
                    assert await redis.ping()
                break
            except RedisError, OSError:
                if attempt == 29:
                    logs = await anyio.run_process(["docker", "logs", container], check=False)
                    raise RuntimeError((logs.stdout + logs.stderr).decode()) from None
                await anyio.sleep(0.1)
        async with SessionFactory() as session:
            actor = UserEntity(
                username=f"cache-admin-{token}", hashed_password=token, is_superuser=True
            )
            target = UserEntity(username=f"cache-target-{token}", hashed_password=token)
            session.add_all([actor, target])
            await session.commit()
            query = UserQuery.model_validate(
                {
                    "filters": [
                        {"field_name": "username", "operation": "equal", "value": target.username}
                    ]
                }
            )
            service = UserService(UserRepository(session, UserEntity), cache)
            initial = await service.list_public(query)
            assert initial.total == 1
            async with cache._client() as redis:
                keys = [key async for key in redis.scan_iter(match=f"read-cache:{namespace}:*")]
                assert len(keys) >= 2
            request = Request({"type": "http", "headers": []})
            before = create_ref_id(target.id, target.version)
            await delete_user(request, before, actor, session)
            assert (await service.list_public(query)).total == 0
            await session.refresh(target)
            deleted_ref = create_ref_id(target.id, target.version)
            result = await restore_user(request, deleted_ref, actor, session)
            assert result.data.ref_id != before
            assert (await service.list_public(query)).total == 1
    finally:
        register_cached_model(UserEntity, "users")
        await engine.dispose()
        await anyio.run_process(["docker", "stop", container])
