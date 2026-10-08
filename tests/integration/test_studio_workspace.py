"""Actual HTTP workspace persistence, conflict and publication gates."""

import os
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from apps.step_types.application.registry import builtin_registry
from apps.step_types.application.service import StepTypeService
from apps.users.domain.auth_entity import (
    PermissionEntity,
    RoleEntity,
    RolePermissionEntity,
    UserRoleEntity,
)
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import WorkflowCreateDTO, WorkflowVersionCreateDTO
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from main import app
from tests.integration.test_processes import _step_refs
from utils.security import hash_password

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses isolated PostgreSQL"),
]


async def seed_studio():
    password = "Studio-" + str(uuid7())
    hashed = await hash_password(password)
    async with SessionFactory() as session:
        author = UserEntity(username="studio-" + str(uuid7()), hashed_password=hashed)
        outsider = UserEntity(username="studio-outsider-" + str(uuid7()), hashed_password=hashed)
        session.add_all([author, outsider])
        await session.flush()
        role = RoleEntity(name="studio-author-" + str(uuid7()))
        session.add(role)
        await session.flush()
        session.add(UserRoleEntity(user_id=author.id, role_id=role.id))
        for name in ["forms.manage", "workflows.manage", "requests.manage"]:
            permission = (
                await session.exec(select(PermissionEntity).where(PermissionEntity.name == name))
            ).one_or_none()
            if permission is None:
                permission = PermissionEntity(name=name)
                session.add(permission)
                await session.flush()
            session.add(RolePermissionEntity(role_id=role.id, permission_id=permission.id))
        registry = builtin_registry()
        await StepTypeService(session, registry).reconcile()
        service = WorkflowService(session, registry)
        root = await service.create(
            WorkflowCreateDTO(code="ST" + uuid7().hex, name="Studio WIP"), author.id
        )
        version = await service.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        refs = await _step_refs(session)
        graph = {
            "steps": [
                {"key": "start", "type_code": "START", "type_version_ref": refs[("START", 1)]},
                {"key": "finish", "type_code": "FINISH", "type_version_ref": refs[("FINISH", 1)]},
            ],
            "transitions": [
                {"source": "start", "target": "finish", "outcome": "next", "is_default": True}
            ],
            "bindings": [],
            "targets": [],
        }
        await session.commit()
        return {
            "username": author.username,
            "outsider": outsider.username,
            "password": password,
            "workflow_ref": create_ref_id(root.id, root.version),
            "version_ref": create_ref_id(version.id, version.version),
            "graph": graph,
        }


@pytest.mark.anyio
async def test_workspace_reopen_conflict_promotion_and_immutable_publication():
    fixture = await seed_studio()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        async def login(username):
            response = await client.post(
                "/api/v1/auth/login", json={"username": username, "password": fixture["password"]}
            )
            assert response.status_code == 200
            return {"Authorization": "Bearer " + response.json()["data"]["access_token"]}

        headers = await login(fixture["username"])
        denied = await login(fixture["outsider"])
        base = "/api/v1/workflow-versions/" + fixture["version_ref"]
        assert (await client.get(base + "/workspace", headers=denied)).status_code == 403
        original = (await client.get(base, headers=headers)).json()["data"]
        doc = {
            "graph": {"steps": [{"key": "half"}]},
            "positions": {"half": {"x": 40, "y": 80}},
            "viewport": {"x": 10, "y": 20, "zoom": 1.2},
        }
        saved = await client.put(
            base + "/workspace", headers=headers, json={"workspace_ref_id": None, "document": doc}
        )
        assert saved.status_code == 200
        assert saved.headers["cache-control"] == "private, no-store"
        state = saved.json()["data"]
        assert state["workspace_ref_id"]
        assert (await client.get(base + "/workspace", headers=headers)).json()["data"]["document"][
            "positions"
        ]["half"] == {"x": 40.0, "y": 80.0}
        assert (await client.get(base, headers=headers)).json()["data"]["ref_id"] == original[
            "ref_id"
        ]
        assert (
            await client.put(
                base + "/workspace",
                headers=headers,
                json={"workspace_ref_id": None, "document": doc},
            )
        ).status_code == 409
        assert (
            await client.post(
                base + "/workspace/promote",
                headers=headers,
                json={"workspace_ref_id": state["workspace_ref_id"]},
            )
        ).status_code == 422
        assert (await client.post(base + "/publish", headers=headers)).status_code in {409, 422}
        doc["graph"] = fixture["graph"]
        saved = await client.put(
            base + "/workspace",
            headers=headers,
            json={"workspace_ref_id": state["workspace_ref_id"], "document": doc},
        )
        assert saved.status_code == 200
        state = saved.json()["data"]
        promoted = await client.post(
            base + "/workspace/promote",
            headers=headers,
            json={"workspace_ref_id": state["workspace_ref_id"]},
        )
        assert promoted.status_code == 200
        base = "/api/v1/workflow-versions/" + promoted.json()["data"]["ref_id"]
        reopened = (await client.get(base + "/workspace", headers=headers)).json()["data"]
        assert reopened["document"]["positions"]["half"] == {"x": 40.0, "y": 80.0}
        # Layout-only edits retain promotion and do not modify executable version identity.
        doc["positions"]["half"]["x"] = 100
        layout = await client.put(
            base + "/workspace",
            headers=headers,
            json={"workspace_ref_id": reopened["workspace_ref_id"], "document": doc},
        )
        assert layout.status_code == 200
        # An edit through the existing executable-graph API invalidates promotion.
        changed_graph = __import__("copy").deepcopy(fixture["graph"])
        changed_graph["steps"][1]["display_order"] = 1
        changed = await client.put(base + "/graph", headers=headers, json=changed_graph)
        assert changed.status_code == 200
        base = "/api/v1/workflow-versions/" + changed.json()["data"]["ref_id"]
        assert (await client.post(base + "/publish", headers=headers)).status_code == 409
        promoted_again = await client.post(
            base + "/workspace/promote",
            headers=headers,
            json={"workspace_ref_id": layout.json()["data"]["workspace_ref_id"]},
        )
        assert promoted_again.status_code == 200
        base = "/api/v1/workflow-versions/" + promoted_again.json()["data"]["ref_id"]
        history = await client.post(
            base + "/workspace/history", headers=headers, json={"page": 1, "size": 20}
        )
        assert history.status_code == 200
        assert history.json()["result"]["items"]
        publication = await client.post(base + "/publish", headers=headers)
        assert publication.status_code == 200
        published = publication.json()["data"]
        assert published["status"] == "PUBLISHED"
        base = "/api/v1/workflow-versions/" + published["ref_id"]
        assert (
            await client.put(
                base + "/workspace",
                headers=headers,
                json={
                    "workspace_ref_id": layout.json()["data"]["workspace_ref_id"],
                    "document": doc,
                },
            )
        ).status_code == 409
        assert (
            await client.put(base + "/graph", headers=headers, json=fixture["graph"])
        ).status_code == 409
    await engine.dispose()


@pytest.mark.anyio
async def test_author_preview_filters_simulated_policy_and_uses_runtime_metadata():
    fixture = await seed_studio()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": fixture["username"], "password": fixture["password"]},
        )
        headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
        body = {
            "documents": {
                "data_schema": {
                    "type": "object",
                    "properties": {"amount": {"type": "string"}, "secret": {"type": "string"}},
                },
                "render_schema": {
                    "root": {
                        "component": "vertical",
                        "children": [
                            {"component": "text", "scope": "/properties/amount"},
                            {"component": "text", "scope": "/properties/secret"},
                        ],
                    }
                },
            },
            "data": {"amount": "125.750", "secret": "hidden"},
            "policy": {
                "read": ["/properties/amount"],
                "write": ["/properties/amount"],
                "hidden": ["/properties/secret"],
            },
        }
        response = await client.post("/api/v1/forms/runtime-preview", headers=headers, json=body)
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["resource_ref_id"] == "simulated-preview"
        assert result["data"] == {"amount": "125.750"}
        assert len(result["field_metadata"]) == 1
        assert result["render_schema"]["dialect"] == "bpms.render/1"
        body["policy"] = {}
        empty = await client.post("/api/v1/forms/runtime-preview", headers=headers, json=body)
        assert empty.status_code == 200
        assert empty.json()["data"]["data"] == {}
        body["policy"] = {"read": ["/properties/amount"]}
        body["purpose"] = "print"
        result = (
            await client.post("/api/v1/forms/runtime-preview", headers=headers, json=body)
        ).json()["data"]
        assert result["writable_scopes"] == []
        options = await client.post(
            "/api/v1/forms/options",
            headers=headers,
            json={
                "documents": {
                    "data_schema": {"type": "object", "properties": {"choice": {"type": "string"}}},
                    "render_schema": {
                        "root": {
                            "component": "choice",
                            "scope": "/properties/choice",
                            "source": {"kind": "custom", "items": [{"key": "one", "value": "One"}]},
                        }
                    },
                },
                "query": {"node_pointer": "/root", "generation": 3},
                "locale": "fa",
            },
        )
        assert options.status_code == 200
        assert options.json()["result"]["locale"] == "fa"
        assert options.json()["result"]["items"][0]["key"] == 'json:"one"'

    await engine.dispose()
