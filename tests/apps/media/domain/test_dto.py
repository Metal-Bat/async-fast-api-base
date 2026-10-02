"""Tests for media domain DTOs."""

from uuid import uuid7

from apps.media.domain.dto import UserUploadDTO
from apps.media.domain.entity import UserUploadEntity


def test_upload_dto_exposes_only_ref_id() -> None:
    entity = UserUploadEntity(
        id=uuid7(),
        user_id=uuid7(),
        kind="file",
        object_key="key",
        original_filename="file.txt",
        content_type="text/plain",
        size_bytes=1,
        sha256="0" * 64,
    )
    assert set(UserUploadDTO.model_validate(entity).model_dump()) == {"ref_id"}

    from_mapping = UserUploadDTO.model_validate({"id": uuid7(), "version": 2})
    assert from_mapping.ref_id
