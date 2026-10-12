"""Owned real HTTP/Redis/Celery delivery; browser and Node proxy acceptance are separate."""

import json
import os
import socket
import sys
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import UUID, uuid7

import anyio
import httpx
import jwt
import pytest
from sqlmodel import select

from apps.notifications.application.events import stage_notice
from apps.notifications.application.live import PUSH_TASK, publish_notification
from apps.notifications.data.live import recipient_channel, signal_client, subscribe
from apps.notifications.domain.entity import NotificationEntity
from apps.reporting.application.service import ReportService
from apps.reporting.domain.entity import ReportEntity, ReportStatus
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import BusinessRequestCreateDTO, BusinessRequestSubmitDTO
from apps.tasks.application.outbox import dispatch_outbox
from apps.tasks.domain.entity import TaskOutboxEntity
from apps.tasks.tasks import push_inbox_notification
from apps.users.domain.auth_dto import TokenPairDTO
from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from core.celery_app import celery_app
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id, open_ref_id
from core.settings import settings
from tests.integration.test_frontend_journey import _prepare_journey
from utils.date_utils import get_datetime_utc
from utils.exceptions import RateLimitedException
from utils.s3 import ensure_bucket

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_REPORT_WORKER") != "1",
        reason="requires disposable reporting worker and storage",
    ),
]


@asynccontextmanager
async def owned_api(
    lifetime: int = 300, *, lifespan: str = "off"
) -> AsyncGenerator[httpx.AsyncClient]:
    """Run another API process against only the transfer profile's owned resources."""
    database = os.environ["POSTGRES_DB"]
    assert database.startswith("bpms_flow_") and database == os.getenv("FLOW_TEST_OWNED_DATABASE")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with TemporaryDirectory(prefix="inbox-sse-api-") as directory:
        os.chmod(directory, 0o700)
        path = Path(directory) / "api.log"
        with path.open("w+") as log:
            os.chmod(path, 0o600)
            # Accelerate heartbeat/resync only in this owned test process. Production limits
            # and timeout behavior are independently exercised at the transport seam.
            command = (
                "from apps.notifications.application import live; "
                "live.HEARTBEAT_SECONDS=0.2; live.RESYNC_SECONDS=0.6; "
                f"live.LIFETIME_SECONDS={lifetime}; "
                "from apps.notifications.presentation import live as http_live; "
                f"http_live.LIFETIME_SECONDS={lifetime}; "
                "import uvicorn; "
                f"uvicorn.run('main:app',host='127.0.0.1',port={port},lifespan={lifespan!r},log_level='warning')"
            )
            process = await anyio.open_process(
                [sys.executable, "-c", command],
                env={**os.environ, "LOG_LEVEL": "WARNING"},
                stdout=log,
                stderr=log,
            )
            try:
                async with httpx.AsyncClient(
                    base_url=f"http://127.0.0.1:{port}",
                    trust_env=False,
                    timeout=30,
                ) as client:
                    with anyio.fail_after(60):
                        while True:
                            assert process.returncode is None, "Owned API exited"
                            try:
                                response = await client.get("/api/v1/openapi.json")
                                if response.status_code == 200:
                                    break
                            except httpx.ConnectError:
                                pass
                            await anyio.sleep(0.1)
                    yield client
                    assert "ERROR:" not in path.read_text(), (
                        "Owned API emitted an unexpected runtime error"
                    )
            finally:
                process.terminate()
                with anyio.CancelScope(shield=True):
                    with anyio.move_on_after(10) as wait_scope:
                        await process.wait()
                    if wait_scope.cancel_called:
                        process.kill()
                        await process.wait()
                    await process.aclose()


@asynccontextmanager
async def dispatching() -> AsyncGenerator[None]:
    """Reuse the real dispatcher for both domain fanout and its committed push successors."""

    stopping = anyio.Event()

    async def pulse():
        while not stopping.is_set():
            await dispatch_outbox(celery_app)
            await anyio.sleep(0.1)

    async with anyio.create_task_group() as group:
        group.start_soon(pulse)
        try:
            yield
        finally:
            stopping.set()


async def frame(lines: AsyncIterator[str]) -> tuple[str, dict[str, Any] | None, str | None]:
    """Read one actual SSE frame, keeping heartbeat comments separate from JSON events."""
    event, data, identity = "", None, None
    with anyio.fail_after(30):
        async for line in lines:
            if not line:
                if event or data is not None:
                    return event, data, identity
                continue
            if line.startswith(":"):
                event = "heartbeat"
            elif line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
            elif line.startswith("id: "):
                identity = line[4:]
    raise AssertionError("Stream closed without the required frame")


async def changed(lines: AsyncIterator[str], expected: UUID | None = None) -> dict[str, Any]:
    """Allow unrelated own notices but reject private payload expansion."""
    with anyio.fail_after(45):
        while True:
            name, data, identity = await frame(lines)
            if name == "inbox.changed":
                assert data is not None and set(data) == {"schema_version", "notification_ref_id"}
                assert data["schema_version"] == 1 and identity == data["notification_ref_id"]
                assert identity is not None
                if expected is None or open_ref_id(identity)[0] == expected:
                    return data


async def login(
    client: httpx.AsyncClient, username: str, password: str
) -> tuple[dict[str, str], dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    pair = TokenPairDTO.model_validate(response.json()["data"])
    return {"Authorization": "Bearer " + pair.access_token}, {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
    }


@pytest.mark.anyio
async def test_actual_report_cartable_worker_push_duplicate_and_offline_resync():
    try:
        await ensure_bucket()
        names, password, kind = await _prepare_journey()
        async with SessionFactory() as session:
            owner = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[0]))
            ).one()
            reviewer = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[1]))
            ).one()
            owner_id, reviewer_id = owner.id, reviewer.id
        async with owned_api() as client:
            owner_headers, _ = await login(client, names[0], password)
            reviewer_headers, _ = await login(client, names[1], password)
            async with client.stream(
                "GET", "/api/v1/inbox/events", headers=owner_headers
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                assert response.headers["cache-control"] == "private, no-store, no-transform"
                assert response.headers["x-accel-buffering"] == "no"
                lines = response.aiter_lines()
                assert (await frame(lines))[1] == {"schema_version": 1, "reason": "connected"}
                async with SessionFactory() as session:
                    owner = await session.get(UserEntity, owner_id)
                    assert owner is not None
                    report = await ReportService(session).create(
                        "users",
                        owner,
                        UserQuery.model_validate(
                            {
                                "filters": [
                                    {
                                        "field_name": "username",
                                        "operation": "equal",
                                        "value": names[0],
                                    }
                                ]
                            }
                        ),
                        "en",
                    )
                    report_id = report.id
                async with dispatching():
                    with anyio.fail_after(45):
                        while True:
                            async with SessionFactory() as session:
                                report = await session.get(ReportEntity, report_id)
                                assert report is not None and report.status != ReportStatus.FAILED
                                notices = (
                                    await session.exec(
                                        select(NotificationEntity).where(
                                            NotificationEntity.target_id == report_id,
                                            NotificationEntity.recipient_user_id == owner_id,
                                        )
                                    )
                                ).all()
                                if report.status == ReportStatus.READY and notices:
                                    assert len(notices) == 1
                                    notification_id = notices[0].id
                                    assert notices[0].read_at is None
                                    break
                            await anyio.sleep(0.1)
                    report_event = await changed(lines, notification_id)
                    # Two actual worker replays publish the same logical invalidation.
                    for _ in range(2):
                        push_inbox_notification.apply_async(
                            kwargs={"notification_id": str(notification_id)},
                        )
                    async with SessionFactory() as session, session.begin():
                        row = await stage_notice(
                            session,
                            map_id="MAP-14",
                            event_id=uuid7(),
                            recipient_id=owner_id,
                            target_kind="account",
                            target_id=owner_id,
                        )
                        assert row is not None
                        followup_id = row.id
                    next_event = await changed(lines)
                    assert open_ref_id(next_event["notification_ref_id"])[0] == followup_id
                    async with client.stream(
                        "GET", "/api/v1/inbox/events", headers=reviewer_headers
                    ) as work_response:
                        work_lines = work_response.aiter_lines()
                        assert (await frame(work_lines))[0] == "inbox.resync"
                        async with SessionFactory() as session, session.begin():
                            owner = await session.get(UserEntity, owner_id)
                            assert owner is not None
                            service = RequestService(session)
                            request, _ = await service.create_draft(
                                BusinessRequestCreateDTO(
                                    request_type_ref_id=kind, data={"amount": "42"}
                                ),
                                owner,
                            )
                            request, _ = await service.submit(
                                create_ref_id(request.id, request.version),
                                BusinessRequestSubmitDTO(submit_key=uuid7().hex),
                                owner,
                            )
                            request_id = request.id
                        with anyio.fail_after(45):
                            while True:
                                async with SessionFactory() as session:
                                    rows = (
                                        await session.exec(
                                            select(NotificationEntity).where(
                                                NotificationEntity.business_request_id
                                                == request_id,
                                                NotificationEntity.recipient_user_id == reviewer_id,
                                                NotificationEntity.template_key
                                                == "application.map_02",
                                            )
                                        )
                                    ).all()
                                    if rows:
                                        assert len(rows) == 1
                                        work_notice_id = rows[0].id
                                        break
                                await anyio.sleep(0.1)
                        await changed(work_lines, work_notice_id)
            # No connected browser is needed to persist or dispatch the next notification.
            async with SessionFactory() as session, session.begin():
                row = await stage_notice(
                    session,
                    map_id="MAP-14",
                    event_id=uuid7(),
                    recipient_id=owner_id,
                    target_kind="account",
                    target_id=owner_id,
                )
                assert row is not None
                offline_id = row.id
            async with dispatching():
                await anyio.sleep(0.5)
            headers = {**owner_headers, "Last-Event-ID": report_event["notification_ref_id"]}
            async with client.stream("GET", "/api/v1/inbox/events", headers=headers) as response:
                assert response.status_code == 200, (await response.aread()).decode()
                assert (await frame(response.aiter_lines()))[1] == {
                    "schema_version": 1,
                    "reason": "reconnected",
                }
                inbox = await client.post(
                    "/api/v1/inbox/search", json={"size": 100}, headers=owner_headers
                )
                assert inbox.status_code == 200
                identities = {
                    open_ref_id(row["ref_id"])[0] for row in inbox.json()["result"]["items"]
                }
                assert {notification_id, offline_id} <= identities
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_actual_heartbeat_lifetime_renewal_and_cleanup():
    try:
        names, password, _ = await _prepare_journey()
        async with SessionFactory() as session:
            actor = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[0]))
            ).one()
            recipient_id = actor.id
        async with owned_api(lifetime=2) as client:
            headers, _ = await login(client, names[0], password)
            async with client.stream("GET", "/api/v1/inbox/events", headers=headers) as response:
                assert response.status_code == 200
                with anyio.fail_after(5):
                    lines = [line async for line in response.aiter_lines()]
                assert ": heartbeat" in lines
                assert 'data: {"schema_version":1,"reason":"lifetime"}' in lines
            async with signal_client() as cache:
                with anyio.fail_after(5):
                    while await cache.zcard(f"inbox-live:connections:{recipient_id}"):
                        await anyio.sleep(0.1)
                assert await cache.pubsub_numsub(recipient_channel(recipient_id)) == [
                    (recipient_channel(recipient_id).encode(), 0)
                ]
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_committed_only_signals_outsider_revocation_limits_and_disconnect():
    try:
        names, password, _ = await _prepare_journey()
        async with SessionFactory() as session:
            owner = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[0]))
            ).one()
            other = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[2]))
            ).one()
            owner_id, other_id = owner.id, other.id
        # An independent cache subscriber must never see a rolled-back creation signal.
        async with subscribe(owner_id) as observer:
            async with SessionFactory() as session:
                row = await stage_notice(
                    session,
                    map_id="MAP-14",
                    event_id=uuid7(),
                    recipient_id=owner_id,
                    target_kind="account",
                    target_id=owner_id,
                )
                assert row is not None
                rolled_back_id = row.id
                await session.rollback()
            await dispatch_outbox(celery_app)
            assert not await publish_notification(rolled_back_id)
            assert await observer.receive(0.1) is None
            async with SessionFactory() as session:
                assert await session.get(NotificationEntity, rolled_back_id) is None
                pending = (
                    await session.exec(
                        select(TaskOutboxEntity).where(TaskOutboxEntity.task_name == PUSH_TASK)
                    )
                ).all()
                assert all(
                    row.kwargs.get("notification_id") != str(rolled_back_id) for row in pending
                )
        async with owned_api() as client:
            owner_headers, pair = await login(client, names[0], password)
            other_headers, _ = await login(client, names[2], password)
            assert (await client.get("/api/v1/inbox/events")).status_code == 401
            assert (
                await client.get(
                    "/api/v1/inbox/events?user_id=" + str(owner_id), headers=other_headers
                )
            ).status_code == 422
            assert (
                await client.get(
                    "/api/v1/inbox/events", headers={**owner_headers, "Last-Event-ID": "x" * 257}
                )
            ).status_code == 422
            async with SessionFactory() as session, session.begin():
                row = await stage_notice(
                    session,
                    map_id="MAP-14",
                    event_id=uuid7(),
                    recipient_id=owner_id,
                    target_kind="account",
                    target_id=owner_id,
                )
                assert row is not None
                reference = create_ref_id(row.id, row.version)
                notification_id = row.id
            assert (
                await client.get("/api/v1/inbox/" + reference, headers=other_headers)
            ).status_code == 403
            async with client.stream(
                "GET", "/api/v1/inbox/events", headers=other_headers
            ) as response:
                assert response.status_code == 200
                lines = response.aiter_lines()
                assert (await frame(lines))[0] == "inbox.resync"
                assert await publish_notification(notification_id)
                for _ in range(3):
                    assert (await frame(lines))[0] != "inbox.changed"
            async with AsyncExitStack() as stack:
                retained_lines = []
                for _ in range(3):
                    response = await stack.enter_async_context(
                        client.stream("GET", "/api/v1/inbox/events", headers=owner_headers)
                    )
                    assert response.status_code == 200
                    lines = response.aiter_lines()
                    retained_lines.append(lines)
                    assert (await frame(lines))[0] == "inbox.resync"
                async with client.stream(
                    "GET", "/api/v1/inbox/events", headers=owner_headers
                ) as denied:
                    assert denied.status_code == 429
                    assert json.loads(await denied.aread())["code"] == 1006
                # Independent subscription admission shares the same recipient/global lease state.
                with pytest.raises(RateLimitedException):
                    async with subscribe(owner_id):
                        pytest.fail("Cross-process admission limit was bypassed")
            async with signal_client() as cache:
                with anyio.fail_after(5):
                    while await cache.zcard(f"inbox-live:connections:{owner_id}"):
                        await anyio.sleep(0.1)
                assert await cache.pubsub_numsub(recipient_channel(owner_id)) == [
                    (recipient_channel(owner_id).encode(), 0)
                ]
            async with client.stream(
                "GET", "/api/v1/inbox/events", headers=owner_headers
            ) as response:
                assert response.status_code == 200
                lines = response.aiter_lines()
                assert (await frame(lines))[0] == "inbox.resync"
                revoked = await client.post(
                    "/api/v1/auth/logout", json={"refresh_token": pair["refresh_token"]}
                )
                assert revoked.status_code == 200
                with anyio.fail_after(5):
                    remaining = [line async for line in lines]
                assert not any("inbox.changed" in line for line in remaining)
            assert (
                await client.get("/api/v1/inbox/events", headers=owner_headers)
            ).status_code == 401
            # Existing active-user and JWT expiry checks apply to live connections too.
            expired = jwt.decode(
                pair["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            expired["exp"] = int(get_datetime_utc().timestamp()) - 1
            expired_headers = {
                "Authorization": "Bearer "
                + jwt.encode(expired, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
            }
            assert (
                await client.get("/api/v1/inbox/events", headers=expired_headers)
            ).status_code == 401
            _, fresh_pair = await login(client, names[0], password)
            short = jwt.decode(
                fresh_pair["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            short["exp"] = int(get_datetime_utc().timestamp()) + 3
            short_headers = {
                "Authorization": "Bearer "
                + jwt.encode(short, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
            }
            async with client.stream(
                "GET", "/api/v1/inbox/events", headers=short_headers
            ) as response:
                assert response.status_code == 200
                lines = response.aiter_lines()
                assert (await frame(lines))[0] == "inbox.resync"
                with anyio.fail_after(6):
                    remaining = [line async for line in lines]
                assert not any("inbox.changed" in line for line in remaining)
            async with client.stream(
                "GET", "/api/v1/inbox/events", headers=other_headers
            ) as response:
                assert response.status_code == 200
                lines = response.aiter_lines()
                assert (await frame(lines))[0] == "inbox.resync"
                async with SessionFactory() as session, session.begin():
                    other = await session.get(UserEntity, other_id)
                    assert other is not None
                    other.deleted_at = get_datetime_utc()
                with anyio.fail_after(5):
                    remaining = [line async for line in lines]
                assert not any("inbox.changed" in line for line in remaining)
            assert (
                await client.get("/api/v1/inbox/events", headers=other_headers)
            ).status_code == 401
            async with signal_client() as cache:
                with anyio.fail_after(5):
                    while await cache.zcard(f"inbox-live:connections:{owner_id}"):
                        await anyio.sleep(0.1)
                assert await cache.zcard(f"inbox-live:connections:{other_id}") == 0
                # Global admission is also shared and prunes stale crashed leases.
                global_key = "inbox-live:connections"
                now, _ = await cache.time()
                tokens = ["owned-limit-" + uuid7().hex for _ in range(200)]
                await cache.zadd(global_key, dict.fromkeys(tokens, now + 330))
                try:
                    with pytest.raises(RateLimitedException):
                        async with subscribe(uuid7()):
                            pytest.fail("Global admission limit was bypassed")
                finally:
                    await cache.zrem(global_key, *tokens)
                stale = "owned-stale-" + uuid7().hex
                await cache.zadd(global_key, {stale: now - 1})
                async with subscribe(uuid7()):
                    assert await cache.zscore(global_key, stale) is None
    finally:
        await engine.dispose()
