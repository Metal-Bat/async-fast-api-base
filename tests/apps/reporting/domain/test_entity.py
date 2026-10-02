"""Tests for report domain history metadata."""

from core.history import history_tables


def test_report_table_has_field_history_with_password_redaction() -> None:
    table = history_tables()["report"]
    assert "FROM_STATUS" in table.c
    assert "TO_STORAGE_KEY" in table.c
    assert "TO_ZIP_PASSWORD" in table.c
