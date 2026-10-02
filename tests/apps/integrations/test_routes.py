from main import app


def test_connection_routes_and_secret_free_response_contract() -> None:
    schema = app.openapi()
    base = "/api/v1/integration-connections"
    for path in (
        "",
        "/search",
        "/report",
        "/{ref_id}/history",
        "/{ref_id}/rotate",
        "/{ref_id}/verify",
        "/{ref_id}/revoke",
        "/{ref_id}/grants",
    ):
        assert "post" in schema["paths"][base + path]
    assert "get" in schema["paths"][base + "/{ref_id}"]
    fields = schema["components"]["schemas"]["ConnectionDTO"]["properties"]
    assert "secret_ref" not in fields and "secret_version" not in fields
