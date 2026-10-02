"""Tests for localized, self-hosted API documentation."""

import pytest
import yaml
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from core.settings import settings
from utils.localized_docs import configure_localized_docs, localized_openapi


def docs_app() -> FastAPI:
    app = FastAPI(
        title="test",
        description=settings.PROJECT_DESCRIPTION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    configure_localized_docs(app)
    return app


def test_openapi_metadata_is_localized_without_mutating_default() -> None:
    assert settings.DOCS_URL == "/api/v1/swagger-ui"
    assert settings.REDOC_URL == "/api/v1/redoc"
    assert settings.OPENAPI_URL == "/api/v1/openapi.json"
    assert settings.OPENAPI_YAML_URL == "/api/v1/openapi.yaml"
    app = docs_app()
    english = localized_openapi(app, "en")
    persian = localized_openapi(app, "fa")
    assert english["x-docs-language"] == "en"
    assert persian["x-docs-language"] == "fa"
    assert english["info"]["description"] == settings.PROJECT_DESCRIPTION
    assert english["info"]["description"] != persian["info"]["description"]
    assert app.openapi()["info"]["description"] == settings.PROJECT_DESCRIPTION


@pytest.mark.anyio
async def test_docs_and_schema_use_accept_language_at_one_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SWAGGER_CLIENT_ID", "swagger-client")
    monkeypatch.setattr(settings, "SWAGGER_CLIENT_SECRET", "swagger-secret")
    app = docs_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        swagger = await client.get(settings.DOCS_URL, headers={"Accept-Language": "fa-IR"})
        redoc = await client.get(settings.REDOC_URL, headers={"Accept-Language": "fa-IR"})
        schema = await client.get(settings.OPENAPI_URL, headers={"Accept-Language": "fa-IR"})
        yaml_schema = await client.get(
            settings.OPENAPI_YAML_URL,
            headers={"Accept-Language": "fa-IR"},
        )
        swagger_javascript = await client.get(
            f"{settings.DOCS_ASSETS_URL}/swagger-ui/swagger-ui-bundle.js"
        )
        redoc_javascript = await client.get(f"{settings.DOCS_ASSETS_URL}/redoc/redoc.standalone.js")
        unknown_asset = await client.get(f"{settings.DOCS_ASSETS_URL}/not-vendored.js")
        language_path = await client.get(f"{settings.DOCS_URL}/en")
        old_docs = await client.get("/docs")
        old_redoc = await client.get("/redoc")
        old_schema = await client.get("/openapi.json")

    assert settings.OPENAPI_URL in swagger.text
    assert settings.OPENAPI_URL in redoc.text
    assert settings.DOCS_ASSETS_URL in swagger.text
    assert settings.DOCS_ASSETS_URL in redoc.text
    assert "https://" not in swagger.text
    assert "https://" not in redoc.text
    assert '"clientId": "swagger-client"' in swagger.text
    assert '"clientSecret": "swagger-secret"' in swagger.text
    assert '"operationsSorter": (left, right) =>' in swagger.text
    assert '"operationsSorter": "subjectCrudOrder"' not in swagger.text
    assert '"operationsSorter": "method"' not in swagger.text
    assert swagger.headers["content-language"] == "fa"
    assert redoc.headers["content-language"] == "fa"
    assert redoc.headers["vary"] == "Accept-Language"
    assert schema.headers["content-language"] == "fa"
    assert schema.headers["vary"] == "Accept-Language"
    assert schema.json()["x-docs-language"] == "fa"
    assert yaml_schema.headers["content-language"] == "fa"
    assert yaml_schema.headers["vary"] == "Accept-Language"
    assert yaml_schema.headers["content-type"].startswith("application/yaml")
    assert yaml.safe_load(yaml_schema.text) == schema.json()
    assert swagger_javascript.status_code == 200
    assert redoc_javascript.status_code == 200
    assert unknown_asset.status_code == 404
    assert language_path.status_code == 404
    assert old_docs.status_code == 404
    assert old_redoc.status_code == 404
    assert old_schema.status_code == 404


def test_designer_tags_have_localized_descriptions() -> None:
    from main import app as main_app

    english = {tag["name"]: tag for tag in main_app.openapi()["tags"]}
    persian = {tag["name"]: tag for tag in localized_openapi(main_app, "fa")["tags"]}
    for name in ("designer", "definition-library"):
        assert english[name]["description"]
        assert persian[name]["description"]
        assert persian[name]["description"] != english[name]["description"]


def test_all_topic_descriptions_are_localized() -> None:
    from main import app as main_app

    english = {tag["name"]: tag["description"] for tag in main_app.openapi()["tags"]}
    persian = {tag["name"]: tag["description"] for tag in localized_openapi(main_app, "fa")["tags"]}
    assert english.keys() == persian.keys()
    for name, description in english.items():
        assert description
        assert persian[name] and persian[name] != description, name
