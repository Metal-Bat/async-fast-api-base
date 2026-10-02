"""Tests for public user domain DTOs."""

from datetime import UTC, datetime
from uuid import uuid7

from apps.users.domain.dto import UserDTO


def test_user_dto_creates_opaque_reference_and_serializes_snake_case() -> None:
    values = {
        "id": uuid7(),
        "version": 1,
        "username": "ada",
        "email": None,
        "created_at": datetime.now(UTC),
        "updated_at": None,
        "deleted_at": None,
        "first_name": None,
        "last_name": None,
        "is_superuser": False,
        "is_active": True,
    }
    user = UserDTO.model_validate(values)
    assert user.ref_id
    assert "ref_id" in user.model_dump(mode="json")
    assert "refId" not in user.model_dump(mode="json")
