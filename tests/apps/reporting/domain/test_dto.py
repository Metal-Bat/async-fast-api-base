"""Tests for report response DTO boundaries."""

from apps.reporting.domain.dto import ReportDetailDTO, ReportDTO


def test_report_list_keeps_operational_metadata_in_detail_only() -> None:
    detail_only = {
        "checksum_sha256",
        "content_type",
        "row_count",
        "exported_row_count",
        "error_code",
        "error_message",
        "download_count",
        "last_downloaded_at",
    }
    assert detail_only.isdisjoint(ReportDTO.model_fields)
    assert detail_only <= ReportDetailDTO.model_fields.keys()
