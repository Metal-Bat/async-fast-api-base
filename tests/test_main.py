"""Tests for application assembly and lifespan behavior."""

from unittest.mock import Mock

import pytest


def test_application_exposes_expected_routes() -> None:
    from main import app

    schema = app.openapi()
    paths = schema["paths"]
    assert "/api/v1/media/files" in paths
    assert "/api/v1/media/images" in paths
    assert "/api/v1/tasks/schedules" in paths
    assert "/api/v1/tasks/definitions/search" in paths
    assert "/api/v1/tasks/definitions/select" in paths
    assert "/api/v1/tasks/queues/select" in paths
    assert "/api/v1/tasks/definitions/{ref_id}/history" in paths
    assert "/api/v1/tasks/schedules/search" in paths
    assert "/api/v1/tasks/executions/search" in paths
    assert "/api/v1/tasks/executions/{ref_id}" in paths
    assert "/api/v1/tasks/schedules/{ref_id}/history" in paths
    assert "/api/v1/admin/users/search" in paths
    assert "/api/v1/admin/work-groups/search" in paths
    assert "/api/v1/admin/work-groups/select" in paths
    assert "/api/v1/admin/roles/search" in paths
    assert "/api/v1/admin/permissions/search" in paths
    assert "/api/v1/admin/audit-events/{ref_id}" in paths
    assert "/api/v1/admin/roles/{ref_id}/history" in paths
    assert "/api/v1/admin/permissions/{ref_id}/history" in paths
    assert "/api/v1/admin/users/{ref_id}" in paths
    assert "/api/v1/auth/me" in paths
    assert "/api/v1/auth/sessions/{ref_id}" in paths
    event_path = paths["/api/v1/process-events/{event_type}/deliver"]["post"]
    assert event_path["security"] == [{"OAuth2PasswordBearer": []}]
    assert "/health" in paths
    assert "/ready" in paths
    assert "/internal/{service_name}" in paths
    assert "/api/v1/health" not in paths
    assert "security" not in paths["/internal/{service_name}"]["get"]
    assert "/api/v1/users/" not in paths
    assert paths["/api/v1/media/files/{ref_id}"]["get"]["security"] == [
        {"OAuth2PasswordBearer": []}
    ]
    assert paths["/api/v1/media/images/{ref_id}"]["get"]["security"] == [
        {"OAuth2PasswordBearer": []}
    ]
    assert schema["info"]["description"]
    password_flow = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"][
        "password"
    ]
    assert password_flow["tokenUrl"] == "/api/v1/auth/token"
    assert app.swagger_ui_parameters is not None
    assert app.swagger_ui_parameters["persistAuthorization"] is True
    assert app.swagger_ui_parameters["operationsSorter"] == "subjectCrudOrder"
    assert [tag["name"] for tag in schema["tags"]] == [
        "auth",
        "me",
        "saved-views",
        "favorites",
        "sessions",
        "users",
        "roles",
        "permissions",
        "work-groups",
        "audit-events",
        "history",
        "clients",
        "client-releases",
        "designer",
        "resource-links",
        "definition-library",
        "forms",
        "form-versions",
        "form-components",
        "form-component-versions",
        "form-data-types",
        "form-data-type-versions",
        "step-types",
        "workflows",
        "workflow-versions",
        "request-types",
        "business-requests",
        "processes",
        "process-events",
        "work-items",
        "integration-connections",
        "ai-agents",
        "notifications",
        "files",
        "images",
        "reports",
        "analytics",
        "task-definitions",
        "task-schedules",
        "task-executions",
        "setup",
        "calendar-events",
        "support-incidents",
        "inbox",
        "health",
    ]
    assert paths["/api/v1/admin/permissions/search"]["post"]["tags"] == ["permissions"]
    assert paths["/api/v1/admin/roles/search"]["post"]["tags"] == ["roles"]
    assert paths["/api/v1/tasks/schedules/search"]["post"]["tags"] == ["task-schedules"]
    assert paths["/api/v1/tasks/run"]["post"]["tags"] == ["task-executions"]


@pytest.mark.anyio
async def test_lifespan_initializes_storage(monkeypatch) -> None:
    import main

    called = False

    async def ensure() -> None:
        nonlocal called
        called = True

    async def reconcile(_service) -> list[object]:
        return []

    monkeypatch.setattr(main, "ensure_bucket", ensure)
    monkeypatch.setattr(main.StepTypeService, "reconcile", reconcile)
    async with main.lifespan(main.app):
        assert called


@pytest.mark.anyio
async def test_lifespan_shuts_down_telemetry(monkeypatch) -> None:
    import main

    providers = Mock()

    async def ensure() -> None:
        pass

    async def reconcile(_service) -> list[object]:
        return []

    monkeypatch.setattr(main, "ensure_bucket", ensure)
    monkeypatch.setattr(main.StepTypeService, "reconcile", reconcile)
    monkeypatch.setattr(main, "telemetry_providers", providers)

    async with main.lifespan(main.app):
        providers.shutdown.assert_not_called()

    providers.shutdown.assert_called_once_with()


def test_application_operations_use_documented_subject_tags() -> None:
    from main import app

    schema = app.openapi()
    descriptions = {tag["name"]: tag.get("description") for tag in schema["tags"]}
    expected_topics = {
        "/api/v1/forms/search": "forms",
        "/api/v1/form-versions/search": "form-versions",
        "/api/v1/form-components/search": "form-components",
        "/api/v1/form-component-versions/search": "form-component-versions",
        "/api/v1/form-data-types/search": "form-data-types",
        "/api/v1/form-data-type-versions/search": "form-data-type-versions",
        "/api/v1/workflows/search": "workflows",
        "/api/v1/workflow-versions/search": "workflow-versions",
        "/api/v1/request-types/search": "request-types",
        "/api/v1/business-requests/search": "business-requests",
        "/api/v1/processes/{ref_id}": "processes",
        "/api/v1/process-events/{event_type}/deliver": "process-events",
        "/api/v1/work-items/search": "work-items",
        "/api/v1/notifications/search": "notifications",
    }
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            tags = operation["tags"]
            assert len(tags) == 1, (path, method)
            assert descriptions.get(tags[0]), (path, method, tags[0])
            if path.startswith("/api/v1/"):
                assert tags != ["health"], (path, method)
            if path in expected_topics:
                assert tags == [expected_topics[path]], (path, method)
