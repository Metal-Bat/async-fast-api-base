"""Tests for task domain entity history metadata."""

from core.history import history_tables


def test_mutable_schedule_entity_registers_field_history() -> None:
    assert "FROM_ENABLED" in history_tables()["periodic_task"].c
