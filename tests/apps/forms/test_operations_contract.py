"""Observable contracts required by frontend operational steps."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.forms.application.runtime import display_page
from main import app


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/business-requests/{ref_id}/attachments/{attachment_ref_id}/content",
        "/api/v1/work-items/{ref_id}/attachments/{attachment_ref_id}/content",
        "/api/v1/reports/{ref_id}/download",
    ],
)
def test_private_stream_schema_is_binary(path):
    content = app.openapi()["paths"][path]["get"]["responses"]["200"]["content"]
    assert any(row.get("schema", {}).get("format") == "binary" for row in content.values())


def test_declared_pages_are_bounded_and_actor_filtered():
    settings = {
        "pages": [
            {"key": "public", "title": "Visible", "scopes": ["/properties/name"]},
            {"key": "private", "title": "Secret", "scopes": ["/properties/hidden"]},
        ],
        "script": "unsafe",
    }
    assert display_page(settings, {"/properties/name"}) == {
        "pages": [{"key": "public", "title": "Visible", "scopes": ["/properties/name"]}]
    }
    assert "pages" not in display_page({"pages": [{}] * 33}, {"/properties/name"})


def test_history_is_metadata_only_and_authenticated():
    schema = app.openapi()
    for subject in ("business-requests", "work-items"):
        route = schema["paths"][f"/api/v1/{subject}/{{ref_id}}/history"]["post"]
        assert route["security"]
    fields = schema["components"]["schemas"]["ResourceHistoryDTO"]["properties"]
    assert set(fields) == {"changed_at", "operation", "version"}


@pytest.mark.anyio
async def test_request_collection_returns_latest_owning_runtime(monkeypatch):
    from apps.requests.presentation import routes

    runtime = object()
    service = MagicMock(edit_collection=AsyncMock(), runtime_state=AsyncMock(return_value=runtime))
    monkeypatch.setattr(routes, "RequestService", lambda _: service)
    monkeypatch.setattr(routes, "success_response", lambda request, data: data)
    session = MagicMock(commit=AsyncMock())
    result = await routes.edit_request_collection(
        MagicMock(), "current", MagicMock(), MagicMock(), MagicMock(), session
    )
    assert result is runtime
    service.runtime_state.assert_awaited_once()
