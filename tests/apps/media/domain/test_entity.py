"""Tests for media domain entity history metadata."""

from apps.media.domain.entity import UserUploadHistoryTable


def test_upload_history_has_from_and_to_columns() -> None:
    assert "FROM_OBJECT_KEY" in UserUploadHistoryTable.c
    assert "TO_OBJECT_KEY" in UserUploadHistoryTable.c
