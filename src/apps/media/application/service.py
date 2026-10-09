import asyncio
import hashlib
import io
import json
import zipfile
from collections.abc import AsyncIterator
from pathlib import PurePath
from typing import Literal, Protocol
from uuid import UUID, uuid7

import structlog
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.media.domain.entity import UserUploadEntity
from apps.users.domain.entity import UserEntity
from core.ref_id import open_ref_id
from core.settings import settings
from utils.exceptions import (
    InvalidFileException,
    InvalidImageException,
    NotFoundException,
    UploadRateLimitException,
    UploadTooLargeException,
)
from utils.s3 import delete_object, get_object, object_info, put_object, stream_object

logger = structlog.get_logger(__name__)


class UploadAccessPolicy(Protocol):
    """Code-owned extension seam for future relationship-based BPMS access."""

    async def can_read(self, upload: UserUploadEntity, actor: UserEntity) -> bool: ...


class OwnerOnlyUploadAccess:
    async def can_read(self, upload: UserUploadEntity, actor: UserEntity) -> bool:
        return upload.user_id == actor.id


def safe_filename(value: str | None) -> str:
    """Keep one bounded basename without response-header control characters."""
    name = PurePath((value or "upload").replace("\\", "/")).name
    safe = "".join(
        char for char in name if char >= " " and char != "\x7f" and char not in {'"', ":", ";"}
    )
    return safe[:255] or "upload"


def _validated_file_type(data: bytes, declared: str | None) -> str:
    content_type = (declared or "").partition(";")[0].strip().lower()
    if content_type == "application/pdf" and data.startswith(b"%PDF-"):
        return content_type
    if content_type in {"text/plain", "text/csv"} and b"\x00" not in data:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            return content_type
    if content_type == "application/json":
        try:
            json.loads(data)
        except UnicodeDecodeError, json.JSONDecodeError:
            pass
        else:
            return content_type
    if content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
                if {"[Content_Types].xml", "xl/workbook.xml"} <= names and all(
                    member.file_size <= settings.MAX_UPLOAD_BYTES
                    and member.compress_size > 0
                    and member.file_size <= member.compress_size * 100
                    for member in archive.infolist()
                ):
                    return content_type
        except zipfile.BadZipFile:
            pass
    raise InvalidFileException("The uploaded content is not a supported file")


async def enforce_upload_limit(user_id: UUID) -> None:
    """Atomically limit each user to the configured number of uploads per minute."""
    cache = Redis.from_url(str(settings.CACHE_DSN), decode_responses=True)
    key = f"rate-limit:upload:{user_id}"
    script = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
    return current
    """
    try:
        count = await cache.eval(script, 1, key, 60)
        if int(count) > settings.USER_UPLOADS_PER_MINUTE:
            raise UploadRateLimitException("Upload limit exceeded")
    finally:
        await cache.aclose()


async def _read_limited(upload: UploadFile) -> bytes:
    data = await upload.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise UploadTooLargeException("Upload exceeds the configured size limit")
    return data


def _to_webp(data: bytes) -> tuple[bytes, int, int]:
    try:
        with Image.open(io.BytesIO(data)) as source:
            width, height = source.size
            if width * height > settings.MAX_IMAGE_PIXELS:
                raise InvalidImageException("The uploaded image dimensions are too large")
            source.load()
            source = ImageOps.exif_transpose(source)
            width, height = source.size
            if width * height > settings.MAX_IMAGE_PIXELS:
                raise InvalidImageException("The uploaded image dimensions are too large")
            converted = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            output = io.BytesIO()
            # RE-ENCODING PIXELS WITHOUT EXIF, ICC, COMMENTS, OR XMP STRIPS UNTRUSTED METADATA.
            converted.save(output, format="WEBP", quality=82, method=6, optimize=True)
            return output.getvalue(), width, height
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageException("The uploaded content is not a valid image") from exc


class UserUploadService:
    """Store and retrieve authenticated user uploads."""

    def __init__(
        self, session: AsyncSession, access_policy: UploadAccessPolicy | None = None
    ) -> None:
        self.session = session
        self.access_policy = access_policy or OwnerOnlyUploadAccess()

    async def upload_file(self, user_id: UUID, upload: UploadFile) -> UserUploadEntity:
        """Validate the size, persist a private file, and return its metadata entity."""
        await enforce_upload_limit(user_id)
        data = await _read_limited(upload)
        object_key = f"user/{user_id}/file/{uuid7()}"
        content_type = _validated_file_type(data, upload.content_type)
        return await self._store(user_id, upload, "file", object_key, data, content_type)

    async def upload_image(self, user_id: UUID, upload: UploadFile) -> UserUploadEntity:
        """Validate an image, convert it to WebP off-loop, and persist it privately."""
        await enforce_upload_limit(user_id)
        original = await _read_limited(upload)
        data, width, height = await asyncio.to_thread(_to_webp, original)
        object_key = f"user/{user_id}/image/{uuid7()}.webp"
        return await self._store(
            user_id, upload, "image", object_key, data, "image/webp", width, height
        )

    async def _store(
        self,
        user_id: UUID,
        upload: UploadFile,
        kind: str,
        object_key: str,
        data: bytes,
        content_type: str,
        width: int | None = None,
        height: int | None = None,
    ) -> UserUploadEntity:
        await put_object(object_key, data, content_type)
        entity = UserUploadEntity(
            user_id=user_id,
            kind=kind,
            object_key=object_key,
            original_filename=safe_filename(upload.filename),
            content_type=content_type,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            width=width,
            height=height,
        )
        self.session.add(entity)
        try:
            await self.session.commit()
            await self.session.refresh(entity)
        except BaseException:
            try:
                await self.session.rollback()
            except Exception as exc:  # noqa: BLE001 - preserve the persistence failure
                logger.error("upload.rollback_failed", error_type=type(exc).__name__)
            try:
                await delete_object(object_key)
            except Exception as exc:  # noqa: BLE001 - orphan cleanup remains observable
                logger.error(
                    "upload.orphan_cleanup_failed",
                    object_key=object_key,
                    error_type=type(exc).__name__,
                )
            raise
        return entity

    async def download(self, upload: UserUploadEntity) -> bytes:
        """Return stored bytes only after their SHA-256 digest matches the upload."""
        data = await get_object(upload.object_key)
        if hashlib.sha256(data).hexdigest() != upload.sha256:
            raise NotFoundException("Upload not found")
        return data

    async def get_for_download(
        self, ref_id: str, kind: Literal["file", "image"], actor: UserEntity
    ) -> UserUploadEntity:
        """Resolve an upload only when trusted policy grants the authenticated actor access."""
        upload_id, expected_version = open_ref_id(ref_id)
        upload = await self.session.get(UserUploadEntity, upload_id)
        if (
            upload is None
            or upload.version != expected_version
            or upload.kind != kind
            or upload.deleted_at is not None
            or not await self.access_policy.can_read(upload, actor)
        ):
            raise NotFoundException("Upload not found")
        return upload

    async def stream(self, upload: UserUploadEntity) -> AsyncIterator[bytes]:
        """Preflight immutable object metadata, then return a bounded-memory stream."""
        info = await object_info(upload.object_key)
        if (
            info.size != upload.size_bytes
            or info.content_type != upload.content_type
            or info.metadata.get("sha256") != upload.sha256
        ):
            raise NotFoundException("Upload not found")
        return stream_object(upload.object_key)
