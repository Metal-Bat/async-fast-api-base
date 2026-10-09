"""Small synthetic assets go through private upload validation, persistence and storage."""

import hashlib
from io import BytesIO
from uuid import uuid5

from fastapi import UploadFile
from PIL import Image
from sqlmodel import func, select
from starlette.datastructures import Headers

from apps.media.application.service import UserUploadService, _to_webp
from apps.media.domain.entity import UserUploadEntity
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException


def _synthetic_assets() -> list[tuple[str, bytes, bytes, str]]:
    text = b"Synthetic application fixture; no real personal data or external effect.\n"
    with BytesIO() as output:
        Image.new("RGB", (8, 8), (80, 120, 200)).save(output, "PNG")
        png = output.getvalue()
    webp, _, _ = _to_webp(png)
    return [("file", text, text, "text/plain"), ("image", png, webp, "image/png")]


async def install_demo_assets(
    manifest: BootstrapManifest, *, check_only: bool = False
) -> dict[str, str]:
    """Upload commits stay separate from the atomic account/template transaction and are repairable."""
    result = {}
    owner_id = uuid5(manifest.installation_id, "user:requester")
    for kind, original, stored, content_type in _synthetic_assets():
        filename = f"demo-{manifest.installation_id.hex}-{kind}"
        async with SessionFactory() as session:
            owner = await session.get(UserEntity, owner_id)
            if owner is None or owner.deleted_at is not None or owner.is_superuser:
                raise VersionConflictException("Demo asset identity unavailable")
            if not check_only:
                await session.exec(select(func.pg_advisory_xact_lock(func.hashtext(filename))))
            rows = (
                await session.exec(
                    select(UserUploadEntity).where(
                        UserUploadEntity.user_id == owner_id,
                        UserUploadEntity.original_filename == filename,
                        UserUploadEntity.kind == kind,
                    )
                )
            ).all()
            service = UserUploadService(session)
            if rows:
                if (
                    len(rows) != 1
                    or rows[0].deleted_at is not None
                    or rows[0].sha256 != hashlib.sha256(stored).hexdigest()
                ):
                    raise VersionConflictException(
                        "Demo asset changed; refusing duplicate private uploads"
                    )
                row = rows[0]
                await service.stream(
                    row
                )  # Header integrity preflight; the stream is not opened here.
                if await service.download(row) != stored:
                    raise VersionConflictException("Demo asset integrity differs")
            else:
                if check_only:
                    raise VersionConflictException("Demo asset is missing")
                upload = UploadFile(
                    filename=filename,
                    file=BytesIO(original),
                    headers=Headers({"content-type": content_type}),
                )
                try:
                    row = (
                        await service.upload_file(owner_id, upload)
                        if kind == "file"
                        else await service.upload_image(owner_id, upload)
                    )
                finally:
                    await upload.close()
            result[kind] = create_ref_id(row.id, row.version)
    return result
