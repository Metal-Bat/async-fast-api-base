"""Read-only readiness against owned migrated PostgreSQL and real authorization."""

import os
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import col, select

from apps.designer.application.readiness import DependencyReadinessService
from apps.designer.domain.readiness import DependencyReadinessQuery
from apps.health.setup import SetupService
from apps.step_types.application.registry import get_registry
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import WorkflowCreateDTO, WorkflowVersionCreateDTO
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from main import app
from utils.exceptions import NotFoundException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_setup_and_dependency_facts_do_not_write_or_grant(monkeypatch):
    async def no_network():
        return None

    monkeypatch.setattr(
        "apps.health.setup.CHECKS", {key: no_network for key in ("cache", "broker", "s3")}
    )
    try:
        async with SessionFactory() as session, session.begin():
            before = list((await session.exec(select(col(UserEntity.id)))).all())
            initial = await SetupService(session).inspect()
            assert initial.status in {"blocked", "unknown"}
            assert next(c for c in initial.checks if c.key == "schema_head").status == "ready"
            assert (
                next(c for c in initial.checks if c.key == "worker_execution").status == "unknown"
            )
            assert before == list((await session.exec(select(col(UserEntity.id)))).all())
            await reconcile_permissions(
                session, roles=("requester", "reviewer", "designer", "administrator")
            )
            seeded = await SetupService(session).inspect()
            assert next(c for c in seeded.checks if c.key == "role_designer").status == "ready"
            assert seeded.status != "ready"
            token = uuid7().hex
            owner = UserEntity(
                username="readiness-" + token, hashed_password=token, is_superuser=True
            )
            other = UserEntity(
                username="readiness-other-" + token, hashed_password=token, is_superuser=True
            )
            session.add_all([owner, other])
            await session.flush()
            workflows = WorkflowService(session, get_registry())
            root = await workflows.create(
                WorkflowCreateDTO(code="R" + token, name="Private definition"), owner.id
            )
            version = await workflows.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(root.id, root.version), number=1
                )
            )
            query = DependencyReadinessQuery(
                workflow_version_ref_id=create_ref_id(version.id, version.version)
            )
            result = await DependencyReadinessService(session).inspect(query, owner)
            assert result.ready is False and result.issues
            assert result.requester_eligibility == "not_checked"
            other.is_superuser = False
            from apps.users.domain.auth_entity import RoleEntity, UserRoleEntity

            role = (
                await session.exec(select(RoleEntity).where(RoleEntity.name == "app.designer.v1"))
            ).one()
            session.add(UserRoleEntity(user_id=other.id, role_id=role.id))
            await session.flush()
            with pytest.raises(NotFoundException):
                await DependencyReadinessService(session).inspect(query, other)
            with pytest.raises(VersionConflictException):
                await DependencyReadinessService(session).inspect(
                    query.model_copy(
                        update={
                            "workflow_version_ref_id": create_ref_id(
                                version.id, version.version + 1
                            )
                        }
                    ),
                    owner,
                )
            assert version.status == "DRAFT"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/api/v1/setup/readiness")).status_code == 401
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_definition_exact_pins_missing_form_client_and_empty_candidates():
    from apps.clients.application.service import ClientService
    from apps.clients.domain.dto import ClientCreateDTO, ClientReleaseCreateDTO
    from apps.forms.domain.entity import FormDefinitionEntity
    from apps.requests.domain.entity import RequestTypeEntity
    from apps.work_groups.domain.entity import WorkGroupEntity
    from apps.workflows.domain.dto import GraphTarget
    from apps.workflows.domain.entity import WorkflowVersionEntity
    from core.ref_id import open_ref_id
    from tests.integration.test_frontend_journey import _prepare_journey

    try:
        names, password, kind = await _prepare_journey()
        async with SessionFactory() as session, session.begin():
            owner = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[0]))
            ).one()
            owner.is_superuser = True
            await session.flush()
            request_type = await session.get(RequestTypeEntity, open_ref_id(kind)[0])
            assert request_type is not None
            version = (
                await session.exec(
                    select(WorkflowVersionEntity).where(
                        WorkflowVersionEntity.workflow_definition_id
                        == request_type.workflow_definition_id
                    )
                )
            ).one()
            query = DependencyReadinessQuery(
                workflow_version_ref_id=create_ref_id(version.id, version.version)
            )
            readiness = DependencyReadinessService(session)
            original = await readiness.inspect(query, owner)
            assert original.ready and original.pins and bool(original.graph_checksum)
            assert any(pin.checksum for pin in original.pins)
            clients = ClientService(session)
            token = uuid7().hex
            client, _ = await clients.create_client(
                ClientCreateDTO(
                    code="ready" + token, name="Readiness client", kind="WEB", platform="browser"
                )
            )
            release = await clients.create_release(
                client.id, ClientReleaseCreateDTO(version="1.0.0", api_version="v1")
            )
            query = query.model_copy(
                update={"client_release_ref_id": create_ref_id(release.id, release.version)}
            )
            assert (await readiness.inspect(query, owner)).client_readiness == "ready"
            release.is_enabled = False
            await session.flush()
            query = query.model_copy(
                update={"client_release_ref_id": create_ref_id(release.id, release.version)}
            )
            unavailable = await readiness.inspect(query, owner)
            assert not unavailable.ready and unavailable.client_readiness == "blocked"
            assert any(issue.code == "client.unavailable" for issue in unavailable.issues)
            query = query.model_copy(update={"client_release_ref_id": None})
            form = await session.get(FormDefinitionEntity, request_type.form_definition_id)
            assert form is not None
            form.is_active = False
            await session.flush()
            missing = await readiness.inspect(query, owner)
            assert not missing.ready
            assert any(
                issue.code == "human.form.not_published" and issue.node_key == "review"
                for issue in missing.issues
            )
            form.is_active = True
            await session.flush()
            group = WorkGroupEntity(code="empty" + token, name="Empty candidates")
            session.add(group)
            await session.flush()
            workflows = WorkflowService(session, get_registry())
            graph = await workflows.snapshot(version.id)
            graph.targets = [
                GraphTarget(step="review", work_group_ref=create_ref_id(group.id, group.version))
            ]
            root = await workflows.get(create_ref_id(request_type.workflow_definition_id, 0))
            draft = await workflows.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(root.id, root.version), number=2
                )
            )
            draft = await workflows.replace_graph(
                create_ref_id(draft.id, draft.version), graph, owner.id
            )
            empty = await readiness.inspect(
                DependencyReadinessQuery(
                    workflow_version_ref_id=create_ref_id(draft.id, draft.version)
                ),
                owner,
            )
            assert any(issue.code == "human.candidates.empty" for issue in empty.issues)
            assert draft.status == "DRAFT" and version.status == "PUBLISHED"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            tokens = []
            for name in names[:2]:
                login = await client.post(
                    "/api/v1/auth/login", json={"username": name, "password": password}
                )
                tokens.append({"Authorization": "Bearer " + login.json()["data"]["access_token"]})
            assert (
                await client.get("/api/v1/setup/readiness", headers=tokens[1])
            ).status_code == 403
            result = await client.get("/api/v1/setup/readiness", headers=tokens[0])
            assert (
                result.status_code == 200 and result.headers["cache-control"] == "private, no-store"
            )
            assert result.json()["data"]["status"] != "ready"
    finally:
        await engine.dispose()
