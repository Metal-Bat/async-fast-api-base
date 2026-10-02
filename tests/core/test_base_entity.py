"""Tests for shared database entity conventions."""

from sqlmodel import SQLModel

from apps.media.domain import entity as media_entities  # noqa: F401
from apps.tasks.domain import entity as task_entities  # noqa: F401
from apps.users.domain import auth_entity as auth_entities  # noqa: F401
from apps.users.domain import entity as user_entities  # noqa: F401


def test_database_identifiers_defaults_and_comments_follow_schema_conventions() -> None:
    """Database metadata uses uppercase names and PostgreSQL-generated UUIDv7 keys."""
    for table in SQLModel.metadata.sorted_tables:
        assert table.name == table.name.upper()
        for column in table.columns:
            assert column.comment is None or column.comment == column.comment.upper()
        if "ID" in table.c:
            default = table.c.ID.server_default
            assert default is not None
            assert str(getattr(default, "arg", None)) == "uuidv7()"
