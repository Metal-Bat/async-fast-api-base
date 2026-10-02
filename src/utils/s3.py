from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import aioboto3

from core.settings import settings


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    """Object size, content type, and stored integrity metadata."""

    size: int
    content_type: str
    metadata: dict[str, str]


@asynccontextmanager
async def s3_client() -> AsyncGenerator[Any]:
    """Yield an asynchronously managed S3 client configured for MinIO."""
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    ) as client:
        yield client


async def ensure_bucket() -> None:
    """Create the configured bucket when it does not exist."""
    async with s3_client() as client:
        try:
            await client.head_bucket(Bucket=settings.S3_BUCKET)
        except client.exceptions.ClientError:
            await client.create_bucket(Bucket=settings.S3_BUCKET)


async def put_object(key: str, body: bytes, content_type: str) -> None:
    """Upload one private object."""
    async with s3_client() as client:
        await client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
            ACL="private",
            Metadata={"sha256": sha256(body).hexdigest()},
        )


async def object_info(key: str) -> ObjectInfo:
    """Read trusted object metadata before opening a response stream."""
    async with s3_client() as client:
        response = await client.head_object(Bucket=settings.S3_BUCKET, Key=key)
        return ObjectInfo(
            size=int(response["ContentLength"]),
            content_type=str(response.get("ContentType", "application/octet-stream")),
            metadata={str(k): str(v) for k, v in response.get("Metadata", {}).items()},
        )


async def put_file(key: str, path: Path, content_type: str) -> None:
    """Upload a private file without buffering the complete artifact in memory."""
    async with s3_client() as client:
        await client.upload_file(
            str(path),
            settings.S3_BUCKET,
            key,
            ExtraArgs={"ContentType": content_type, "ACL": "private"},
        )


async def get_object(key: str) -> bytes:
    """Download one object fully and close its response stream."""
    async with s3_client() as client:
        response = await client.get_object(Bucket=settings.S3_BUCKET, Key=key)
        stream = response["Body"]
        async with stream:
            data = await stream.read()
            if not isinstance(data, bytes):
                raise TypeError("S3 response body must return bytes")
            return data


async def stream_object(key: str, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
    """Stream an object without buffering the complete download in memory."""
    async with s3_client() as client:
        response = await client.get_object(Bucket=settings.S3_BUCKET, Key=key)
        stream = response["Body"]
        async with stream:
            while chunk := await stream.read(chunk_size):
                if not isinstance(chunk, bytes):
                    raise TypeError("S3 response body must return bytes")
                yield chunk


async def delete_object(key: str) -> None:
    """Delete one object from the configured bucket."""
    async with s3_client() as client:
        await client.delete_object(Bucket=settings.S3_BUCKET, Key=key)
