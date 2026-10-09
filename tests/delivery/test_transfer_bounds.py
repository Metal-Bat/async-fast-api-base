"""Late private storage failures must be discovered before response headers commit."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest

from apps.reporting.application.service import ReportService
from apps.reporting.domain.entity import ReportEntity, ReportStatus
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException
from utils.s3 import ObjectInfo


@pytest.mark.anyio
async def test_report_integrity_preflight_does_not_record_a_missing_download(monkeypatch):
    session = Mock(commit=AsyncMock())
    report = ReportEntity(
        owner_id=uuid7(),
        definition_key="users",
        definition_version=1,
        max_rows=100,
        chunk_size=10,
        parallelism=1,
        priority=1,
        task_id=str(uuid7()),
        status=ReportStatus.READY,
        storage_key="synthetic/private.zip",
        file_size=10,
        checksum_sha256="a" * 64,
        content_type="application/zip",
        expires_at=get_datetime_utc() + timedelta(days=1),
    )
    info = AsyncMock(return_value=ObjectInfo(size=11, content_type="application/zip", metadata={}))
    monkeypatch.setattr("apps.reporting.application.service.object_info", info, raising=False)
    with pytest.raises(NotFoundException):
        await ReportService(session).download(report)
    session.commit.assert_not_awaited()
    assert report.download_count == 0


def test_safe_filename_removes_every_header_control_character():
    from apps.media.application.service import safe_filename

    assert safe_filename("../../safe\x7f\r\n.txt") == "safe.txt"


def test_report_metadata_operations_document_private_headers():
    from main import app

    paths = app.openapi()["paths"]
    for route, method in (
        ("/reports/search", "post"),
        ("/reports/{ref_id}", "get"),
        ("/reports/{ref_id}/history", "post"),
    ):
        headers = paths["/api/v1" + route][method]["responses"]["200"].get("headers", {})
        assert "Cache-Control" in headers


def test_archive_bound_is_checked_before_private_upload(tmp_path, monkeypatch):
    from apps.reporting.tasks import ReportTooLargeError, validate_archive_size
    from core.settings import settings

    monkeypatch.setattr(settings, "MAX_REPORT_ARCHIVE_BYTES", 10)
    archive = tmp_path / "synthetic.zip"
    archive.write_bytes(b"x" * 10)
    assert validate_archive_size(archive) == 10
    archive.write_bytes(b"x" * 11)
    with pytest.raises(ReportTooLargeError):
        validate_archive_size(archive)


def test_pixel_bound_is_checked_before_decoding_pixels(monkeypatch):
    from unittest.mock import MagicMock

    from apps.media.application.service import _to_webp
    from utils.exceptions import InvalidImageException

    source = MagicMock()
    source.size = (100_000, 100_000)
    source.__enter__.return_value = source
    monkeypatch.setattr("apps.media.application.service.Image.open", Mock(return_value=source))
    with pytest.raises(InvalidImageException):
        _to_webp(b"synthetic-header")
    source.load.assert_not_called()
