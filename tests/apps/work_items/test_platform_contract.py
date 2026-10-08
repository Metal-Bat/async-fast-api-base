"""Machine-readable platform contracts needed by ordinary frontend actors."""

from main import app


def test_runtime_and_discovery_operations_exist_without_authoring_workarounds():
    schema = app.openapi()
    for path, method in [
        ("/api/v1/business-requests/{ref_id}/view", "get"),
        ("/api/v1/work-items/{ref_id}/runtime", "get"),
        ("/api/v1/request-types/eligible/search", "post"),
        ("/api/v1/integration-connections/{ref_id}/grants/search", "post"),
        ("/api/v1/workflows/{ref_id}/grants/search", "post"),
    ]:
        assert method in schema["paths"].get(path, {})


def test_runtime_dialect_permissions_and_current_resource_references_are_explicit():
    schemas = app.openapi()["components"]["schemas"]
    runtime = schemas["RuntimeFormStateDTO"]["properties"]
    for name in [
        "runtime_dialect",
        "resource_ref_id",
        "resource_kind",
        "form_version_ref_id",
        "submission_ref_id",
        "writable_scopes",
        "required_scopes",
        "field_metadata",
        "data",
        "render_schema",
    ]:
        assert name in runtime
    assert "kind" in schemas["WorkItemDTO"]["properties"]
    assert "process_ref_id" in schemas["BusinessRequestDTO"]["properties"]


def test_new_runtime_routes_are_localized_private_and_examples_validate():
    from apps.forms.domain.runtime import RuntimeFormStateDTO
    from utils.localized_docs import localized_openapi

    english = app.openapi()
    persian = localized_openapi(app, "fa")
    for path, method in [
        ("/api/v1/business-requests/{ref_id}/view", "get"),
        ("/api/v1/work-items/{ref_id}/runtime", "get"),
        ("/api/v1/request-types/eligible/search", "post"),
        ("/api/v1/integration-connections/{ref_id}/grants/search", "post"),
        ("/api/v1/workflows/{ref_id}/grants/search", "post"),
    ]:
        operation = english["paths"][path][method]
        assert operation["summary"] != persian["paths"][path][method]["summary"]
        assert operation["description"] != persian["paths"][path][method]["description"]
        assert operation.get("security")
        assert "Cache-Control" in operation["responses"]["200"].get("headers", {})
    for example in english["components"]["schemas"]["RuntimeFormStateDTO"]["examples"]:
        RuntimeFormStateDTO.model_validate(example)


def test_runtime_projection_removes_nested_hidden_metadata_and_executable_dependencies():
    from apps.forms.application.runtime import runtime_projection

    schema = {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "visible": {"type": "string", "default": "public-default"},
                        "private": {"type": "string", "default": "private-default"},
                    },
                    "required": ["private"],
                },
            }
        },
    }
    render = {
        "dialect": "bpms.render/1",
        "root": {
            "component": "repeater",
            "scope": "/properties/rows",
            "children": [
                {
                    "component": "text",
                    "scope": "/properties/rows/items/properties/visible",
                    "calculation": {"scopes": ["private"]},
                },
                {"component": "text", "scope": "/properties/rows/items/properties/private"},
            ],
        },
    }
    policy = {
        "read": ["/properties/rows"],
        "write": ["/properties/rows"],
        "hidden": ["/properties/rows/items/properties/private"],
    }
    state = runtime_projection(
        {"rows": [{"visible": "yes", "private": "hidden-value"}]},
        {"/rows": ["row-1"]},
        {},
        schema,
        render,
        policy,
        {"/properties/rows"},
        set(),
        set(),
    )
    assert state["data"] == {"rows": [{"visible": "yes"}]}
    assert state["item_identity"] == {"/rows": ["row-1"]}
    assert state["writable_scopes"] == []
    assert not any(
        value in str(state)
        for value in (
            "hidden-value",
            "private-default",
            "public-default",
            "calculation",
            '"private"',
        )
    )
    assert state["field_metadata"][0].validation_schema["items"]["required"] == []
