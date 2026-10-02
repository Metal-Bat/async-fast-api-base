"""Work-item state and HTTP contract."""

import pytest

from apps.work_items.domain.state import transition
from main import app


@pytest.mark.parametrize(
    ("source", "action", "target"),
    [
        ("OPEN", "claim", "CLAIMED"),
        ("OPEN", "cancel", "CANCELLED"),
        ("OPEN", "expire", "EXPIRED"),
        ("CLAIMED", "start", "IN_PROGRESS"),
        ("CLAIMED", "release", "OPEN"),
        ("CLAIMED", "complete", "COMPLETED"),
        ("IN_PROGRESS", "reject", "REJECTED"),
        ("IN_PROGRESS", "return", "RETURNED"),
    ],
)
def test_work_item_action_matrix(source: str, action: str, target: str) -> None:
    assert transition(source, action) == target  # ty:ignore[invalid-argument-type]


def test_terminal_work_item_rejects_lifecycle_actions() -> None:
    for status in ("COMPLETED", "REJECTED", "RETURNED", "CANCELLED", "EXPIRED"):
        with pytest.raises(ValueError, match="invalid"):
            transition(status, "claim")


def test_work_item_routes_expose_cartables_and_explicit_actions() -> None:
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/work-items/search"]
    assert "get" in paths["/api/v1/work-items/{ref_id}"]
    for action in (
        "claim",
        "release",
        "start",
        "save",
        "complete",
        "reject",
        "return",
        "forward",
        "cancel",
        "expire",
        "comment",
        "read",
        "pin",
        "archive",
        "watch",
    ):
        assert "post" in paths[f"/api/v1/work-items/{{ref_id}}/{action}"]
    assert {"get", "post", "put"} <= set(paths["/api/v1/work-items/{ref_id}/attachments"])
    member = "/api/v1/work-items/{ref_id}/attachments/{attachment_ref_id}"
    assert {"put", "delete"} <= set(paths[member])
    assert "get" in paths[member + "/content"]


def test_work_item_wire_fields_are_snake_case() -> None:
    schemas = app.openapi()["components"]["schemas"]
    assert {"cartable", "page", "size"} <= set(schemas["CartableQueryDTO"]["properties"])
    assert {"command_key", "outcome_key", "data"} <= set(
        schemas["WorkItemCompleteDTO"]["properties"]
    )
    assert {"user_ref_ids", "work_group_ref_ids", "reason"} <= set(
        schemas["WorkItemForwardDTO"]["properties"]
    )


def test_task_view_and_correction_openapi_contracts_are_typed_and_localized():
    from utils.localized_docs import localized_openapi

    english = app.openapi()
    persian = localized_openapi(app, "fa")
    view_path = "/api/v1/work-items/{ref_id}/view"
    feedback_path = "/api/v1/work-items/{ref_id}/feedback/{feedback_key}/resolve"
    assert (
        english["paths"][view_path]["get"]["operationId"]
        == persian["paths"][view_path]["get"]["operationId"]
    )
    assert "get" in english["paths"][view_path]
    assert "post" in english["paths"][feedback_path]
    props = english["components"]["schemas"]["WorkItemViewDTO"]["properties"]
    assert {
        "data",
        "before_data",
        "render_schema",
        "actions",
        "feedback",
        "autosave_conflict",
        "unsaved_navigation",
    } <= set(props)
    actions = english["components"]["schemas"]["TaskActionViewDTO"]["properties"]
    assert {"kind", "outcome_key", "required_scopes", "validation"} <= set(actions)
    assert "feedback" in english["components"]["schemas"]["WorkItemCompleteDTO"]["properties"]
