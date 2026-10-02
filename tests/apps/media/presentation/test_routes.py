"""Tests for media upload and download routes."""

import hashlib
import io
from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from fastapi import FastAPI, Request, UploadFile
from httpx import ASGITransport, AsyncClient
from starlette.middleware.cors import CORSMiddleware

from apps.media.application.service import UserUploadService
from apps.media.domain.entity import UserUploadEntity
from apps.media.presentation.routes import (
    download_file,
    download_image,
    get_upload_service,
    router,
    upload_file,
    upload_image,
)
from apps.users.domain.entity import UserEntity
from core.deps import get_current_user
from core.ref_id import create_ref_id, open_ref_id
from main import CORS_EXPOSE_HEADERS
from utils.exception_handlers import configure_exception_handlers
from utils.exceptions import NotFoundException, ValidationDetailsException
from utils.localized_docs import localized_openapi


def download_request(*values: str, cache_control: str | None = None) -> Request:
    headers = [(b"content-disposition", value.encode()) for value in values]
    if cache_control is not None:
        headers.append((b"cache-control", cache_control.encode()))
    return Request({"type": "http", "headers": headers})


@pytest.mark.anyio
async def test_media_download_routes_reject_unauthenticated_requests() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in ("files", "images"):
            response = await client.get(f"/api/v1/media/{path}/unknown")
            assert response.status_code == 401


@pytest.mark.anyio
async def test_media_uploads_and_downloads_require_the_owner() -> None:
    user = UserEntity(id=uuid7(), username="owner", hashed_password="hash")
    stored = UserUploadEntity(
        id=uuid7(),
        user_id=user.id,
        kind="file",
        object_key="key",
        original_filename="report.txt",
        content_type="text/plain",
        size_bytes=1,
        sha256="0" * 64,
    )
    service = Mock()
    service.upload_file = AsyncMock(return_value=stored)
    service.upload_image = AsyncMock(return_value=stored)
    service.get_for_download = AsyncMock(return_value=stored)
    service.stream = AsyncMock(return_value=iter_bytes(b"x"))
    request_upload = UploadFile(io.BytesIO(b"x"), filename="x")
    request = Request({"type": "http", "headers": []})

    assert open_ref_id((await upload_file(request, request_upload, user, service)).data.ref_id) == (
        stored.id,
        stored.version,
    )
    assert open_ref_id(
        (await upload_image(request, request_upload, user, service)).data.ref_id
    ) == (
        stored.id,
        stored.version,
    )
    ref_id = create_ref_id(stored.id, stored.version)
    response = await download_file(ref_id, user, service, download_request())
    assert response.media_type == "text/plain"
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''report.txt"
    assert response.headers["cache-control"] == "private, no-store"

    stored.kind = "image"
    image = await download_image(ref_id, user, service, download_request())
    assert image.media_type == "image/webp"
    assert "content-disposition" not in image.headers
    assert image.headers["cache-control"] == "private, no-store"
    assert service.get_for_download.await_args_list[0].args == (ref_id, "file", user)
    assert service.get_for_download.await_args_list[1].args == (ref_id, "image", user)


async def iter_bytes(value: bytes):
    yield value


@pytest.mark.anyio
@pytest.mark.parametrize("kind,download", [("file", download_file), ("image", download_image)])
async def test_corrupted_upload_is_not_returned(monkeypatch, kind, download) -> None:
    stored = UserUploadEntity(
        id=uuid7(),
        user_id=uuid7(),
        kind=kind,
        object_key="key",
        original_filename="upload.txt",
        content_type="text/plain",
        size_bytes=8,
        sha256=hashlib.sha256(b"original").hexdigest(),
    )
    service = UserUploadService(Mock())
    service.get_for_download = AsyncMock(return_value=stored)
    service.stream = AsyncMock(side_effect=NotFoundException("Upload not found"))
    user = UserEntity(id=stored.user_id, username="owner", hashed_password="hash")

    with pytest.raises(NotFoundException, match="Upload not found"):
        await download(create_ref_id(stored.id, stored.version), user, service, download_request())


@pytest.mark.anyio
async def test_private_media_disposition_is_bounded_and_uses_server_filenames() -> None:
    user = UserEntity(id=uuid7(), username="owner", hashed_password="hash")
    stored = UserUploadEntity(
        id=uuid7(),
        user_id=user.id,
        kind="file",
        object_key="key",
        original_filename="گزارش.txt\r\nX-Evil: yes",
        content_type="text/plain",
        size_bytes=1,
        sha256="0" * 64,
    )
    service = Mock()
    service.get_for_download = AsyncMock(return_value=stored)
    service.stream = AsyncMock(return_value=iter_bytes(b"x"))
    ref_id = create_ref_id(stored.id, stored.version)

    file = await download_file(
        ref_id, user, service, download_request("attachment", cache_control="public")
    )
    assert file.headers["content-disposition"].startswith("attachment; filename*=UTF-8''")
    assert "%D8%" in file.headers["content-disposition"]
    assert "\r" not in file.headers["content-disposition"]
    assert "\n" not in file.headers["content-disposition"]
    assert file.headers["cache-control"] == "private, no-store"
    assert file.headers["x-content-type-options"] == "nosniff"

    stored.kind = "image"
    stored.original_filename = "پرتره.png"
    for mode in ("inline", "attachment"):
        response = await download_image(ref_id, user, service, download_request(mode))
        assert response.headers["content-disposition"].startswith(f"{mode}; filename*=UTF-8''")
        assert response.headers["content-disposition"].endswith(".webp")
        assert response.headers["cache-control"] == "private, no-store"
        assert response.media_type == "image/webp"


@pytest.mark.anyio
async def test_private_media_rejects_unsafe_or_duplicate_disposition_before_streaming() -> None:
    user = UserEntity(id=uuid7(), username="owner", hashed_password="hash")
    stored = UserUploadEntity(
        id=uuid7(),
        user_id=user.id,
        kind="file",
        object_key="key",
        original_filename="report.txt",
        content_type="text/plain",
        size_bytes=1,
        sha256="0" * 64,
    )
    service = Mock()
    service.get_for_download = AsyncMock(return_value=stored)
    service.stream = AsyncMock(return_value=iter_bytes(b"x"))
    ref_id = create_ref_id(stored.id, stored.version)

    for request in (
        download_request("inline"),
        download_request('attachment; filename="forged.txt"'),
        download_request("attachment", "attachment"),
        download_request("attachment\r\nX-Evil: yes"),
        download_request(""),
    ):
        with pytest.raises(ValidationDetailsException):
            await download_file(ref_id, user, service, request)
    service.stream.assert_not_awaited()


@pytest.mark.anyio
async def test_media_http_contract_rejects_invalid_disposition_with_public_error() -> None:
    user = UserEntity(id=uuid7(), username="owner", hashed_password="hash")
    stored = UserUploadEntity(
        id=uuid7(),
        user_id=user.id,
        kind="image",
        object_key="key",
        original_filename="photo.png",
        content_type="image/webp",
        size_bytes=1,
        sha256="0" * 64,
    )
    service = Mock()
    service.get_for_download = AsyncMock(return_value=stored)
    service.stream = AsyncMock(return_value=iter_bytes(b"x"))
    app = FastAPI()
    configure_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_upload_service] = lambda: service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://client.example"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=CORS_EXPOSE_HEADERS,
    )
    ref_id = create_ref_id(stored.id, stored.version)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        preflight = await client.options(
            f"/api/v1/media/images/{ref_id}",
            headers={
                "Origin": "https://client.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Disposition, Authorization",
            },
        )
        valid = await client.get(
            f"/api/v1/media/images/{ref_id}",
            headers={
                "Origin": "https://client.example",
                "Content-Disposition": "attachment",
                "Cache-Control": "public",
            },
        )
        invalid = await client.get(
            f"/api/v1/media/images/{ref_id}",
            headers={"Content-Disposition": 'inline; filename="forged.webp"'},
        )
        duplicate = await client.get(
            f"/api/v1/media/images/{ref_id}",
            headers=[("Content-Disposition", "inline"), ("Content-Disposition", "attachment")],
        )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://client.example"
    assert "content-disposition" in preflight.headers["access-control-allow-headers"].lower()
    assert valid.status_code == 200
    assert valid.content == b"x"
    assert valid.headers["content-disposition"] == "attachment; filename*=UTF-8''photo.webp"
    assert valid.headers["cache-control"] == "private, no-store"
    assert valid.headers["access-control-allow-origin"] == "https://client.example"
    assert "Content-Disposition" in valid.headers["access-control-expose-headers"]
    assert "Cache-Control" in valid.headers["access-control-expose-headers"]
    assert invalid.status_code == duplicate.status_code == 422
    assert invalid.json()["code"] == duplicate.json()["code"] == 1002
    assert invalid.json()["data"]["issues"][0]["code"] == "media.disposition.invalid"
    assert duplicate.json()["data"]["issues"][0]["code"] == "media.disposition.duplicate"


def test_media_download_openapi_describes_private_binary_contract_in_both_languages() -> None:
    from main import app

    english = app.openapi()
    persian = localized_openapi(app, "fa")
    for kind in ("files", "images"):
        path = f"/api/v1/media/{kind}/{{ref_id}}"
        operation = english["paths"][path]["get"]
        localized = persian["paths"][path]["get"]
        inputs = [item for item in operation["parameters"] if item["in"] == "header"]
        assert sum(item["name"] == "Content-Disposition" for item in inputs) == 1
        assert all(item["name"] != "Cache-Control" for item in inputs)
        assert operation["security"] == [{"OAuth2PasswordBearer": []}]
        assert operation["description"] != localized["description"]
        assert operation["operationId"] == localized["operationId"]
        assert {"Content-Disposition", "Cache-Control", "X-Content-Type-Options"} <= set(
            operation["responses"]["200"]["headers"]
        )
    file_content = english["paths"]["/api/v1/media/files/{ref_id}"]["get"]["responses"]["200"][
        "content"
    ]
    image_content = english["paths"]["/api/v1/media/images/{ref_id}"]["get"]["responses"]["200"][
        "content"
    ]
    assert file_content["application/pdf"]["schema"] == {"type": "string", "format": "binary"}
    assert image_content == {"image/webp": {"schema": {"type": "string", "format": "binary"}}}
