"""Tests for user domain entity history metadata."""

from core.history import history_tables


def test_mutable_user_admin_entities_register_field_history() -> None:
    tables = history_tables()
    assert {"permission", "role", "user"} <= tables.keys()
    assert "TO_DESCRIPTION" in tables["permission"].c
    assert "TO_NAME" in tables["role"].c
