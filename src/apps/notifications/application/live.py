"""Commit-owned outbox hints and bounded recipient streams over the existing inbox."""

from collections.abc import AsyncIterator, Awaitable, Callable
from time import monotonic
from uuid import UUID, uuid5

import anyio
import anyio.lowlevel
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.notifications.data.live import LiveSubscription, recipient_channel, signal_client
from apps.notifications.domain.entity import NotificationEntity
from apps.notifications.domain.live import (
    HEARTBEAT_SECONDS,
    LIFETIME_SECONDS,
    MAX_SIGNAL_BYTES,
    MAX_SIGNALS,
    RESYNC_SECONDS,
    SEND_TIMEOUT,
    InboxChanged,
    InboxLiveEvent,
    InboxResync,
)
from apps.tasks.application.outbox import enqueue_task
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory
from core.ref_id import create_ref_id
from core.settings import settings

PUSH_TASK = "bpms.push_inbox_notification"


def stage_push(session: AsyncSession, row: NotificationEntity) -> None:
    """Stage one creation signal with the notification; callers own the commit."""
    identity = uuid5(row.id, "inbox-push:created")
    enqueue_task(
        session,
        PUSH_TASK,
        kwargs={"notification_id": str(row.id)},
        queue=settings.CELERY_AUTOMATION_QUEUE,
        task_id=str(identity),
        idempotency_key=identity,
    )


async def publish_notification(notification_id: UUID) -> bool:
    """The existing worker loads only committed rows, then publishes a minimal invalidation."""
    async with SessionFactory() as session:
        row = await session.get(NotificationEntity, notification_id)
        if row is None or row.deleted_at is not None or row.status != "ACTIVE":
            return False
        recipient = await session.get(UserEntity, row.recipient_user_id)
        if recipient is None or recipient.deleted_at is not None:
            return False
        recipient_id = recipient.id
        event = InboxChanged(notification_ref_id=create_ref_id(row.id, row.version))
    async with signal_client() as cache:
        await cache.publish(recipient_channel(recipient_id), event.model_dump_json())
    return True


def resync(reason: str, *, initial: bool = False) -> InboxLiveEvent:
    """Tell clients to refresh persisted search/unread state without a replay promise."""
    return InboxLiveEvent(
        event="inbox.resync",
        data=InboxResync.model_validate({"reason": reason}),
        retry=3000 if initial else None,
    )


async def stream_events(
    subscription: LiveSubscription,
    authorize: Callable[[], Awaitable[bool]],
    *,
    reconnect: bool = False,
) -> AsyncIterator[InboxLiveEvent]:
    """Bound signals, time and dedupe memory; recheck auth using short independent sessions."""
    start = monotonic()
    # Leave time to recheck authorization, emit renewal and finish the response before
    # the hard transport deadline. Short owned test lifetimes retain the same policy.
    lifetime = LIFETIME_SECONDS - min(2 * SEND_TIMEOUT, LIFETIME_SECONDS / 2)
    last_resync = start
    next_check = start + HEARTBEAT_SECONDS
    seen: set[str] = set()
    received = 0
    if not await authorize():
        return
    yield resync("reconnected" if reconnect else "connected", initial=True)
    while monotonic() - start < lifetime:
        timeout = min(next_check - monotonic(), lifetime - (monotonic() - start))
        payload = await subscription.receive(max(0, timeout))
        check_started = monotonic()
        if not await authorize():
            return
        next_check = check_started + HEARTBEAT_SECONDS
        now = monotonic()
        if now - start >= lifetime:
            break
        if now - last_resync >= RESYNC_SECONDS:
            last_resync = now
            yield resync("periodic")
        if payload is None:
            yield InboxLiveEvent(comment="heartbeat")
            continue
        received += 1
        if len(payload) <= MAX_SIGNAL_BYTES:
            try:
                event = InboxChanged.model_validate_json(payload)
            except ValidationError:
                event = None
            if event is not None and event.notification_ref_id not in seen:
                seen.add(event.notification_ref_id)
                yield InboxLiveEvent(
                    event="inbox.changed",
                    data=event,
                    id=event.notification_ref_id,
                )
        if received >= MAX_SIGNALS:
            yield resync("event_limit")
            return
        await anyio.lowlevel.checkpoint()
    yield resync("lifetime")
