"""Live transport contracts preserve the persisted recipient-only inbox."""

from unittest.mock import AsyncMock

import anyio
import pytest


def test_sse_openapi_is_separate_from_json_and_has_no_recipient_parameter():
    from main import app

    operation = app.openapi()["paths"]["/api/v1/inbox/events"]["get"]
    assert operation["security"]
    assert set(operation["responses"]["200"]["content"]) == {"text/event-stream"}
    assert not any(p["in"] == "query" for p in operation.get("parameters", []))
    assert "Last-Event-ID" in {p["name"] for p in operation["parameters"]}
    schemas = operation["x-sse-event-schemas"]
    assert set(schemas["inbox.changed"]["properties"]) == {"schema_version", "notification_ref_id"}
    assert schemas["inbox.changed"]["additionalProperties"] is False
    assert {"401", "403", "422", "429", "503"} <= set(operation["responses"])
    assert "application/json" in operation["responses"]["429"]["content"]
    from utils.localized_docs import localized_openapi

    translated = localized_openapi(app, "fa")["paths"]["/api/v1/inbox/events"]["get"]
    assert translated["summary"] != operation["summary"]
    assert translated["description"] != operation["description"]
    assert translated["x-sse-event-schemas"] == schemas


@pytest.mark.anyio
async def test_stream_deduplicates_bounds_input_and_closes_on_auth_revocation(monkeypatch):
    from apps.notifications.application import live
    from apps.notifications.domain.live import InboxChanged

    payload = InboxChanged(notification_ref_id="synthetic-reference").model_dump_json()
    subscription = AsyncMock()
    subscription.receive.side_effect = [payload, payload, payload]
    authorize = AsyncMock(side_effect=[True, True, True, False])
    events = [event async for event in live.stream_events(subscription, authorize)]
    assert [event.event for event in events] == ["inbox.resync", "inbox.changed"]
    assert events[1].id == "synthetic-reference"
    assert events[1].data is not None
    assert events[1].data.model_dump() == {
        "schema_version": 1,
        "notification_ref_id": "synthetic-reference",
    }


@pytest.mark.anyio
async def test_stream_heartbeat_reconnect_periodic_resync_and_signal_limit(monkeypatch):
    from apps.notifications.application import live

    clock = [0.0]
    monkeypatch.setattr(live, "monotonic", lambda: clock[0])
    monkeypatch.setattr(live, "MAX_SIGNALS", 2)

    async def receive(timeout):
        clock[0] += timeout
        return None if clock[0] <= 60 else '{"unexpected":"not public"}'

    subscription = AsyncMock()
    subscription.receive.side_effect = receive
    events = [
        event
        async for event in live.stream_events(
            subscription, AsyncMock(return_value=True), reconnect=True
        )
    ]
    assert getattr(events[0].data, "reason", None) == "reconnected"
    assert any(event.comment == "heartbeat" for event in events)
    assert any(getattr(event.data, "reason", None) == "periodic" for event in events)
    assert getattr(events[-1].data, "reason", None) == "event_limit"
    assert all(event.event != "inbox.changed" for event in events)


@pytest.mark.anyio
async def test_slow_response_send_is_bounded_and_iterator_is_closed(monkeypatch):
    from apps.notifications.presentation import live

    monkeypatch.setattr(live, "SEND_TIMEOUT", 0.01)
    closed = []

    async def body():
        try:
            yield b"event: inbox.resync\ndata: {}\n\n"
            await anyio.sleep_forever()
        finally:
            closed.append(True)

    async def send(message):
        if message["type"] == "http.response.body":
            await anyio.sleep_forever()

    async def receive():
        await anyio.sleep_forever()

    response = live.InboxEventSourceResponse(body())
    with anyio.fail_after(1):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
    assert closed == [True]


@pytest.mark.anyio
async def test_stream_lifetime_resync_is_bounded_without_a_db_connection(monkeypatch):
    from apps.notifications.application import live

    clock = [0.0]
    monkeypatch.setattr(live, "monotonic", lambda: clock[0])
    monkeypatch.setattr(live, "LIFETIME_SECONDS", 10)

    async def receive(timeout):
        assert timeout <= 10
        clock[0] += timeout

    subscription = AsyncMock()
    subscription.receive.side_effect = receive
    events = [
        event async for event in live.stream_events(subscription, AsyncMock(return_value=True))
    ]
    assert [getattr(event.data, "reason", None) for event in events] == ["connected", "lifetime"]


@pytest.mark.anyio
async def test_authentication_closes_each_session_before_streaming(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from uuid import uuid7

    from apps.notifications.presentation import live

    active_sessions = []
    recipient = uuid7()

    @asynccontextmanager
    async def session_factory():
        active_sessions.append(True)
        try:
            yield AsyncMock()
        finally:
            active_sessions.pop()

    monkeypatch.setattr(live, "SessionFactory", session_factory)
    monkeypatch.setattr(
        live, "get_current_user", AsyncMock(return_value=SimpleNamespace(id=recipient))
    )
    for _ in range(2):
        assert await live.authenticate(AsyncMock(), "synthetic-token") == recipient
        assert active_sessions == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        b'{"notification_ref_id":"safe\\nevent: injected"}',
        b'{"notification_ref_id":"safe","zip_password":"synthetic"}',
        b"x" * 1025,
    ],
)
async def test_malformed_private_or_oversized_signals_never_reach_sse(monkeypatch, payload):
    from apps.notifications.application import live

    monkeypatch.setattr(live, "MAX_SIGNALS", 1)
    subscription = AsyncMock()
    subscription.receive.return_value = payload
    events = [
        event async for event in live.stream_events(subscription, AsyncMock(return_value=True))
    ]
    assert [event.event for event in events] == ["inbox.resync", "inbox.resync"]
