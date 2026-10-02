"""Tests for private S3 object operations."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest

from utils import s3


class Body:
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def __aenter__(self):
        # aiobotocore's StreamingBody enters its wrapped aiohttp response.
        return object()

    async def __aexit__(self, *_args):
        return None

    async def read(self, size: int = -1) -> bytes:
        if not self.data:
            return b""
        if size < 0:
            chunk, self.data = self.data, b""
        else:
            chunk, self.data = self.data[:size], self.data[size:]
        return chunk


class Client:
    class exceptions:
        class ClientError(Exception):
            pass

    def __init__(self, missing: bool = False) -> None:
        self.missing = missing
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def head_bucket(self, **kwargs):
        if self.missing:
            raise self.exceptions.ClientError()
        self.calls.append(("head", kwargs))

    async def create_bucket(self, **kwargs):
        self.calls.append(("create", kwargs))

    async def put_object(self, **kwargs):
        self.calls.append(("put", kwargs))

    async def upload_file(self, *args, **kwargs):
        self.calls.append(("upload", {"args": args, **kwargs}))

    async def get_object(self, **kwargs):
        self.calls.append(("get", kwargs))
        return {"Body": Body(b"abcdef")}

    async def head_object(self, **kwargs):
        self.calls.append(("object-head", kwargs))
        return {
            "ContentLength": 6,
            "ContentType": "text/plain",
            "Metadata": {"sha256": "digest"},
        }

    async def delete_object(self, **kwargs):
        self.calls.append(("delete", kwargs))


def install_client(monkeypatch, client: Client) -> None:
    @asynccontextmanager
    async def fake_client() -> AsyncGenerator[Client]:
        yield client

    monkeypatch.setattr(s3, "s3_client", fake_client)


@pytest.mark.anyio
async def test_s3_object_lifecycle(monkeypatch) -> None:
    client = Client()
    install_client(monkeypatch, client)
    await s3.ensure_bucket()
    await s3.put_object("key", b"body", "text/plain")
    info = await s3.object_info("key")
    assert info.size == 6 and info.metadata == {"sha256": "digest"}
    assert await s3.get_object("key") == b"abcdef"
    assert [part async for part in s3.stream_object("key", 2)] == [b"ab", b"cd", b"ef"]
    await s3.delete_object("key")
    assert {name for name, _ in client.calls} == {
        "head",
        "put",
        "object-head",
        "get",
        "delete",
    }


@pytest.mark.anyio
async def test_missing_bucket_is_created(monkeypatch) -> None:
    client = Client(missing=True)
    install_client(monkeypatch, client)
    await s3.ensure_bucket()
    assert client.calls[0][0] == "create"


@pytest.mark.anyio
async def test_uploads_are_explicitly_private(tmp_path, monkeypatch) -> None:
    client = Client()
    install_client(monkeypatch, client)
    source = tmp_path / "report.zip"
    source.write_bytes(b"zip")

    await s3.put_object("one", b"body", "application/zip")
    await s3.put_file("two", source, "application/zip")

    put = next(values for name, values in client.calls if name == "put")
    upload = next(values for name, values in client.calls if name == "upload")
    assert put["ACL"] == "private"
    metadata = put["Metadata"]
    assert isinstance(metadata, dict)
    assert metadata["sha256"]
    upload_args = cast(dict[str, Any], upload["ExtraArgs"])
    assert upload_args["ACL"] == "private"
