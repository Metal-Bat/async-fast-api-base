"""Repair projections preserve validator codes and never echo private diagnostics."""

from apps.designer.application.readiness import repair_issue
from main import app


def test_readiness_query_preserves_explicit_client_release_pin():
    from apps.designer.domain.readiness import DependencyReadinessQuery

    query = DependencyReadinessQuery(
        workflow_version_ref_id="current-workflow", client_release_ref_id="exact-client"
    )
    assert query.client_release_ref_id == "exact-client"


def test_existing_codes_select_bounded_owning_repairs():
    issue = repair_issue(
        {
            "pointer": "/steps/2/config/connection_ref",
            "code": "connection.unavailable",
            "actual_schema": {"private": "value"},
        },
        "review",
    )
    assert issue.repair_key == "connections"
    assert issue.node_key == "review"
    assert "private" not in issue.model_dump_json()
    assert issue.code == "connection.unavailable"
    assert (
        repair_issue(
            {"pointer": "/bindings/0", "code": "binding.type.incompatible"}, None
        ).repair_key
        == "workflow_versions"
    )


def test_readiness_http_seam_requires_authentication():
    operation = app.openapi()["paths"]["/api/v1/designer/dependency-readiness"]["post"]
    assert operation["security"]
    assert "Cache-Control" in operation["responses"]["200"]["headers"]
