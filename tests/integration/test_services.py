"""Cross-service infrastructure integration tests."""

import os
from datetime import UTC, datetime
from uuid import UUID, uuid7

import pytest
from anyio import create_task_group, to_thread
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import func, select

from apps.media.application.service import UserUploadService
from apps.media.domain.entity import UserUploadEntity
from apps.tasks.application.idempotency import claim_task
from apps.users.application.auth_service import AuthService
from apps.users.data.repository import UserRepository
from apps.users.domain.auth_dto import LoginDTO
from apps.users.domain.entity import UserEntity
from core.celery_app import celery_app
from core.deps import SessionFactory
from core.history import history_tables
from core.ref_id import create_ref_id
from core.settings import settings
from utils.exceptions import NotFoundException
from utils.s3 import delete_object, get_object, object_info, put_object, stream_object
from utils.security import hash_password

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1",
        reason="set RUN_INTEGRATION=1 with Docker Compose services running",
    ),
]


@pytest.mark.anyio
async def test_postgresql_and_dragonfly_are_available() -> None:
    """Exercise real PostgreSQL and Dragonfly connections."""
    async with SessionFactory() as session:
        value = (
            await super(type(session), session).execute(  # ty:ignore[deprecated]
                text("SELECT 1")
            )
        ).scalar_one()
    cache = Redis.from_url(str(settings.CACHE_DSN), decode_responses=True)
    try:
        assert value == 1
        assert await cache.ping()
    finally:
        await cache.aclose()


@pytest.mark.anyio
async def test_minio_upload_download_delete_round_trip() -> None:
    """Round-trip a private object through real MinIO."""
    key = f"integration/{uuid7()}"
    try:
        await put_object(key, b"integration", "text/plain")
        info = await object_info(key)
        assert info.content_type == "text/plain"
        assert info.metadata["sha256"]
        assert await get_object(key) == b"integration"
        assert b"".join([part async for part in stream_object(key, 3)]) == b"integration"
    finally:
        await delete_object(key)


@pytest.mark.anyio
async def test_postgresql_upload_access_is_owner_only_and_revocable() -> None:
    """Concurrent readers see only an active upload owned by their actor."""
    owner = UserEntity(username=f"media-owner-{uuid7()}", hashed_password="hash")
    outsider = UserEntity(username=f"media-outsider-{uuid7()}", hashed_password="hash")
    async with SessionFactory() as session:
        session.add_all([owner, outsider])
        await session.flush()
        upload = UserUploadEntity(
            user_id=owner.id,
            kind="file",
            object_key=f"integration/{uuid7()}",
            original_filename="report.txt",
            content_type="text/plain",
            size_bytes=6,
            sha256="0" * 64,
        )
        session.add(upload)
        await session.commit()
        reference = create_ref_id(upload.id, upload.version)

    outcomes: list[str] = []

    async def read_as(user_id: UUID, label: str) -> None:
        async with SessionFactory() as session:
            actor = await session.get(UserEntity, user_id)
            assert actor is not None
            try:
                await UserUploadService(session).get_for_download(reference, "file", actor)
            except NotFoundException:
                outcomes.append(f"{label}:hidden")
            else:
                outcomes.append(f"{label}:allowed")

    async with create_task_group() as group:
        group.start_soon(read_as, owner.id, "owner")
        group.start_soon(read_as, outsider.id, "outsider")
    assert sorted(outcomes) == ["outsider:hidden", "owner:allowed"]

    async with SessionFactory() as session:
        stored = await session.get(UserUploadEntity, upload.id)
        actor = await session.get(UserEntity, owner.id)
        assert stored is not None and actor is not None
        stored.deleted_at = datetime.now(UTC)
        await session.commit()
        with pytest.raises(NotFoundException, match="Upload not found"):
            await UserUploadService(session).get_for_download(reference, "file", actor)


@pytest.mark.anyio
async def test_rabbitmq_celery_worker_executes_task() -> None:
    """Submit a task through RabbitMQ and await a real worker result."""
    result = await to_thread.run_sync(
        lambda: celery_app.send_task("system.ping", queue=settings.CELERY_DEFAULT_QUEUE)
    )
    value = await to_thread.run_sync(lambda: result.get(timeout=15, disable_sync_subtasks=False))
    assert value == {"status": "ok"}


@pytest.mark.anyio
async def test_concurrent_task_idempotency_has_one_winner() -> None:
    """Concurrent Dragonfly/PostgreSQL claims allow exactly one worker."""
    key = uuid7()
    results: list[bool] = []

    async def claim(task_id: str) -> None:
        results.append(await claim_task(key, task_id))

    async with create_task_group() as group:
        group.start_soon(claim, "one")
        group.start_soon(claim, "two")
    assert sorted(results) == [False, True]


@pytest.mark.anyio
async def test_full_authentication_rotation_logout_and_password_flow() -> None:
    """Exercise login, rotation, logout, reset, and audit persistence on PostgreSQL."""
    username = f"auth-{uuid7()}"
    async with SessionFactory() as session:
        user = UserEntity(username=username, hashed_password=await hash_password("password-old"))
        session.add(user)
        await session.commit()
        service = AuthService(session)
        pair = await service.login(
            LoginDTO(username=username, password="password-old", device_name="pytest"),
            request_id=str(uuid7()),
            ip_address="127.0.0.1",
            user_agent="pytest",
        )
        rotated = await service.refresh(pair.refresh_token)
        assert rotated.refresh_token != pair.refresh_token
        await service.logout(rotated.refresh_token)
        reset = await service.request_password_reset(username)
        assert reset is not None
        await service.reset_password(reset, "password-new")
        again = await service.login(
            LoginDTO(username=username, password="password-new"),
            request_id=None,
            ip_address=None,
            user_agent=None,
        )
        assert again.access_token


@pytest.mark.anyio
async def test_concurrent_optimistic_lock_detects_stale_writer() -> None:
    """Two independently loaded writers cannot silently overwrite each other."""
    user = UserEntity(
        username=f"optimistic-{uuid7()}", hashed_password=await hash_password("password")
    )
    async with SessionFactory() as seed:
        seed.add(user)
        await seed.commit()
    async with SessionFactory() as first, SessionFactory() as second:
        first_copy = await first.get(UserEntity, user.id)
        second_copy = await second.get(UserEntity, user.id)
        assert first_copy is not None and second_copy is not None
        await UserRepository(first, UserEntity).update(first_copy, {"username": f"first-{uuid7()}"})
        await first.commit()
        with pytest.raises(StaleDataError):
            second_copy.username = f"second-{uuid7()}"
            second.add(second_copy)
            await second.flush()


@pytest.mark.anyio
async def test_history_is_created_and_rolled_back_with_business_transaction() -> None:
    """History rows share commit and rollback semantics with entity changes."""
    table = history_tables()["user"]
    user = UserEntity(username=f"history-{uuid7()}", hashed_password="secret")
    async with SessionFactory() as session:
        session.add(user)
        await session.commit()
        before = (
            await super(type(session), session).execute(  # ty:ignore[deprecated]
                select(func.count()).select_from(table).where(table.c.ENTITY_ID == user.id)
            )
        ).scalar_one()
        user.first_name = "rolled-back"
        session.add(user)
        await session.flush()
        await session.rollback()
        after = (
            await super(type(session), session).execute(  # ty:ignore[deprecated]
                select(func.count()).select_from(table).where(table.c.ENTITY_ID == user.id)
            )
        ).scalar_one()
    assert before == after == 1
