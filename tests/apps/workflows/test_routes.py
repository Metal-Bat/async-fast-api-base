import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.anyio
async def test_workflow_routes_are_protected_and_follow_resource_contract() -> None:
    schema = app.openapi()
    for resource in ("workflows", "workflow-versions"):
        base = "/api/v1/" + resource
        assert "post" in schema["paths"][base + "/search"]
        assert "get" in schema["paths"][base + "/{ref_id}"]
        assert "post" in schema["paths"][base + "/{ref_id}/history"]
        assert "post" in schema["paths"][base + "/report"]
    assert "put" in schema["paths"]["/api/v1/workflows/{ref_id}"]
    assert "post" in schema["paths"]["/api/v1/workflows/{ref_id}/grants"]
    assert "get" in schema["paths"]["/api/v1/workflow-versions/{ref_id}/graph"]
    assert "put" in schema["paths"]["/api/v1/workflow-versions/{ref_id}/graph"]
    assert "post" in schema["paths"]["/api/v1/workflow-versions/{ref_id}/publish"]
    assert "post" in schema["paths"]["/api/v1/workflow-versions/{ref_id}/retire"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/workflows/validate", json={})
        assert response.status_code == 401
