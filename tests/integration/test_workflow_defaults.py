"""Exact template restoration over ordinary authenticated HTTP and real PostgreSQL."""

import asyncio
import os
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient

from core.deps import engine
from main import app
from tests.integration.test_studio_workspace import seed_studio

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses isolated PostgreSQL"),
]


@pytest.fixture(autouse=True)
async def release_database_pool():
    try:
        yield
    finally:
        await engine.dispose()


async def published_template(client, fixture, headers):
    base = "/api/v1/workflow-versions/" + fixture["version_ref"]
    graph = await client.put(base + "/graph", headers=headers, json=fixture["graph"])
    assert graph.status_code == 200, graph.text
    base = "/api/v1/workflow-versions/" + graph.json()["data"]["ref_id"]
    published = await client.post(base + "/publish", headers=headers)
    assert published.status_code == 200, published.text
    return published.json()["data"]["ref_id"]


async def login(client, fixture, outsider=False):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": fixture["outsider"] if outsider else fixture["username"],
            "password": fixture["password"],
        },
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["data"]["access_token"]}


@pytest.mark.anyio
async def test_successor_restore_replays_one_draft_and_preserves_published_source():
    fixture = await seed_studio()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await login(client, fixture)
        source = await published_template(client, fixture, headers)
        base = "/api/v1/workflow-versions/" + source
        before = (await client.get(base + "/graph", headers=headers)).json()["data"]
        plan = await client.post(
            base + "/default-preview",
            headers=headers,
            json={"source_ref_id": source, "mode": "successor"},
        )
        assert plan.status_code == 200, plan.text
        assert plan.headers["cache-control"] == "private, no-store"
        assert plan.json()["data"]["blockers"] == []
        command = {"command_key": str(uuid7()), "plan_token": plan.json()["data"]["plan_token"]}
        results = await asyncio.gather(
            *[client.post(base + "/default-apply", headers=headers, json=command) for _ in range(2)]
        )
        assert [response.status_code for response in results] == [200, 200], [
            response.text for response in results
        ]
        values = [response.json()["data"] for response in results]
        assert sorted(value["replayed"] for value in values) == [False, True]
        assert values[0]["workflow_version_ref_id"] == values[1]["workflow_version_ref_id"]
        successor = "/api/v1/workflow-versions/" + values[0]["workflow_version_ref_id"]
        assert (await client.get(successor, headers=headers)).json()["data"]["status"] == "DRAFT"
        assert (await client.get(base + "/graph", headers=headers)).json()["data"] == before
        other = await client.post(
            base + "/default-preview",
            headers=headers,
            json={
                "source_ref_id": source,
                "mode": "successor",
                "bindings": {"step_type:start": fixture["graph"]["steps"][0]["type_version_ref"]},
            },
        )
        assert other.status_code == 200
        changed = dict(command, plan_token=other.json()["data"]["plan_token"])
        assert (
            await client.post(base + "/default-apply", headers=headers, json=changed)
        ).status_code == 409
        assert (
            await client.post(
                base + "/default-preview",
                headers=await login(client, fixture, True),
                json={"source_ref_id": source, "mode": "successor"},
            )
        ).status_code == 403


@pytest.mark.anyio
async def test_stale_workspace_invalidates_restore_and_layout_reset_preserves_graph():
    fixture = await seed_studio()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await login(client, fixture)
        source = await published_template(client, fixture, headers)
        draft = await client.post(
            "/api/v1/workflow-versions",
            headers=headers,
            json={"workflow_ref_id": fixture["workflow_ref"], "number": 2},
        )
        assert draft.status_code == 201, draft.text
        base = "/api/v1/workflow-versions/" + draft.json()["data"]["ref_id"]
        preview = await client.post(
            base + "/default-preview",
            headers=headers,
            json={"source_ref_id": source, "mode": "replace_draft"},
        )
        assert preview.status_code == 200, preview.text
        document = {"graph": fixture["graph"], "positions": {"start": {"x": 20, "y": 40}}}
        saved = await client.put(base + "/workspace", headers=headers, json={"document": document})
        assert saved.status_code == 200, saved.text
        stale = await client.post(
            base + "/default-apply",
            headers=headers,
            json={"command_key": str(uuid7()), "plan_token": preview.json()["data"]["plan_token"]},
        )
        assert stale.status_code == 409, stale.text
        state = saved.json()["data"]
        reset = await client.post(
            base + "/layout-reset",
            headers=headers,
            json={"workspace_ref_id": state["workspace_ref_id"]},
        )
        assert reset.status_code == 200, reset.text
        assert reset.json()["data"]["document"]["graph"] == state["document"]["graph"]
        assert reset.json()["data"]["document"]["positions"] == {}
        assert reset.json()["data"]["workflow_version_ref_id"] == state["workflow_version_ref_id"]
        assert reset.json()["data"]["workspace_ref_id"] != state["workspace_ref_id"]


@pytest.mark.anyio
async def test_mixed_template_restoration_preserves_cases_and_rolls_back_partial_failure(
    tmp_path, monkeypatch
):
    from scripts.bootstrap_application import open_manifest
    from sqlmodel import select

    from apps.forms.domain.entity import FormVersionEntity
    from apps.processes.domain.entity import ProcessInstanceEntity
    from apps.requests.application.demo import install_demo
    from apps.requests.domain.entity import (
        BusinessRequestEntity,
        FormSubmissionEntity,
        RequestTypeEntity,
    )
    from apps.users.application.bootstrap import install_accounts
    from apps.users.application.permission_catalog import reconcile_permissions
    from apps.users.domain.entity import UserEntity
    from apps.workflows.application.defaults import WorkflowDefaultsService
    from apps.workflows.application.workspace import WorkspaceService
    from apps.workflows.domain.defaults import RestoreApplyInput, RestorePreviewInput
    from apps.workflows.domain.entities.restore import WorkflowRestoreEntity
    from apps.workflows.domain.entity import WorkflowVersionEntity
    from core.deps import SessionFactory
    from core.ref_id import create_ref_id

    async def frozen_state(session):
        return {
            entity.__name__: [
                row.model_dump(mode="json") for row in (await session.exec(select(entity))).all()
            ]
            for entity in (
                BusinessRequestEntity,
                FormSubmissionEntity,
                ProcessInstanceEntity,
                RequestTypeEntity,
                FormVersionEntity,
            )
        }

    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        async with SessionFactory() as session, session.begin():
            await reconcile_permissions(
                session, roles=tuple(account.persona for account in manifest.accounts)
            )
            await install_accounts(session, manifest)
            await install_demo(session, manifest)
        async with SessionFactory() as session, session.begin():
            owner = (
                await session.exec(
                    select(UserEntity).where(
                        UserEntity.username
                        == next(
                            account.username
                            for account in manifest.accounts
                            if account.persona == "designer"
                        )
                    )
                )
            ).one()
            sources = (
                await session.exec(
                    select(WorkflowVersionEntity).where(
                        WorkflowVersionEntity.published_by_user_id == owner.id,
                        WorkflowVersionEntity.status == "PUBLISHED",
                    )
                )
            ).all()
            source = sources[0]
            source_ref = create_ref_id(source.id, source.version)
            before = await frozen_state(session)
            plan = await WorkflowDefaultsService(session).preview(
                source_ref, RestorePreviewInput(source_ref_id=source_ref, mode="successor"), owner
            )
            assert any(key.startswith("form:") for key in plan.dependencies)
            assert plan.plan_token is not None
            actor_id = owner.id
        async with SessionFactory() as session, session.begin():
            owner = await session.get(UserEntity, actor_id)
            assert owner is not None
            await WorkflowDefaultsService(session).apply(
                source_ref,
                RestoreApplyInput(command_key=str(uuid7()), plan_token=plan.plan_token),
                owner,
            )
            assert await frozen_state(session) == before

        async with SessionFactory() as session, session.begin():
            owner = await session.get(UserEntity, actor_id)
            assert owner is not None
            plan = await WorkflowDefaultsService(session).preview(
                source_ref, RestorePreviewInput(source_ref_id=source_ref, mode="successor"), owner
            )
            assert plan.plan_token is not None
            version_ids = {
                row.id for row in (await session.exec(select(WorkflowVersionEntity))).all()
            }
            receipt_ids = {
                row.id for row in (await session.exec(select(WorkflowRestoreEntity))).all()
            }

        async def interrupted_save(*args, **kwargs):
            raise RuntimeError("owned-test-interruption")

        with monkeypatch.context() as patch:
            patch.setattr(WorkspaceService, "save", interrupted_save)
            with pytest.raises(RuntimeError, match="owned-test-interruption"):
                async with SessionFactory() as session, session.begin():
                    owner = await session.get(UserEntity, actor_id)
                    assert owner is not None
                    await WorkflowDefaultsService(session).apply(
                        source_ref,
                        RestoreApplyInput(command_key=str(uuid7()), plan_token=plan.plan_token),
                        owner,
                    )
        async with SessionFactory() as session:
            assert {
                row.id for row in (await session.exec(select(WorkflowVersionEntity))).all()
            } == version_ids
            assert {
                row.id for row in (await session.exec(select(WorkflowRestoreEntity))).all()
            } == receipt_ids
            assert await frozen_state(session) == before


@pytest.mark.anyio
async def test_restore_requires_explicit_source_and_rechecks_live_permissions():
    from sqlmodel import select

    from apps.users.domain.auth_entity import UserRoleEntity
    from apps.users.domain.entity import UserEntity
    from core.deps import SessionFactory

    fixture = await seed_studio()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await login(client, fixture)
        source = await published_template(client, fixture, headers)
        base = "/api/v1/workflow-versions/" + source
        missing_source = await client.post(
            base + "/default-preview", headers=headers, json={"mode": "successor"}
        )
        assert missing_source.status_code == 422
        invalid_dependency = await client.post(
            base + "/default-preview",
            headers=headers,
            json={
                "source_ref_id": source,
                "mode": "successor",
                "bindings": {"step_type:start": source},
            },
        )
        assert invalid_dependency.status_code == 200, invalid_dependency.text
        assert invalid_dependency.json()["data"]["plan_token"] is None
        assert invalid_dependency.json()["data"]["blockers"]
        preview = await client.post(
            base + "/default-preview",
            headers=headers,
            json={"source_ref_id": source, "mode": "successor"},
        )
        assert preview.status_code == 200
        async with SessionFactory() as session, session.begin():
            user = (
                await session.exec(
                    select(UserEntity).where(UserEntity.username == fixture["username"])
                )
            ).one()
            for assignment in (
                await session.exec(select(UserRoleEntity).where(UserRoleEntity.user_id == user.id))
            ).all():
                await session.delete(assignment)
        denied = await client.post(
            base + "/default-apply",
            headers=headers,
            json={"command_key": str(uuid7()), "plan_token": preview.json()["data"]["plan_token"]},
        )
        assert denied.status_code == 403, denied.text


@pytest.mark.anyio
async def test_retired_baseline_restores_successor_without_republishing_it():
    fixture = await seed_studio()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await login(client, fixture)
        source = await published_template(client, fixture, headers)
        base = "/api/v1/workflow-versions/" + source
        plan = await client.post(
            base + "/default-preview",
            headers=headers,
            json={"source_ref_id": source, "mode": "successor"},
        )
        applied = await client.post(
            base + "/default-apply",
            headers=headers,
            json={"command_key": str(uuid7()), "plan_token": plan.json()["data"]["plan_token"]},
        )
        assert applied.status_code == 200, applied.text
        restored = "/api/v1/workflow-versions/" + applied.json()["data"]["workflow_version_ref_id"]
        workspace_ref = applied.json()["data"]["workspace_ref_id"]
        retired = await client.post(base + "/retire", headers=headers)
        assert retired.status_code == 200, retired.text
        # The association identifies immutable content even after retirement increments metadata revision.
        associated = await client.post(
            restored + "/default-preview",
            headers=headers,
            json={"mode": "replace_draft", "workspace_ref_id": workspace_ref},
        )
        assert associated.status_code == 200, associated.text
        assert associated.json()["data"]["template_ref_id"] == retired.json()["data"]["ref_id"]
        assert associated.json()["data"]["plan_token"] is not None
        retired_base = "/api/v1/workflow-versions/" + retired.json()["data"]["ref_id"]
        plan = await client.post(
            retired_base + "/default-preview",
            headers=headers,
            json={"source_ref_id": retired.json()["data"]["ref_id"], "mode": "successor"},
        )
        applied = await client.post(
            retired_base + "/default-apply",
            headers=headers,
            json={"command_key": str(uuid7()), "plan_token": plan.json()["data"]["plan_token"]},
        )
        assert applied.status_code == 200, applied.text
        assert (await client.get(retired_base, headers=headers)).json()["data"][
            "status"
        ] == "RETIRED"


@pytest.mark.anyio
async def test_preview_blocks_template_that_cannot_fit_the_bounded_workspace():
    fixture = await seed_studio()
    start = fixture["graph"]["steps"][0]
    finish = fixture["graph"]["steps"][1]
    literal = "x" * 450
    fixture["graph"] = {
        "steps": [start, *[dict(finish, key=f"finish{i}") for i in range(230)]],
        "transitions": [
            {
                "source": "start",
                "target": f"finish{i}",
                "outcome": "next",
                "condition": None if i == 229 else f'"{literal}" == "{literal}"',
                "priority": 229 - i,
                "is_default": i == 229,
            }
            for i in range(230)
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await login(client, fixture)
        source = await published_template(client, fixture, headers)
        base = "/api/v1/workflow-versions/" + source
        preview = await client.post(
            base + "/default-preview",
            headers=headers,
            json={"source_ref_id": source, "mode": "successor"},
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["data"]["plan_token"] is None
        assert any(
            issue["code"] == "workspace.graph.invalid"
            for issue in preview.json()["data"]["blockers"]
        )
