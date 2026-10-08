"""Workspace persistence is bounded and separate from executable GraphSnapshot."""

import pytest
from pydantic import ValidationError

from apps.workflows.domain import workspace
from main import app


def test_workspace_accepts_incomplete_graph_but_bounds_layout():
    value = workspace.WorkspaceDocument.model_validate(
        {"graph": {"steps": [{"key": "half"}]}, "positions": {"half": {"x": 12, "y": 30}}}
    )
    assert value.graph["steps"][0]["key"] == "half"
    with pytest.raises(ValidationError):
        workspace.WorkspaceDocument.model_validate({"viewport": {"x": 0, "y": 0, "zoom": 0}})


def test_workspace_routes_require_author_and_expose_revision():
    schema = app.openapi()
    for method, suffix in [
        ("get", "workspace"),
        ("put", "workspace"),
        ("post", "workspace/promote"),
    ]:
        operation = schema["paths"]["/api/v1/workflow-versions/{ref_id}/" + suffix][method]
        assert operation["security"]
        assert (
            operation["responses"]["200"]["headers"]["Cache-Control"]["schema"]["const"]
            == "private, no-store"
        )
    assert (
        "workspace_ref_id" in schema["components"]["schemas"]["WorkflowWorkspaceDTO"]["properties"]
    )
