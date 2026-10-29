"""AI authoring and capability HTTP contract."""


def test_ai_authoring_and_catalog_routes_are_protected_and_typed() -> None:
    from main import app

    schema = app.openapi()
    paths = schema["paths"]
    expected = {
        "/api/v1/ai-agents/search": "post",
        "/api/v1/ai-agents/{ref_id}": "get",
        "/api/v1/ai-agents/report": "post",
        "/api/v1/ai-agents": "post",
        "/api/v1/ai-agents/{ref_id}/publish": "post",
        "/api/v1/ai-agents/select": "post",
        "/api/v1/ai-agents/providers/select": "post",
        "/api/v1/ai-agents/connections/select": "post",
        "/api/v1/ai-agents/models/suggestions": "post",
        "/api/v1/ai-agents/processes/{process_ref}/executions/{execution_ref}/budget": "get",
        "/api/v1/ai-agents/connections/{connection_ref}/models/select": "post",
        "/api/v1/ai-agents/{ref_id}/decision-preview": "post",
        "/api/v1/ai-agents/{ref_id}/workflow-context": "post",
        "/api/v1/ai-agents/{ref_id}/retrieval-sources/search": "post",
        "/api/v1/ai-agents/{ref_id}/retrieval-preview": "post",
        "/api/v1/ai-agents/{ref_id}/evaluations": "post",
    }
    for path, method in expected.items():
        operation = paths[path][method]
        assert operation["tags"] == ["ai-agents"]
        assert operation["security"]
    create = paths["/api/v1/ai-agents"]["post"]
    body = create["requestBody"]["content"]["application/json"]["schema"]
    assert "AIAgentCreateDTO" in str(body)


def test_ai_swagger_summary_description_and_tag_translate_to_farsi() -> None:
    from main import app
    from utils.localized_docs import localized_openapi

    english = app.openapi()
    persian = localized_openapi(app, "fa")
    path = "/api/v1/ai-agents/search"
    for field in ("summary", "description"):
        assert persian["paths"][path]["post"][field] != english["paths"][path]["post"][field]
    en_tag = next(tag for tag in english["tags"] if tag["name"] == "ai-agents")
    fa_tag = next(tag for tag in persian["tags"] if tag["name"] == "ai-agents")
    assert fa_tag["description"] != en_tag["description"]


def test_tool_approval_api_has_protected_bounded_contracts() -> None:
    from main import app

    schema = app.openapi()
    path = "/api/v1/ai-agents/work-items/{work_item_ref}/tool-approval"
    assert schema["paths"][path]["get"]["security"]
    assert schema["paths"][path]["post"]["security"]
    command = schema["components"]["schemas"]["AIToolApprovalCommandDTO"]
    assert set(command["required"]) == {"approved", "command_key"}
    assert command["properties"]["command_key"]["maxLength"] == 128
    result = schema["components"]["schemas"]["AIToolApprovalDTO"]
    assert "messages" not in result["properties"]
    assert "payload_ciphertext" not in result["properties"]


def test_authoring_routes_reject_unauthenticated_requests_and_evaluation_requires_both_permissions():
    from fastapi import FastAPI
    from fastapi.routing import APIRoute
    from fastapi.testclient import TestClient

    from apps.ai.presentation.routes import router
    from apps.users.application.authorization import RequirePermission

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    for suffix, body in [
        ("decision-preview", {}),
        ("workflow-context", {"workflow_version_ref": "current", "step_key": "classify"}),
        ("retrieval-sources/search", {}),
        ("retrieval-preview", {"report_ref": "current", "limit": 1}),
        ("evaluations", {"request_ref": "current", "submit_key": "reviewed"}),
    ]:
        response = client.post("/api/v1/ai-agents/current/" + suffix, json=body)
        assert response.status_code in (401, 403)
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.path == "/ai-agents/{ref_id}/evaluations"
    )
    permissions = {
        dep.call.permission
        for dep in route.dependant.dependencies
        if isinstance(dep.call, RequirePermission)
    }
    assert permissions == {"workflows.manage", "requests.start"}
