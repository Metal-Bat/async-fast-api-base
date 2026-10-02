"""Exercise the documented HTTP journey with real sessions and PostgreSQL."""

import os
from urllib.parse import quote
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from apps.requests.application.service import RequestService
from apps.requests.domain.dto import RequestTypeCreateDTO
from apps.step_types.application.registry import builtin_registry
from apps.users.domain.auth_entity import (
    PermissionEntity,
    RoleEntity,
    RolePermissionEntity,
    UserRoleEntity,
)
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphSnapshot,
    GraphStep,
    GraphTarget,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from main import app
from tests.integration.test_processes import _published_form, _step_refs
from utils.security import hash_password

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


async def _prepare_journey() -> tuple[list[str], str, str]:
    password = f"Journey-{uuid7()}"
    hashed = await hash_password(password)
    async with SessionFactory() as session:
        users = [
            UserEntity(username=f"journey-{role}-{uuid7()}", hashed_password=hashed)
            for role in ("requester", "reviewer", "outsider", "unprivileged")
        ]
        session.add_all(users)
        permission = (
            await session.exec(
                select(PermissionEntity).where(PermissionEntity.name == "requests.start")
            )
        ).one_or_none()
        if permission is None:
            permission = PermissionEntity(name="requests.start")
            session.add(permission)
        role = RoleEntity(name=f"journey-{uuid7()}")
        session.add(role)
        await session.flush()
        session.add(RolePermissionEntity(role_id=role.id, permission_id=permission.id))
        session.add_all([UserRoleEntity(user_id=user.id, role_id=role.id) for user in users[:3]])
        requester, reviewer = users[:2]
        form, form_version = await _published_form(session, requester)
        refs = await _step_refs(session)
        workflows = WorkflowService(session, builtin_registry())
        root = await workflows.create(
            WorkflowCreateDTO(code=f"HJ{uuid7().hex}", name="HTTP documentation approval"),
            requester.id,
        )
        version = await workflows.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        version = await workflows.replace_graph(
            create_ref_id(version.id, version.version),
            GraphSnapshot(
                steps=[
                    GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                    GraphStep(
                        key="review",
                        type_code="HUMAN_TASK",
                        type_version_ref=refs[("HUMAN_TASK", 1)],
                        form_ref=create_ref_id(form_version.id, form_version.version),
                        task_contract={
                            "inherit_previous": True,
                            "default_view": "review",
                            "views": [
                                {
                                    "key": "review",
                                    "purpose": "edit",
                                    "title": {"en": "Purchase review"},
                                    "scopes": ["/properties/amount"],
                                }
                            ],
                            "actions": [
                                {
                                    "key": "approve",
                                    "kind": "complete",
                                    "outcome_key": "approve",
                                    "title": {"en": "Approve"},
                                    "required_scopes": ["/properties/amount"],
                                }
                            ],
                        },
                        field_policy={
                            "read": ["/properties/amount"],
                            "write": ["/properties/amount"],
                            "required": ["/properties/amount"],
                            "hidden": [],
                        },
                    ),
                    GraphStep(
                        key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                ],
                targets=[
                    GraphTarget(
                        step="review", user_ref=create_ref_id(reviewer.id, reviewer.version)
                    )
                ],
                transitions=[
                    GraphTransition(
                        source="start", target="review", outcome="next", is_default=True
                    ),
                    GraphTransition(
                        source="review", target="finish", outcome="approve", is_default=True
                    ),
                ],
            ),
        )
        await workflows.publish(create_ref_id(version.id, version.version), requester.id)
        kind = await RequestService(session).create_type(
            RequestTypeCreateDTO(
                code=f"HQ{uuid7().hex}",
                name="HTTP purchase",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        await session.commit()
        return [user.username for user in users], password, create_ref_id(kind.id, kind.version)


async def _call(client, method, path, *, token=None, body=None, status=200, code=None):
    headers = {"Accept-Language": "en"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = await client.request(method, f"/api/v1{path}", json=body, headers=headers)
    assert response.status_code == status, response.text
    payload = response.json()
    if code is not None:
        assert payload["code"] == code, payload
        assert payload["success"] is False
    else:
        assert payload["success"] is True, payload
    return payload


def _member(resource, ref):
    return f"/{resource}/{quote(ref, safe='')}"


@pytest.mark.anyio
async def test_documented_http_login_submit_approve_track_and_session_lifecycle():
    try:
        names, password, kind = await _prepare_journey()
        # ASGI transport exercises routes/middleware, but deliberately does not start S3 lifespan.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _call(
                client,
                "POST",
                "/auth/login",
                body={"username": names[0], "password": "wrong"},
                status=401,
                code=2001,
            )
            pairs = []
            for name in names:
                pairs.append(
                    (
                        await _call(
                            client,
                            "POST",
                            "/auth/login",
                            body={"username": name, "password": password},
                        )
                    )["data"]
                )
            requester, reviewer, outsider, unprivileged = [pair["access_token"] for pair in pairs]
            await _call(client, "GET", "/auth/me", token=requester)
            await _call(
                client,
                "POST",
                "/business-requests",
                token=unprivileged,
                body={"request_type_ref_id": kind, "data": {}},
                status=403,
                code=2002,
            )
            draft = (
                await _call(
                    client,
                    "POST",
                    "/business-requests",
                    token=requester,
                    body={"request_type_ref_id": kind, "data": {}},
                    status=201,
                )
            )["data"]
            path = _member("business-requests", draft["ref_id"])
            assert draft["status"] == "DRAFT"
            await _call(client, "GET", path, token=outsider, status=404, code=1003)
            await _call(
                client,
                "POST",
                path + "/submit",
                token=requester,
                body={"submit_key": "invalid-submit"},
                status=422,
                code=1002,
            )
            saved = (
                await _call(
                    client,
                    "PUT",
                    path,
                    token=requester,
                    body={"data": {"amount": "125.00"}, "priority": 5},
                )
            )["data"]
            await _call(
                client,
                "PUT",
                path,
                token=requester,
                body={"data": {"amount": "9"}},
                status=409,
                code=1004,
            )
            submit_path = _member("business-requests", saved["ref_id"]) + "/submit"
            for _ in range(2):
                submitted = (
                    await _call(
                        client,
                        "POST",
                        submit_path,
                        token=requester,
                        body={"submit_key": "purchase-submit-001"},
                    )
                )["data"]
                assert submitted["status"] == "RUNNING"
            items = (
                await _call(
                    client,
                    "POST",
                    "/work-items/search",
                    token=reviewer,
                    body={"cartable": "available", "page": 1, "size": 20},
                )
            )["result"]["items"]
            assert len(items) == 1
            task_path = _member("work-items", items[0]["ref_id"])
            await _call(
                client,
                "POST",
                task_path + "/claim",
                token=outsider,
                body={"command_key": "forbidden-claim"},
                status=404,
                code=1003,
            )
            for _ in range(2):
                claimed = (
                    await _call(
                        client,
                        "POST",
                        task_path + "/claim",
                        token=reviewer,
                        body={"command_key": "purchase-claim-001"},
                    )
                )["data"]
                assert claimed["status"] == "CLAIMED"
            view = (
                await _call(
                    client,
                    "GET",
                    _member("work-items", claimed["ref_id"]) + "/view",
                    token=reviewer,
                )
            )["data"]
            assert view["data"] == {"amount": "125.00"}
            assert any(
                action["kind"] == "complete" and action["outcome_key"] == "approve"
                for action in view["actions"]
            )
            complete_path = _member("work-items", view["work_item_ref_id"]) + "/complete"
            action = {
                "command_key": "purchase-approve-001",
                "outcome_key": "approve",
                "data": {"amount": "125.00"},
                "comment": "Reviewed the purchase amount.",
                "feedback": [],
            }
            await _call(
                client,
                "POST",
                complete_path,
                token=reviewer,
                body={**action, "data": {}},
                status=422,
                code=1002,
            )
            for _ in range(2):
                completed = (
                    await _call(client, "POST", complete_path, token=reviewer, body=action)
                )["data"]
                assert completed["status"] == "COMPLETED"
            await _call(
                client,
                "POST",
                complete_path,
                token=reviewer,
                body={**action, "comment": "Changed payload"},
                status=409,
                code=1004,
            )
            tracked = (await _call(client, "GET", path, token=requester))["data"]
            assert tracked["status"] == "COMPLETED"
            assert tracked["data"] == {"amount": "125.00"}
            closed = (
                await _call(
                    client,
                    "GET",
                    _member("work-items", completed["ref_id"]) + "/view",
                    token=reviewer,
                )
            )["data"]
            assert closed["actions"] == []
            rotated = (
                await _call(
                    client,
                    "POST",
                    "/auth/refresh",
                    body={"refresh_token": pairs[0]["refresh_token"]},
                )
            )["data"]
            assert rotated["refresh_token"] != pairs[0]["refresh_token"]
            await _call(client, "GET", "/auth/me", token=rotated["access_token"])
            await _call(
                client,
                "POST",
                "/auth/refresh",
                body={"refresh_token": pairs[0]["refresh_token"]},
                status=401,
                code=2004,
            )
            await _call(
                client, "GET", "/auth/me", token=rotated["access_token"], status=401, code=2001
            )
            await _call(
                client, "POST", "/auth/logout", body={"refresh_token": pairs[1]["refresh_token"]}
            )
            await _call(client, "GET", "/auth/me", token=reviewer, status=401, code=2001)
    finally:
        await engine.dispose()
