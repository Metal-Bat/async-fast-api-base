"""Restore plans bind current definitions and reject ambiguous or oversized commands."""

import pytest
from pydantic import ValidationError


def test_restore_commands_are_bounded_and_explicit():
    from apps.workflows.domain.defaults import RestorePreviewInput

    data = RestorePreviewInput(source_ref_id="published", mode="successor")
    assert data.bindings == {} and data.workspace_ref_id is None
    with pytest.raises(ValidationError):
        RestorePreviewInput.model_validate(
            {"source_ref_id": "published", "mode": "overwrite_published"}
        )
    with pytest.raises(ValidationError):
        RestorePreviewInput(
            source_ref_id="published", mode="successor", bindings={"unknown": "ref"}
        )


def test_restore_routes_expose_preview_and_apply_without_publishing():
    from main import app

    paths = app.openapi()["paths"]
    for action in ("default-preview", "default-apply", "layout-reset"):
        path = f"/api/v1/workflow-versions/{{ref_id}}/{action}"
        assert "post" in paths[path]
        assert paths[path]["post"]["security"]


def test_restore_operations_and_nested_contracts_are_localized():
    from main import app
    from utils.localized_docs import localized_openapi

    english = localized_openapi(app, "en")
    persian = localized_openapi(app, "fa")
    for action in ("default-preview", "default-apply", "layout-reset"):
        path = f"/api/v1/workflow-versions/{{ref_id}}/{action}"
        for field in ("summary", "description"):
            assert english["paths"][path]["post"][field] != persian["paths"][path]["post"][field]
    for schema in ("RestorePreviewInput", "RestoreApplyInput"):
        for name, prop in english["components"]["schemas"][schema]["properties"].items():
            if "description" in prop:
                assert (
                    prop["description"]
                    != persian["components"]["schemas"][schema]["properties"][name]["description"]
                )
