"""Real persistence and publication retain declared source and legacy port schemas."""

import os
from uuid import uuid7

import pytest
from sqlmodel import col, select

from apps.step_types.application.registry import builtin_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import GraphSnapshot, WorkflowCreateDTO, WorkflowVersionCreateDTO
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses isolated PostgreSQL"),
]


@pytest.fixture(autouse=True)
async def release_database_pool(anyio_backend):
    yield
    await engine.dispose()


async def prepare_graph(session, *, legacy=False, source_kind="REQUEST"):
    registry = builtin_registry()
    await StepTypeService(session, registry).reconcile()
    owner = UserEntity(username="binding-owner-" + uuid7().hex, hashed_password="hash")
    session.add(owner)
    await session.flush()
    service = WorkflowService(session, registry)
    root = await service.create(
        WorkflowCreateDTO(code="B" + uuid7().hex, name="Binding contract"), owner.id
    )
    version = await service.create_version(
        WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
    )
    rows = (
        await session.exec(
            select(StepTypeEntity, StepTypeVersionEntity)
            .join(
                StepTypeVersionEntity,
                col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
            )
            .where(StepTypeVersionEntity.status == "PUBLISHED")
        )
    ).all()
    refs = {(item.code, pin.number): create_ref_id(pin.id, pin.version) for item, pin in rows}
    config = {"conversion_key": "integer"}
    schema = {
        "type": "object",
        "properties": {"amount": {"type": "integer"}},
        "required": ["amount"],
    }
    contract = registry.transform_contract("transform", "2", config)
    assert contract is not None
    target_schema = (
        next(
            port.value_schema
            for port in registry.resolve("transform", "1").metadata().ports
            if port.direction == "INPUT"
        )
        if legacy
        else contract[0]
    )
    binding = (
        {
            "step": "cast",
            "target_port": "value",
            "target_schema": target_schema,
            "source_kind": "CONSTANT",
            "constant_value": "0",
        }
        if legacy
        else {
            "step": "cast",
            "target_port": "value",
            "target_schema": target_schema,
            "source_kind": source_kind,
            "source_path": "/amount",
            "source_schema": schema,
        }
    )
    graph = GraphSnapshot.model_validate(
        {
            "steps": [
                {"key": "start", "type_code": "START", "type_version_ref": refs[("START", 1)]},
                {
                    "key": "cast",
                    "type_code": "TRANSFORM",
                    "type_version_ref": refs[("TRANSFORM", 1 if legacy else 2)],
                    "config": config,
                },
                {"key": "finish", "type_code": "FINISH", "type_version_ref": refs[("FINISH", 1)]},
            ],
            "bindings": [binding],
            "transitions": [
                {"source": "start", "target": "cast", "outcome": "next", "is_default": True},
                {"source": "cast", "target": "finish", "outcome": "next", "is_default": True},
            ],
        }
    )
    if not legacy and source_kind == "REQUEST":
        graph.transitions[1].condition = "request.amount >= 0"
        graph.transitions[1].is_default = False
    return service, owner, version, graph


@pytest.mark.anyio
@pytest.mark.parametrize("source_kind", ["REQUEST", "CONTEXT"])
async def test_declared_binding_schema_survives_save_new_session_and_publication(source_kind):
    async with SessionFactory() as session:
        service, owner, version, graph = await prepare_graph(session, source_kind=source_kind)
        version = await service.replace_graph(create_ref_id(version.id, version.version), graph)
        version_id, version_ref, owner_id = (
            version.id,
            create_ref_id(version.id, version.version),
            owner.id,
        )
        await session.commit()
    async with SessionFactory() as session:
        service = WorkflowService(session, builtin_registry())
        restored = await service.snapshot(version_id)
        assert restored.bindings[0].source_schema == graph.bindings[0].source_schema
        assert (await service.validate_graph(restored)).valid
        published = await service.publish(version_ref, owner_id)
        checksum = published.graph_checksum
        await session.commit()
    async with SessionFactory() as session:
        service = WorkflowService(session, builtin_registry())
        restored = await service.snapshot(version_id)
        assert restored.bindings[0].source_schema == graph.bindings[0].source_schema
        assert (await service.validate_graph(restored)).checksum == checksum
    await engine.dispose()


@pytest.mark.anyio
async def test_legacy_transform_publishes_with_its_unchanged_registered_port_schema():
    async with SessionFactory() as session:
        service, owner, version, graph = await prepare_graph(session, legacy=True)
        declared = graph.bindings[0].target_schema.copy()
        version = await service.replace_graph(create_ref_id(version.id, version.version), graph)
        restored = await service.snapshot(version.id)
        assert restored.bindings[0].target_schema == declared
        published = await service.publish(create_ref_id(version.id, version.version), owner.id)
        assert published.graph_checksum
        assert (await service.snapshot(version.id)).bindings[0].target_schema == declared
        await session.rollback()
    await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("legacy", [False, True])
async def test_http_workspace_promotion_publication_and_runtime_keep_exact_bindings(legacy):
    from httpx import ASGITransport, AsyncClient

    from apps.forms.application.service import FormService
    from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
    from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
    from apps.requests.application.service import RequestService
    from apps.requests.domain.dto import (
        BusinessRequestCreateDTO,
        BusinessRequestSubmitDTO,
        RequestTypeCreateDTO,
    )
    from main import app
    from tests.integration.test_studio_workspace import seed_studio

    fixture = await seed_studio()
    async with SessionFactory() as session:
        _, _, _, graph = await prepare_graph(session, legacy=legacy)
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        async def login(username):
            result = await client.post(
                "/api/v1/auth/login", json={"username": username, "password": fixture["password"]}
            )
            assert result.status_code == 200
            return {"Authorization": "Bearer " + result.json()["data"]["access_token"]}

        headers = await login(fixture["username"])
        denied = await login(fixture["outsider"])
        base = "/api/v1/workflow-versions/" + fixture["version_ref"]
        payload = {"workspace_ref_id": None, "document": {"graph": graph.model_dump(mode="json")}}
        assert (
            await client.put(base + "/workspace", headers=denied, json=payload)
        ).status_code == 403
        saved = await client.put(base + "/workspace", headers=headers, json=payload)
        assert saved.status_code == 200
        assert (
            await client.put(base + "/workspace", headers=headers, json=payload)
        ).status_code == 409
        promoted = await client.post(
            base + "/workspace/promote",
            headers=headers,
            json={"workspace_ref_id": saved.json()["data"]["workspace_ref_id"]},
        )
        assert promoted.status_code == 200
        current_ref = promoted.json()["data"]["ref_id"]
        base = "/api/v1/workflow-versions/" + current_ref
        published = await client.post(base + "/publish", headers=headers)
        assert published.status_code == 200
        published_ref = published.json()["data"]["ref_id"]
        base = "/api/v1/workflow-versions/" + published_ref
        assert (
            await client.put(base + "/graph", headers=headers, json=graph.model_dump(mode="json"))
        ).status_code == 409
        loaded = await client.get(
            "/api/v1/workflow-versions/" + published_ref + "/graph", headers=headers
        )
        assert loaded.status_code == 200
        restored = GraphSnapshot.model_validate(loaded.json()["data"])
        assert restored.bindings[0].source_schema == graph.bindings[0].source_schema
        assert restored.bindings[0].target_schema == graph.bindings[0].target_schema
    async with SessionFactory() as session:
        author = (
            await session.exec(select(UserEntity).where(UserEntity.username == fixture["username"]))
        ).one()
        forms = FormService(session)
        form = await forms.create(
            FormCreateDTO(code="F" + uuid7().hex, name="Binding runtime"), author.id
        )
        version = await forms.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(form.id, form.version),
                number=1,
                data_schema={
                    "type": "object",
                    "properties": {"amount": {"type": "integer"}},
                    "required": ["amount"],
                },
                render_schema={
                    "root": {
                        "component": "vertical",
                        "children": [
                            {
                                "component": "number",
                                "scope": "/properties/amount",
                                "label": "Amount",
                            }
                        ],
                    }
                },
            )
        )
        await forms.publish(create_ref_id(version.id, version.version), author.id)
        requests = RequestService(session)
        kind = await requests.create_type(
            RequestTypeCreateDTO(
                code="R" + uuid7().hex,
                name="Binding execution",
                workflow_ref_id=fixture["workflow_ref"],
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(kind.id, kind.version), data={"amount": 0}
            ),
            author,
        )
        submitted, _ = await requests.submit(
            create_ref_id(draft.id, draft.version),
            BusinessRequestSubmitDTO(submit_key=uuid7().hex),
            author,
        )
        process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id
                )
            )
        ).one()
        assert process.status == "COMPLETED", process.last_error_code
        rows = (
            await session.exec(
                select(StepExecutionEntity).where(
                    StepExecutionEntity.process_instance_id == process.id
                )
            )
        ).all()
        result = next(
            (row.output_snapshot or {})["result"]
            for row in rows
            if row.output_snapshot is not None and "result" in row.output_snapshot
        )
        assert result == 0 and type(result) is int
        await session.rollback()


async def object_graph(session):
    from apps.workflows.domain.dto import GraphBinding, GraphStep, GraphTransition

    service, owner, version, graph = await prepare_graph(session)
    source = graph.bindings[0]
    graph.steps.insert(
        2,
        GraphStep(
            key="assemble",
            type_code="TRANSFORM",
            type_version_ref=graph.steps[1].type_version_ref,
            config={
                "conversion_key": "object",
                "projection": {
                    field: "/" + field
                    for field in ("count", "original", "priority", "flag", "items", "note")
                },
            },
        ),
    )
    graph.transitions[1].target = "assemble"
    graph.transitions[1].condition = None
    graph.transitions[1].is_default = True
    graph.transitions.append(
        GraphTransition(source="assemble", target="finish", outcome="next", is_default=True)
    )
    schema = {
        "type": "object",
        "properties": {
            "count": {"type": "integer"},
            "original": {"type": "integer"},
            "priority": {"type": "integer"},
            "flag": {"type": "boolean"},
            "items": {"type": "array", "items": {"type": "integer"}},
            "note": {"type": ["string", "null"]},
        },
        "required": ["count", "original", "priority", "flag", "items", "note"],
        "additionalProperties": False,
    }
    values = [
        (
            "count",
            {
                "source_kind": "STEP_OUTPUT",
                "source_step": "cast",
                "source_port": "result",
                "source_schema": {"type": "integer"},
            },
        ),
        (
            "original",
            {
                "source_kind": "REQUEST",
                "source_path": "/amount",
                "source_schema": source.source_schema,
            },
        ),
        (
            "priority",
            {
                "source_kind": "CONTEXT",
                "source_path": "/request/priority",
                "source_schema": {
                    "type": "object",
                    "properties": {
                        "request": {
                            "type": "object",
                            "properties": {"priority": {"type": "integer"}},
                        }
                    },
                },
            },
        ),
        ("flag", {"source_kind": "CONSTANT", "constant_value": False}),
        ("items", {"source_kind": "CONSTANT", "constant_value": [1, 2]}),
        ("note", {"source_kind": "CONSTANT", "constant_value": None}),
    ]
    graph.bindings.extend(
        GraphBinding.model_validate(
            {
                "step": "assemble",
                "target_port": "value",
                "target_schema": schema,
                "ordinal": ordinal,
                "target_projection": {"dialect": "bpms.binding.object/1", "path": "/" + field},
                **value,
            }
        )
        for ordinal, (field, value) in enumerate(values)
    )
    return service, owner, version, graph


@pytest.mark.anyio
async def test_object_projection_persists_publishes_executes_all_existing_source_kinds_and_replays_once():
    from apps.forms.application.service import FormService
    from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
    from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
    from apps.requests.application.service import RequestService
    from apps.requests.domain.dto import (
        BusinessRequestCreateDTO,
        BusinessRequestSubmitDTO,
        RequestTypeCreateDTO,
    )

    async with SessionFactory() as session:
        service, owner, version, graph = await object_graph(session)
        from utils.exceptions import ValidationDetailsException

        try:
            await service.replace_graph(create_ref_id(version.id, version.version), graph, owner.id)
        except ValidationDetailsException as error:
            pytest.fail(str(error.issues))
        identity, owner_id, root_id = version.id, owner.id, version.workflow_definition_id
        await session.commit()
    async with SessionFactory() as session:
        service = WorkflowService(session, builtin_registry())
        restored = await service.snapshot(identity)
        assert [row.model_dump() for row in restored.bindings] == [
            row.model_dump() for row in graph.bindings
        ]
        from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity

        version = await session.get(WorkflowVersionEntity, identity)
        owner = await session.get(UserEntity, owner_id)
        root = await session.get(WorkflowDefinitionEntity, root_id)
        assert version is not None and owner is not None and root is not None
        await service.publish(create_ref_id(version.id, version.version), owner.id)
        checksum = version.graph_checksum
        forms = FormService(session)
        form = await forms.create(
            FormCreateDTO(code="O" + uuid7().hex, name="Object source form"), owner.id
        )
        form_version = await forms.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(form.id, form.version),
                number=1,
                data_schema={
                    "type": "object",
                    "properties": {"amount": {"type": "integer"}},
                    "required": ["amount"],
                },
                render_schema={
                    "root": {
                        "component": "vertical",
                        "children": [
                            {
                                "component": "number",
                                "scope": "/properties/amount",
                                "label": "Amount",
                            }
                        ],
                    }
                },
            )
        )
        await forms.publish(create_ref_id(form_version.id, form_version.version), owner.id)
        requests = RequestService(session)
        kind = await requests.create_type(
            RequestTypeCreateDTO(
                code="O" + uuid7().hex,
                name="Object composition",
                workflow_ref_id=create_ref_id(root.id, root.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(kind.id, kind.version), data={"amount": 0}
            ),
            owner,
        )
        original_ref = create_ref_id(draft.id, draft.version)
        command = BusinessRequestSubmitDTO(submit_key=uuid7().hex)
        submitted, _ = await requests.submit(original_ref, command, owner)
        first_process = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id
                )
            )
        ).one()
        assert first_process.status == "COMPLETED", first_process.last_error_code
        result_rows = (
            await session.exec(
                select(StepExecutionEntity).where(
                    StepExecutionEntity.process_instance_id == first_process.id
                )
            )
        ).all()
        result = next(
            (row.output_snapshot or {})["result"]
            for row in result_rows
            if isinstance((row.output_snapshot or {}).get("result"), dict)
        )
        assert result == {
            "count": 0,
            "original": 0,
            "priority": submitted.priority,
            "flag": False,
            "items": [1, 2],
            "note": None,
        }
        assert type(result["count"]) is int and type(result["flag"]) is bool
        replayed, _ = await requests.submit(original_ref, command, owner)
        assert replayed.id == submitted.id
        assert (
            len(
                (
                    await session.exec(
                        select(ProcessInstanceEntity).where(
                            ProcessInstanceEntity.business_request_id == submitted.id
                        )
                    )
                ).all()
            )
            == 1
        )
        assert version.graph_checksum == checksum
        assert all(
            row.target_projection is None
            for row in (await service.snapshot(identity)).bindings
            if row.step == "cast"
        )
        await session.commit()


@pytest.mark.anyio
async def test_object_preview_http_is_authorized_bounded_redacted_and_does_not_execute():
    from httpx import ASGITransport, AsyncClient

    from main import app
    from tests.integration.test_studio_workspace import seed_studio

    fixture = await seed_studio()
    async with SessionFactory() as session:
        _, _, _, graph = await object_graph(session)
        await session.commit()
    base = "/api/v1/workflow-versions/" + fixture["version_ref"]
    payload = {
        "graph": graph.model_dump(mode="json"),
        "target_step": "assemble",
        "target_port": "value",
        "samples": [
            {"ordinal": 0, "value": 0},
            {"ordinal": 1, "value": 0},
            {"ordinal": 2, "value": 0},
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

        async def login(name):
            response = await client.post(
                "/api/v1/auth/login", json={"username": name, "password": fixture["password"]}
            )
            assert response.status_code == 200
            return {"Authorization": "Bearer " + response.json()["data"]["access_token"]}

        headers = await login(fixture["username"])
        denied = await login(fixture["outsider"])
        assert (await client.post(base + "/binding-preview", json=payload)).status_code == 401
        assert (
            await client.post(base + "/binding-preview", headers=denied, json=payload)
        ).status_code == 403
        valid = await client.post(base + "/binding-preview", headers=headers, json=payload)
        assert valid.status_code == 200, valid.text
        assert valid.headers["cache-control"] == "private, no-store"
        data = valid.json()["data"]
        assert data["sample_state"] == "VALID", data
        assert len(data["fields"]) == 6
        assert {field["value_type"] for field in data["fields"]} == {
            "integer",
            "boolean",
            "array",
            "null",
        }
        assert data["values_redacted"] and not any(
            data[key] for key in ("provider_called", "tool_called", "handler_called")
        )
        assert all(
            set(field) == {"path", "source_kind", "sample_origin", "value_type"}
            for field in data["fields"]
        )
        missing = dict(payload, samples=[])
        assert (await client.post(base + "/binding-preview", headers=headers, json=missing)).json()[
            "data"
        ]["sample_state"] == "MISSING"
        invalid = dict(payload, samples=[{"ordinal": 0, "value": "PRIVATE-SAMPLE-SENTINEL"}])
        reply = await client.post(base + "/binding-preview", headers=headers, json=invalid)
        assert reply.json()["data"]["sample_state"] == "INVALID"
        assert "PRIVATE-SAMPLE-SENTINEL" not in reply.text
        override = dict(payload, samples=[{"ordinal": 3, "value": True}])
        assert (
            await client.post(base + "/binding-preview", headers=headers, json=override)
        ).json()["data"]["sample_state"] == "INVALID"
        duplicate = dict(payload, samples=[{"ordinal": 0, "value": 0}] * 2)
        assert (
            await client.post(base + "/binding-preview", headers=headers, json=duplicate)
        ).status_code == 422
        oversized = dict(payload, samples=[{"ordinal": 0, "value": "x" * 32769}])
        assert (
            await client.post(base + "/binding-preview", headers=headers, json=oversized)
        ).status_code == 422
        assert (await client.get(base + "/graph", headers=headers)).json()["data"]["bindings"] == []
        saved = await client.put(
            base + "/workspace",
            headers=headers,
            json={"workspace_ref_id": None, "document": {"graph": payload["graph"]}},
        )
        assert saved.status_code == 200
        promoted = await client.post(
            base + "/workspace/promote",
            headers=headers,
            json={"workspace_ref_id": saved.json()["data"]["workspace_ref_id"]},
        )
        assert promoted.status_code == 200, promoted.text
        assert (
            await client.post(base + "/binding-preview", headers=headers, json=payload)
        ).status_code == 409
        current = "/api/v1/workflow-versions/" + promoted.json()["data"]["ref_id"]
        published = await client.post(current + "/publish", headers=headers)
        assert published.status_code == 200, published.text


@pytest.mark.anyio
async def test_agent_context_uses_composed_declaration_and_only_visible_constant_or_author_samples():
    from apps.ai.application.agent_service import AIAgentService
    from apps.ai.application.authoring import AIAgentAuthoringService
    from apps.ai.domain.authoring import AIWorkflowContextInput
    from tests.apps.ai.test_authoring_preview import spec

    async with SessionFactory() as session:
        service, owner, version, graph = await prepare_graph(session)
        from apps.step_types.application.registry import get_registry

        service = WorkflowService(session, get_registry())
        agent = await AIAgentService(session).create(
            "AC" + uuid7().hex, "Composed context", spec(), owner
        )
        agent_ref = create_ref_id(agent.id, agent.version)
        rows = (
            await session.exec(
                select(StepTypeEntity, StepTypeVersionEntity)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
                )
                .where(
                    StepTypeEntity.code == "AI_DECISION",
                    StepTypeVersionEntity.status == "PUBLISHED",
                )
            )
        ).all()
        _, pin = rows[0]
        candidate = graph.model_dump(mode="json")
        candidate["steps"][1].update(
            type_code="AI_DECISION",
            type_version_ref=create_ref_id(pin.id, pin.version),
            config={"agent_ref": agent_ref},
        )
        candidate["transitions"][1].update(condition=None, is_default=True)
        from apps.forms.application.service import FormService
        from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO

        forms = FormService(session)
        form = await forms.create(
            FormCreateDTO(code="H" + uuid7().hex, name="Review sample"), owner.id
        )
        form_version = await forms.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(form.id, form.version),
                number=1,
                data_schema={"type": "object", "properties": {}},
                render_schema={
                    "root": {"component": "vertical", "children": []},
                    "outcomes": ["approve"],
                },
            )
        )
        form_version = await forms.publish(
            create_ref_id(form_version.id, form_version.version), owner.id
        )
        human_pin = (
            await session.exec(
                select(StepTypeVersionEntity)
                .join(
                    StepTypeEntity,
                    col(StepTypeEntity.id) == col(StepTypeVersionEntity.step_type_id),
                )
                .where(
                    StepTypeEntity.code == "HUMAN_TASK", StepTypeVersionEntity.status == "PUBLISHED"
                )
            )
        ).first()
        assert human_pin is not None
        candidate["steps"].append(
            {
                "key": "review",
                "type_code": "HUMAN_TASK",
                "type_version_ref": create_ref_id(human_pin.id, human_pin.version),
                "form_ref": create_ref_id(form_version.id, form_version.version),
                "field_policy": {"read": [], "write": [], "required": [], "hidden": []},
            }
        )
        candidate["transitions"].extend(
            [
                {"source": "cast", "target": "review", "outcome": "review", "is_default": True},
                {"source": "review", "target": "finish", "outcome": "approve", "is_default": True},
            ]
        )
        candidate["targets"] = [
            {"step": "review", "user_ref": create_ref_id(owner.id, owner.version)}
        ]

        choices = [{"key": key, "labels": {"en": key}, "description": key} for key in ("a", "b")]
        root = {
            "type": "object",
            "properties": {"options": {"type": "array", "items": {"type": "object"}}},
            "required": ["options"],
        }
        candidate["bindings"] = [
            {
                "step": "cast",
                "target_port": "data",
                "target_schema": root,
                "ordinal": 0,
                "target_projection": {"dialect": "bpms.binding.object/1", "path": "/options"},
                "source_kind": "CONSTANT",
                "constant_value": choices,
            }
        ]
        from utils.exceptions import ValidationDetailsException

        try:
            version = await service.replace_graph(
                create_ref_id(version.id, version.version), GraphSnapshot.model_validate(candidate)
            )
        except ValidationDetailsException as error:
            pytest.fail(str(error.issues))
        data = AIWorkflowContextInput(
            workflow_version_ref=create_ref_id(version.id, version.version), step_key="cast"
        )
        authoring = AIAgentAuthoringService(session)
        constant = await authoring.workflow_context(agent_ref, data, owner)
        assert constant.input_schema == root and constant.sample_origin == "CONSTANT_BINDING"
        assert constant.decision.sample_state == "VALID" and not constant.decision.provider_called
        candidate["bindings"][0].update(
            source_kind="REQUEST", source_path="/options", source_schema=root
        )
        candidate["bindings"][0].pop("constant_value")
        from utils.exceptions import ValidationDetailsException

        try:
            version = await service.replace_graph(
                create_ref_id(version.id, version.version), GraphSnapshot.model_validate(candidate)
            )
        except ValidationDetailsException as error:
            pytest.fail(str(error.issues))
        data.workflow_version_ref = create_ref_id(version.id, version.version)
        missing = await authoring.workflow_context(agent_ref, data, owner)
        assert missing.sample_origin == "NONE" and missing.decision.sample_state == "MISSING"
        data = AIWorkflowContextInput.model_validate(
            {**data.model_dump(), "sample_inputs": {"options": choices}}
        )
        supplied = await authoring.workflow_context(agent_ref, data, owner)
        assert supplied.sample_origin == "AUTHOR" and supplied.decision.sample_state == "VALID"
        await session.rollback()
