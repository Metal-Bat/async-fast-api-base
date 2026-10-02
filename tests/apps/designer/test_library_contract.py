"""Public contracts for reusable-definition discovery and draft decisions."""

import pytest

from main import app


def test_library_routes_are_typed_and_protected():
    app.openapi_schema = None
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/designer/library/search",
        "/api/v1/designer/library/{kind}/{ref_id}/dependencies",
        "/api/v1/designer/library/{kind}/{ref_id}/where-used",
        "/api/v1/designer/library/{kind}/{ref_id}/compare",
        "/api/v1/designer/library/upgrade-preview",
        "/api/v1/designer/library/templates",
        "/api/v1/designer/library/{kind}/{ref_id}/guidance",
        "/api/v1/designer/library/form-versions/{ref_id}/explanation",
    ):
        operation = paths[path]["post"]
        assert operation["security"]
        assert operation["responses"].get("200") or operation["responses"].get("201")


@pytest.mark.anyio
async def test_library_routes_require_authentication():
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/designer/library/search", json={})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_library_select_returns_version_refs_and_bounded_page(monkeypatch):
    from unittest.mock import Mock

    from apps.designer.application.library import DefinitionLibraryService
    from apps.designer.domain.library import LibraryCard, LibrarySelectQuery
    from utils.pagination import Page

    async def search(self, query, actor):
        assert query.kind == "subprocess"
        assert query.search == "review"
        assert query.size == 1
        return Page[LibraryCard](
            items=[
                LibraryCard(
                    kind="subprocess",
                    ref_id="version-ref",
                    root_ref_id="root-ref",
                    code="review_case",
                    title="Review case",
                    number=2,
                    category="approval",
                    status="PUBLISHED",
                )
            ],
            page=2,
            size=1,
            total=3,
        )

    monkeypatch.setattr(DefinitionLibraryService, "search", search)
    result = await DefinitionLibraryService(Mock()).select(
        LibrarySelectQuery(kind="subprocess", search="review", page=2, size=1), Mock()
    )
    assert result.total == 3
    assert result.page == 2
    assert [item.model_dump() for item in result.items] == [
        {"key": "version-ref", "value": "Review case · v2"}
    ]


def test_library_select_is_documented_as_key_value_options():
    operation = app.openapi()["paths"]["/api/v1/designer/library/select"]["post"]
    assert operation["security"]
    assert "200" in operation["responses"]
