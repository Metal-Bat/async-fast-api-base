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
