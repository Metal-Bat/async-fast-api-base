"""Tests for authenticated media storage services."""

import hashlib
import io
import zipfile
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from PIL import Image

import apps.media.application.service as media
from apps.media.domain.entity import UserUploadEntity
from apps.users.domain.entity import UserEntity
from core.ref_id import create_ref_id
from utils.exceptions import (
    InvalidFileException,
    NotFoundException,
    UploadRateLimitException,
    UploadTooLargeException,
)


class Cache:
    def __init__(self, count: int) -> None:
        self.count = count
        self.closed = False

    async def eval(self, *_args):
        return self.count

    async def aclose(self):
        self.closed = True


@pytest.mark.anyio
async def test_upload_rate_limit_closes_cache(monkeypatch) -> None:
    cache = Cache(1)
    monkeypatch.setattr(media.Redis, "from_url", lambda *_a, **_kw: cache)
    await media.enforce_upload_limit(uuid7())
    assert cache.closed

    cache = Cache(media.settings.USER_UPLOADS_PER_MINUTE + 1)
    monkeypatch.setattr(media.Redis, "from_url", lambda *_a, **_kw: cache)
    with pytest.raises(UploadRateLimitException):
        await media.enforce_upload_limit(uuid7())
    assert cache.closed


@pytest.mark.anyio
async def test_read_limited_rejects_large_upload(monkeypatch) -> None:
    monkeypatch.setattr(media.settings, "MAX_UPLOAD_BYTES", 2)
    upload = Mock()
    upload.read = AsyncMock(return_value=b"abc")
    with pytest.raises(UploadTooLargeException):
        await media._read_limited(upload)


@pytest.mark.anyio
async def test_file_and_image_uploads_are_persisted(monkeypatch) -> None:
    monkeypatch.setattr(media, "enforce_upload_limit", AsyncMock())
    monkeypatch.setattr(media, "put_object", AsyncMock())

    async def run_inline(function, *args):
        return function(*args)

    monkeypatch.setattr(media.asyncio, "to_thread", run_inline)
    session = Mock()
    session.add = Mock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    service = media.UserUploadService(session)
    user_id = uuid7()

    file_upload = Mock(filename="../hello.txt\r\nX-Test: injected", content_type="text/plain")
    file_upload.read = AsyncMock(return_value=b"hello")
    file_entity = await service.upload_file(user_id, file_upload)
    assert file_entity.kind == "file"
    assert file_entity.object_key.startswith(f"user/{user_id}/file/")
    assert file_entity.size_bytes == 5
    assert file_entity.sha256 == hashlib.sha256(b"hello").hexdigest()
    assert file_entity.original_filename == "hello.txtX-Test injected"

    source = io.BytesIO()
    Image.new("RGB", (4, 3), "blue").save(source, format="PNG")
    image_upload = Mock(filename="photo.png", content_type="image/png")
    image_upload.read = AsyncMock(return_value=source.getvalue())
    image_entity = await service.upload_image(user_id, image_upload)
    assert image_entity.kind == "image"
    assert image_entity.content_type == "image/webp"
    assert (image_entity.width, image_entity.height) == (4, 3)
    stored_image = media._to_webp(source.getvalue())[0]
    assert image_entity.sha256 == hashlib.sha256(stored_image).hexdigest()
    assert session.commit.await_count == 2


@pytest.mark.anyio
async def test_download_returns_bytes_only_when_checksum_matches(monkeypatch) -> None:
    data = b"stored contents"
    get_object = AsyncMock(return_value=data)
    monkeypatch.setattr(media, "get_object", get_object)
    upload = Mock(object_key="private/key", sha256=hashlib.sha256(data).hexdigest())

    assert await media.UserUploadService(Mock()).download(upload) == data
    get_object.assert_awaited_once_with("private/key")


@pytest.mark.anyio
async def test_download_rejects_corrupted_bytes(monkeypatch) -> None:
    monkeypatch.setattr(media, "get_object", AsyncMock(return_value=b"corrupted"))
    upload = Mock(object_key="private/key", sha256=hashlib.sha256(b"original").hexdigest())

    with pytest.raises(NotFoundException, match="Upload not found"):
        await media.UserUploadService(Mock()).download(upload)


@pytest.mark.anyio
async def test_download_lookup_is_owner_only_and_hides_unauthorized_uploads() -> None:
    owner = UserEntity(id=uuid7(), username="owner", hashed_password="hash")
    outsider = UserEntity(id=uuid7(), username="outsider", hashed_password="hash")
    upload = Mock(id=uuid7(), version=1, user_id=owner.id, kind="file", deleted_at=None)
    session = Mock()
    session.get = AsyncMock(return_value=upload)
    service = media.UserUploadService(session)
    ref_id = create_ref_id(upload.id, upload.version)

    assert await service.get_for_download(ref_id, "file", owner) is upload
    with pytest.raises(NotFoundException, match="Upload not found"):
        await service.get_for_download(ref_id, "file", outsider)

    session.get.return_value = None
    with pytest.raises(NotFoundException, match="Upload not found"):
        await service.get_for_download(ref_id, "file", owner)


@pytest.mark.anyio
async def test_trusted_code_can_supply_an_explicit_access_policy() -> None:
    class ExplicitRelationshipPolicy:
        async def can_read(self, upload: UserUploadEntity, actor: UserEntity) -> bool:
            return upload.kind == "file" and actor.username == "participant"

    participant = UserEntity(id=uuid7(), username="participant", hashed_password="hash")
    upload = Mock(id=uuid7(), version=1, user_id=uuid7(), kind="file", deleted_at=None)
    session = Mock()
    session.get = AsyncMock(return_value=upload)
    service = media.UserUploadService(session, ExplicitRelationshipPolicy())

    assert (
        await service.get_for_download(
            create_ref_id(upload.id, upload.version), "file", participant
        )
        is upload
    )


@pytest.mark.anyio
async def test_file_upload_rejects_mismatched_or_active_content(monkeypatch) -> None:
    monkeypatch.setattr(media, "enforce_upload_limit", AsyncMock())
    service = media.UserUploadService(Mock())
    upload = Mock(filename="payload.html", content_type="text/html")
    upload.read = AsyncMock(return_value=b"<script>alert(1)</script>")

    with pytest.raises(InvalidFileException, match="supported file"):
        await service.upload_file(uuid7(), upload)


def test_spreadsheet_signature_requires_the_xlsx_container_structure() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", "<workbook/>")
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert media._validated_file_type(output.getvalue(), mime) == mime
    with pytest.raises(InvalidFileException):
        media._validated_file_type(b"PK fake", mime)


@pytest.mark.anyio
async def test_stream_requires_matching_trusted_object_metadata(monkeypatch) -> None:
    digest = hashlib.sha256(b"contents").hexdigest()
    upload = Mock(object_key="private/key", sha256=digest, size_bytes=8)
    object_info = AsyncMock(
        return_value=Mock(size=8, content_type="text/plain", metadata={"sha256": digest})
    )
    monkeypatch.setattr(
        media,
        "object_info",
        object_info,
        raising=False,
    )
    upload.content_type = "text/plain"
    stream = Mock()
    monkeypatch.setattr(media, "stream_object", Mock(return_value=stream), raising=False)
    assert await media.UserUploadService(Mock()).stream(upload) is stream

    object_info.return_value = Mock(
        size=8, content_type="text/plain", metadata={"sha256": "0" * 64}
    )
    with pytest.raises(NotFoundException, match="Upload not found"):
        await media.UserUploadService(Mock()).stream(upload)


@pytest.mark.anyio
async def test_failed_upload_persistence_removes_private_object(monkeypatch) -> None:
    monkeypatch.setattr(media, "enforce_upload_limit", AsyncMock())
    monkeypatch.setattr(media, "put_object", AsyncMock())
    delete_object = AsyncMock()
    monkeypatch.setattr(media, "delete_object", delete_object, raising=False)
    session = Mock()
    session.add = Mock()
    session.commit = AsyncMock(side_effect=RuntimeError("database unavailable"))
    session.rollback = AsyncMock()
    upload = Mock(filename="hello.txt", content_type="text/plain")
    upload.read = AsyncMock(return_value=b"hello")

    with pytest.raises(RuntimeError, match="database unavailable"):
        await media.UserUploadService(session).upload_file(uuid7(), upload)

    session.rollback.assert_awaited_once()
    delete_object.assert_awaited_once()
