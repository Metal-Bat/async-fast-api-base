import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.anyio
async def test_authorized_preview_returns_validation_locations(monkeypatch) -> None:
    from uuid import uuid7

    from apps.clients.domain.contracts import ClientContext
    from apps.users.domain.entity import UserEntity
    from core.deps import get_current_client_context, get_current_user

    user = UserEntity(id=uuid7(), username="designer", hashed_password="hash", is_superuser=True)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: user)
    monkeypatch.setitem(app.dependency_overrides, get_current_client_context, ClientContext.legacy)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/forms/preview",
            json={
                "data_schema": {"type": "object"},
                "render_schema": {"root": {"component": "javascript"}},
            },
        )
        assert response.status_code == 200
        result = response.json()["data"]
        assert not result["valid"] and result["render_schema"] is None
        assert result["issues"][0]["pointer"] == "/render_schema/root/component"


@pytest.mark.anyio
async def test_form_routes_are_protected_and_follow_resource_contract() -> None:
    schema = app.openapi()
    for resource in ("forms", "form-versions"):
        base = "/api/v1/" + resource
        assert "post" in schema["paths"][base + "/search"]
        assert "get" in schema["paths"][base + "/{ref_id}"]
        assert "put" in schema["paths"][base + "/{ref_id}"]
        assert "post" in schema["paths"][base + "/{ref_id}/history"]
        assert "post" in schema["paths"][base + "/report"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/forms/validate", json={"data_schema": {}, "render_schema": {}}
        )
        assert response.status_code == 401
    assert "post" in schema["paths"]["/api/v1/forms/preview"]
    assert "post" in schema["paths"]["/api/v1/form-versions/{ref_id}/publish"]


@pytest.mark.anyio
async def test_client_predicate_preview_uses_bound_context_not_forged_headers(monkeypatch):
    from uuid import uuid7

    from apps.clients.domain.contracts import ClientContext
    from apps.users.domain.entity import UserEntity
    from core.deps import get_current_client_context, get_current_user

    user = UserEntity(
        id=uuid7(), username="predicate-designer", hashed_password="hash", is_superuser=True
    )
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: user)
    context = ClientContext(kind="DESKTOP", release="2.10", trusted=True)
    monkeypatch.setitem(app.dependency_overrides, get_current_client_context, lambda: context)
    payload = {
        "data_schema": {"type": "object"},
        "render_schema": {"root": {"component": "vertical"}},
        "variants": [
            {
                "key": "desktop",
                "priority": 10,
                "condition": 'client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)',
                "render_schema": {"root": {"component": "grid"}},
            }
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/forms/preview",
            json=payload,
            headers={"X-Client-Kind": "ANDROID", "X-Client-Version": "1.0"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["variant_key"] == "desktop"
        context = ClientContext.legacy()
        fallback = await client.post(
            "/api/v1/forms/preview",
            json=payload,
            headers={"X-Client-Kind": "DESKTOP", "X-Client-Version": "2.10"},
        )
        assert fallback.json()["data"]["variant_key"] == "shared"


def test_client_predicate_openapi_contract_is_bounded_and_typed():
    app.openapi_schema = None
    schema = app.openapi()
    variant = schema["components"]["schemas"]["FormDesignVariantDTO"]["properties"]
    condition = variant["condition"]
    assert condition["anyOf"][0]["maxLength"] == 1024
    assert condition["examples"]
    from utils.localized_docs import localized_openapi

    localized = localized_openapi(app, "fa")
    assert (
        localized["components"]["schemas"]["FormDesignVariantDTO"]["properties"]["condition"][
            "description"
        ]
        != condition["description"]
    )
    assert (
        localized["paths"]["/api/v1/forms/preview"]["post"]["description"]
        != schema["paths"]["/api/v1/forms/preview"]["post"]["description"]
    )
    issues = schema["components"]["schemas"]["ValidationIssue"]["properties"]
    assert {"pointer", "code", "line", "column"} <= issues.keys()
    completion = schema["components"]["schemas"]["CompletionItemDTO"]["properties"]
    assert "client" in completion["source"]["enum"]
    assert schema["paths"]["/api/v1/forms/preview"]["post"]["security"]


@pytest.mark.anyio
async def test_field_catalog_options_and_navigation_http_contract(monkeypatch):
    from uuid import uuid7

    from apps.clients.domain.contracts import ClientContext
    from apps.users.domain.entity import UserEntity
    from core.deps import get_current_client_context, get_current_user
    from core.settings import settings
    from tests.apps.forms.test_navigation import navigation_documents
    from tests.apps.forms.test_options import dependent_document

    actor = UserEntity(
        id=uuid7(), username="field-designer", hashed_password="hash", is_superuser=True
    )
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: actor)
    monkeypatch.setitem(app.dependency_overrides, get_current_client_context, ClientContext.legacy)
    monkeypatch.setattr(settings, "FORM_NAVIGATION_ROUTES", ["/people/pick"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        catalog = await client.post("/api/v1/forms/field-catalog")
        assert catalog.status_code == 200 and len(catalog.json()["data"]) == 20
        payload = {
            "documents": dependent_document().model_dump(),
            "query": {
                "node_pointer": "/root/children/1",
                "data": {"country": "IR"},
                "generation": 8,
            },
        }
        response = await client.post(
            "/api/v1/forms/options", json=payload, headers={"Accept-Language": "fa"}
        )
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "private, no-store"
        result = response.json()["result"]
        assert result["items"] == [{"key": "json:1", "value": "Tehran"}]
        assert result["generation"] == 8 and result["locale"] == "fa"
        payload["query"]["variant_key"] = "forged"
        assert (await client.post("/api/v1/forms/options", json=payload)).status_code == 422
        preview = await client.post(
            "/api/v1/forms/navigation-preview",
            json={
                "documents": navigation_documents().model_dump(),
                "query": {"node_pointer": "/root", "data": {"person": "old", "name": "Original"}},
            },
        )
        assert preview.status_code == 200
        assert preview.json()["data"]["plan"]["arguments"] == {"current": "old"}
        assert preview.headers["Cache-Control"] == "private, no-store"


def test_field_openapi_discriminators_localization_and_cache_headers():
    from utils.localized_docs import localized_openapi

    app.openapi_schema = None
    schema = app.openapi()
    fa = localized_openapi(app, "fa")
    for path in (
        "/api/v1/forms/options",
        "/api/v1/forms/navigation-preview",
        "/api/v1/business-requests/{ref_id}/options",
        "/api/v1/work-items/{ref_id}/options",
    ):
        operation = schema["paths"][path]["post"]
        assert operation["security"]
        assert "Cache-Control" in operation["responses"]["200"]["headers"]
        assert operation["description"] != fa["paths"][path]["post"]["description"]
    schemas = schema["components"]["schemas"]
    assert schemas["OptionQuery"]["additionalProperties"] is False
    assert schemas["OptionResult"]["properties"]["key_encoding"]["const"] == "json-scalar/1"
