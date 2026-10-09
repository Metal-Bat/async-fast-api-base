"""Private maximum-size uploads traverse the actual paired Node boundary and real storage."""

import asyncio
import os
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from sqlmodel import select

from apps.reporting.domain.entity import ReportEntity, ReportStatus
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from core.settings import settings
from tests.integration.test_frontend_journey import _prepare_journey
from utils.date_utils import get_datetime_utc
from utils.s3 import ensure_bucket, put_object

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_PRIVATE_TRANSFERS") != "1",
        reason="requires disposable paired transfer services",
    ),
]


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        assert isinstance(port, int)
        return port


@asynccontextmanager
async def _pair(log_directory: Path):
    peer = Path(
        os.getenv("TRANSFER_FRONTEND_ROOT", "/home/erfan/Project/js/async-fast-api-base-frontend")
    )
    if not (peer / "server/main.mjs").is_file():
        raise RuntimeError("Transfer verification requires the pinned peer session boundary")
    backend_port, boundary_port = _port(), _port()
    origin = f"http://127.0.0.1:{boundary_port}"
    environment = os.environ.copy()
    environment.update(
        BOUNDARY_UPSTREAM_ORIGIN=f"http://127.0.0.1:{backend_port}",
        BOUNDARY_BROWSER_ORIGIN=origin,
        BOUNDARY_PORT=str(boundary_port),
        BOUNDARY_CLIENT_MODE="public",
        NODE_ENV="development",
    )
    environment.pop("BOUNDARY_CLIENT_SECRET", None)
    processes = []
    logs = [(log_directory / name).open("w") for name in ("backend.log", "boundary.log")]
    for name in ("backend.log", "boundary.log"):
        os.chmod(log_directory / name, 0o600)
    try:
        processes.append(
            await asyncio.to_thread(
                subprocess.Popen,
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(backend_port),
                    "--log-level",
                    "error",
                ],
                env=environment,
                stdout=logs[0],
                stderr=logs[0],
            )
        )
        processes.append(
            await asyncio.to_thread(
                subprocess.Popen,
                ["mise", "exec", "--", "node", str(peer / "server/main.mjs")],
                cwd=peer,
                env=environment,
                stdout=logs[1],
                stderr=logs[1],
            )
        )
        async with httpx.AsyncClient(timeout=2) as client:
            for attempt in range(150):
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError(
                        f"Owned paired transfer process exited; private logs at {log_directory}"
                    )
                try:
                    response = await client.get(origin + "/session/status")
                    upstream = await client.get(f"http://127.0.0.1:{backend_port}/health/live")
                    if response.status_code == 200 and upstream.status_code < 500:
                        break
                except httpx.HTTPError:
                    pass
                if attempt == 149:
                    raise RuntimeError("Owned paired transfer processes did not become ready")
                await asyncio.sleep(0.1)
        yield origin
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait, timeout=5)
        for log in logs:
            log.close()


@pytest.mark.anyio
async def test_maximum_private_transfer_crosses_actual_session_boundary(tmp_path):
    assert settings.MAX_UPLOAD_BYTES == 10 * 1024 * 1024
    await ensure_bucket()
    users, password, _ = await _prepare_journey()
    try:
        async with (
            _pair(tmp_path) as origin,
            httpx.AsyncClient(base_url=origin, timeout=20) as client,
        ):
            login = await client.post(
                "/session/login",
                headers={"Origin": origin},
                json={"username": users[0], "password": password},
            )
            assert login.status_code == 200, "Paired boundary login failed"
            assert "access_token" not in login.json()
            headers = {"Origin": origin, "X-CSRF-Token": login.json()["csrfToken"]}
            body = b"x" * settings.MAX_UPLOAD_BYTES
            upload = await client.post(
                "/api/v1/media/files",
                headers=headers,
                files={"upload": ("synthetic-maximum.txt", body, "text/plain")},
            )
            assert upload.status_code == 201, upload.text
            assert upload.headers["cache-control"] == "private, no-store"
            reference = upload.json()["data"]["ref_id"]
            downloaded = await client.get("/api/v1/media/files/" + reference)
            assert downloaded.status_code == 200 and downloaded.content == body
            assert downloaded.headers["cache-control"] == "private, no-store"
            assert downloaded.headers["x-content-type-options"] == "nosniff"
            assert "synthetic-maximum.txt" in downloaded.headers["content-disposition"]
            oversize = await client.post(
                "/api/v1/media/files",
                headers=headers,
                files={"upload": ("synthetic-oversize.txt", body + b"x", "text/plain")},
            )
            assert oversize.status_code == 413
            # The boundary rejects declared oversized bodies before upload. Send only headers
            # so an early response cannot race a client still writing an invalid 11 MiB body.
            declared = client.build_request(
                "POST",
                "/api/v1/media/files",
                headers=headers | {"Content-Length": str(11 * 1024 * 1024 + 1)},
            )
            address = urlsplit(origin)
            reader, writer = await asyncio.open_connection(address.hostname, address.port)
            try:
                request_headers = b"\r\n".join(
                    name + b": " + value for name, value in declared.headers.raw
                )
                writer.write(
                    b"POST /api/v1/media/files HTTP/1.1\r\n" + request_headers + b"\r\n\r\n"
                )
                await writer.drain()
                status = await asyncio.wait_for(reader.readline(), timeout=5)
                assert status.split()[1] == b"413"
            finally:
                writer.close()
                await writer.wait_closed()
            assert (await client.get("/session/status")).json()["authenticated"] is True
            # A synthetic artifact tests transport capacity; actual worker generation has
            # its separate mandatory test and is not inferred from this seeded row.
            archive = b"PK" + b"x" * (settings.MAX_REPORT_ARCHIVE_BYTES - 2)
            async with SessionFactory() as session:
                owner = (
                    await session.exec(select(UserEntity).where(UserEntity.username == users[0]))
                ).one()
                report = ReportEntity(
                    owner_id=owner.id,
                    definition_key="users",
                    definition_version=1,
                    max_rows=1,
                    chunk_size=1,
                    parallelism=1,
                    priority=1,
                    task_id="synthetic-transfer-capacity",
                    status=ReportStatus.READY,
                    file_size=len(archive),
                    checksum_sha256=sha256(archive).hexdigest(),
                    content_type="application/zip",
                    expires_at=get_datetime_utc() + timedelta(days=1),
                )
                report.storage_key = f"reports/{report.id}/synthetic-capacity.zip"
                await put_object(report.storage_key, archive, "application/zip")
                session.add(report)
                await session.commit()
                await session.refresh(report)
                report_ref = create_ref_id(report.id, report.version)
            report_download = await client.get(f"/api/v1/reports/{report_ref}/download")
            assert report_download.status_code == 200 and report_download.content == archive
            assert report_download.headers["cache-control"] == "private, no-store"
            assert report_download.headers["x-content-type-options"] == "nosniff"
            async with client.stream("GET", "/api/v1/media/files/" + reference) as stream:
                assert stream.status_code == 200
                assert await anext(stream.aiter_bytes())
            assert (await client.get("/session/status")).json()["authenticated"] is True
            async with httpx.AsyncClient(base_url=origin, timeout=20) as outsider:
                assert (
                    await outsider.post(
                        "/session/login",
                        headers={"Origin": origin},
                        json={"username": users[2], "password": password},
                    )
                ).status_code == 200
                assert (await outsider.get("/api/v1/media/files/" + reference)).status_code == 404
    finally:
        await engine.dispose()
