"""Tests for report route registration and public schemas."""

from apps.reporting.domain.dto import ReportDetailDTO, ReportDTO


def test_reporting_routes_are_registered_without_exposing_s3_keys() -> None:
    from main import app

    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/admin/users/report"]
    assert "post" in paths["/api/v1/reports/search"]
    assert "get" in paths["/api/v1/reports/{ref_id}"]
    assert "get" in paths["/api/v1/reports/{ref_id}/download"]
    assert "post" in paths["/api/v1/reports/{ref_id}/history"]
    assert "delete" in paths["/api/v1/reports/{ref_id}"]
    assert "storage_key" not in ReportDTO.model_fields
    assert "storage_key" not in ReportDetailDTO.model_fields
