"""Authored-library resources keep the project's protected CRUD contract."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


def test_library_openapi_has_subject_crud_and_typed_versions():
    app.openapi_schema = None
    schema = app.openapi()
    for resource in (
        "form-components",
        "form-data-types",
        "form-component-versions",
        "form-data-type-versions",
    ):
        path = "/api/v1/" + resource
        assert "post" in schema["paths"][path + "/search"]
        assert "get" in schema["paths"][path + "/{ref_id}"]
        assert "post" in schema["paths"][path + "/report"]
        assert "post" in schema["paths"][path + "/{ref_id}/history"]
    assert schema["paths"]["/api/v1/form-component-versions/{ref_id}/publish"]["post"]["security"]


@pytest.mark.anyio
async def test_library_routes_require_authorization():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/form-components/search", json={})
    assert response.status_code == 401


def test_reuse_and_behavior_operations_are_documented_and_protected():
    app.openapi_schema = None
    schema = app.openapi()
    paths = schema["paths"]
    for path in (
        "/api/v1/forms/copy-component",
        "/api/v1/form-versions/{ref_id}/reuse-upgrade-preview",
        "/api/v1/forms/behavior-preview",
        "/api/v1/business-requests/{ref_id}/collections/edit",
        "/api/v1/work-items/{ref_id}/collections/edit",
        "/api/v1/business-requests/{ref_id}/overrides",
        "/api/v1/work-items/{ref_id}/overrides",
    ):
        assert paths[path]["post"]["security"]
    component = schema["components"]["schemas"]["ComponentUse"]
    assert "instance_key" in component["properties"]
    assert "component_ref" in component["properties"]
    assert "instanceKey" not in component["properties"]
