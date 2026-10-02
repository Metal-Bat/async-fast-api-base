"""HTTP contract for request types and business-request drafts."""

from main import app


def test_request_routes_follow_resource_and_action_contract() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert "post" in paths["/api/v1/request-types/search"]
    assert "get" in paths["/api/v1/request-types/{ref_id}"]
    assert "post" in paths["/api/v1/request-types/{ref_id}/history"]
    assert "post" in paths["/api/v1/request-types/report"]
    assert "post" in paths["/api/v1/request-types"]
    assert "put" in paths["/api/v1/request-types/{ref_id}"]
    assert "delete" in paths["/api/v1/request-types/{ref_id}"]

    assert "post" in paths["/api/v1/business-requests/search"]
    assert "get" in paths["/api/v1/business-requests/{ref_id}"]
    assert "post" in paths["/api/v1/business-requests/report"]
    assert "post" in paths["/api/v1/business-requests"]
    assert "put" in paths["/api/v1/business-requests/{ref_id}"]
    assert "post" in paths["/api/v1/business-requests/{ref_id}/submit"]
    assert "post" in paths["/api/v1/business-requests/{ref_id}/cancel"]
    assert "get" in paths["/api/v1/business-requests/{ref_id}/attachments"]
    assert "post" in paths["/api/v1/business-requests/{ref_id}/attachments"]
    assert "put" in paths["/api/v1/business-requests/{ref_id}/attachments"]
    member = "/api/v1/business-requests/{ref_id}/attachments/{attachment_ref_id}"
    assert {"put", "delete"} <= set(paths[member])
    assert "get" in paths[member + "/content"]


def test_request_wire_fields_are_snake_case() -> None:
    schema = app.openapi()["components"]["schemas"]
    assert {"request_type_ref_id", "priority", "data"} <= set(
        schema["BusinessRequestCreateDTO"]["properties"]
    )
    assert {"workflow_ref_id", "form_ref_id", "default_priority"} <= set(
        schema["RequestTypeCreateDTO"]["properties"]
    )
    assert {"field_path", "upload_ref_id", "caption", "contributing_group_ref_id"} <= set(
        schema["AttachmentAddDTO"]["properties"]
    )
