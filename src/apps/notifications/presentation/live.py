"""Authenticated SSE transport; authorization never retains a stream-long DB session."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Annotated, Any, override
from uuid import UUID

import anyio
from fastapi import Depends, Header, Request
from fastapi.responses import StreamingResponse
from fastapi.sse import format_sse_event
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import ClientDisconnect
from starlette.types import Receive, Scope, Send

from apps.notifications.application.live import stream_events
from apps.notifications.data.live import LiveSubscription, subscribe
from apps.notifications.domain.live import LIFETIME_SECONDS, SEND_TIMEOUT, InboxChanged, InboxResync
from core.deps import SessionFactory, TokenDep, get_current_user
from core.i18n import _
from utils.base_schema import ERROR_CODES
from utils.exceptions import (
    InactiveUserException,
    InvalidCredentialError,
    NotAllowedException,
    ServiceUnavailableException,
    UserNotFoundException,
    ValidationDetailsException,
)
from utils.presenter import ErrorResponse

SUMMARY = _("Stream private inbox updates")
DESCRIPTION = _(
    "Recipient-only SSE invalidations over the persisted unified inbox. Requires an active bearer access token, user, session and registered client. No query parameters or user_id are accepted. Native EventSource needs an authenticated Node proxy; direct clients use streaming fetch with Authorization. Subscribe then refresh inbox/search and inbox/unread on inbox.resync, on reconnect and at least every 60 seconds. Last-Event-ID is an optional bounded reconnect hint, not an authorized replay cursor. inbox.changed contains only schema_version and notification_ref_id; its SSE id is the same reference. Deduplicate ids and coalesce refreshes. No subject, business data, password, URL or error is streamed. Heartbeat and authorization checks have a 15-second cadence; authorization probes are bounded to 3 seconds and changed events recheck authorization before sending. A stream lasts at most 300 seconds, receives at most 256 signals, and times out blocked sends after 5 seconds. Limit 3 streams per recipient and 200 per configured cache namespace across processes. No stream-long database session. Offline/missed signals remain in persisted search. Authentication or service failure after headers closes the stream; pre-stream errors use existing JSON envelopes. Success is text/event-stream, never a JSON success envelope. Private no-store/no-transform; proxies must disable buffering/compression and propagate disconnects. This backend contract does not establish browser or Node proxy acceptance."
)
RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": _("Private SSE invalidations and heartbeat comments; no JSON envelope."),
        "content": {
            "text/event-stream": {
                "schema": {"type": "string"},
                "example": 'event: inbox.resync\nretry: 3000\ndata: {"schema_version":1,"reason":"connected"}\n\n: heartbeat\n\n',
            }
        },
        "headers": {
            "Cache-Control": {
                "schema": {"type": "string", "const": "private, no-store, no-transform"}
            },
            "X-Accel-Buffering": {"schema": {"type": "string", "const": "no"}},
            "X-Content-Type-Options": {"schema": {"type": "string", "const": "nosniff"}},
        },
    },
    429: {
        "description": _(
            "Concurrent inbox stream limit reached. Retry after disconnecting another stream."
        ),
    },
    503: {
        "description": _(
            "Live signaling unavailable. Persisted inbox search remains authoritative."
        ),
    },
}
for status in ERROR_CODES:
    response = RESPONSES.setdefault(status, {})
    response.setdefault(
        "description", _("Pre-stream JSON error using the existing application envelope.")
    )
    response["content"] = {
        "application/json": {"schema": ErrorResponse.model_json_schema(mode="serialization")}
    }
EVENT_MODELS = {"inbox.changed": InboxChanged, "inbox.resync": InboxResync}
EVENT_SCHEMAS = {
    name: model.model_json_schema(mode="serialization") for name, model in EVENT_MODELS.items()
}


class InboxEventSourceResponse(StreamingResponse):
    """Bound network backpressure and total response lifetime, including stalled producers."""

    media_type = "text/event-stream"

    @override
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.headers["Cache-Control"] = "private, no-store, no-transform"
        self.headers["X-Accel-Buffering"] = "no"
        self.headers["X-Content-Type-Options"] = "nosniff"

        async def bounded_send(message):
            with anyio.fail_after(SEND_TIMEOUT):
                await send(message)

        try:
            with anyio.move_on_after(LIFETIME_SECONDS):
                await super().__call__(scope, receive, bounded_send)
        except TimeoutError, ClientDisconnect:
            pass
        finally:
            close = getattr(self.body_iterator, "aclose", None)
            if close is not None:
                with anyio.move_on_after(3, shield=True):
                    await close()


async def authenticate(request: Request, token: str) -> UUID:
    """Reuse current user/session/client authorization, then close the database session."""
    async with SessionFactory() as session:
        try:
            with anyio.fail_after(3):
                return (await get_current_user(session, token, request)).id
        except TimeoutError:
            raise ServiceUnavailableException() from None
        finally:
            with anyio.move_on_after(3, shield=True):
                await session.close()


@dataclass
class LiveConnection:
    request: Request
    token: str = field(repr=False)
    recipient_id: UUID
    subscription: LiveSubscription
    reconnect: bool

    async def authorized(self) -> bool:
        """Recheck revocation, expiry and active identity without retaining ORM objects."""
        try:
            return await authenticate(self.request, self.token) == self.recipient_id
        except (
            InactiveUserException,
            InvalidCredentialError,
            NotAllowedException,
            UserNotFoundException,
            ServiceUnavailableException,
            SQLAlchemyError,
            RedisError,
            OSError,
        ):
            return False


async def stream_connection(
    request: Request,
    token: TokenDep,
    last_event_id: Annotated[
        str | None,
        Header(
            alias="Last-Event-ID",
            max_length=256,
            description=_("Reconnect hint only; always resynchronize from the persisted inbox."),
        ),
    ] = None,
) -> AsyncIterator[LiveConnection]:
    """Authenticate and acquire admission before headers; release on disconnect/cancellation."""
    recipient_id = await authenticate(request, token)
    if request.query_params:
        raise ValidationDetailsException(
            [{"pointer": "/query", "code": "inbox.stream.query_forbidden"}]
        )
    async with subscribe(recipient_id) as subscription:
        yield LiveConnection(request, token, recipient_id, subscription, bool(last_event_id))


LiveConnectionDep = Annotated[LiveConnection, Depends(stream_connection)]


async def encoded_events(connection: LiveConnection) -> AsyncIterator[bytes]:
    """Encode typed public data with the installed FastAPI SSE formatter."""
    try:
        async for event in stream_events(
            connection.subscription,
            connection.authorized,
            reconnect=connection.reconnect,
        ):
            yield format_sse_event(
                data_str=event.data.model_dump_json() if event.data is not None else None,
                event=event.event,
                id=event.id,
                retry=event.retry,
                comment=event.comment,
            )
    except RedisError, OSError, ServiceUnavailableException:
        return


async def events(connection: LiveConnectionDep) -> InboxEventSourceResponse:
    """Return the actual bounded response; native generator routing discards subclasses."""
    return InboxEventSourceResponse(encoded_events(connection))
