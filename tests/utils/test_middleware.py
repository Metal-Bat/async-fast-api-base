"""Tests for request logging and request identifier middleware."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4, uuid7

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient

from core.history import history_context
from utils import middleware
from utils.middleware import RequestLoggingMiddleware, mask_sensitive_json, resolve_request_id


def test_request_id_preserves_uuid7_and_replaces_invalid_values() -> None:
    existing = str(uuid7())
    assert resolve_request_id(existing) == existing
    assert resolve_request_id(None) != existing
    assert resolve_request_id("invalid") != "invalid"
    assert UUID(resolve_request_id(str(uuid4()))).version == 7
    assert UUID(resolve_request_id(None)).version == 7


def test_mask_sensitive_json_recursively_masks_credentials() -> None:
    body = {
        "username": "admin",
        "password": "admin",
        "result": {
            "accessToken": "access-value",
            "refresh_token": "refresh-value",
            "items": [{"client-secret": "secret-value", "name": "visible"}],
        },
    }

    assert mask_sensitive_json(body) == {
        "username": "admin",
        "password": "[REDACTED]",
        "result": {
            "accessToken": "[REDACTED]",
            "refresh_token": "[REDACTED]",
            "items": [{"client-secret": "[REDACTED]", "name": "visible"}],
        },
    }


def test_event_correlation_keys_are_redacted_from_request_logs() -> None:
    assert mask_sensitive_json({"correlation_key": "invoice-secret"}) == {
        "correlation_key": "[REDACTED]"
    }


@pytest.mark.anyio
async def test_logging_middleware_logs_masked_json_request_and_response(monkeypatch) -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    class CaptureLogger:
        def bind(self, **_: Any) -> CaptureLogger:
            return self

        async def ainfo(self, event: str, **fields: Any) -> None:
            events.append((event, fields))

        async def acritical(self, event: str, **fields: Any) -> None:
            events.append((event, fields))

    monkeypatch.setattr(middleware, "logger", CaptureLogger())
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.post("/echo")
    async def echo(body: dict[str, Any]) -> dict[str, Any]:
        return {"received": body, "access_token": "response-token"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/echo",
            json={"username": "admin", "password": "request-password"},
        )

    assert response.status_code == 200
    received_at = events[0][1].pop("server_received_at")
    duration_ms = events[1][1].pop("processing_duration_ms")
    assert datetime.fromisoformat(received_at).tzinfo == UTC
    assert duration_ms >= 0
    assert events == [
        (
            "REQUEST",
            {
                "content_length": "50",
                "content_type": "application/json",
                "user_agent": "python-httpx/0.28.1",
                "client_date_status": "unavailable",
                "client_date": None,
                "client_date_delta_seconds": None,
                "body": {"username": "admin", "password": "[REDACTED]"},
            },
        ),
        (
            "RESPONSE",
            {
                "status_code": 200,
                "body": {
                    "received": {"username": "admin", "password": "[REDACTED]"},
                    "access_token": "[REDACTED]",
                },
            },
        ),
    ]


@pytest.mark.anyio
async def test_user_agent_capture_is_bounded_and_shared_with_history(monkeypatch) -> None:
    events: list[dict[str, Any]] = []

    class CaptureLogger:
        def bind(self, **_: Any) -> CaptureLogger:
            return self

        async def ainfo(self, event: str, **fields: Any) -> None:
            if event == "REQUEST":
                events.append(fields)

        async def acritical(self, event: str, **fields: Any) -> None:
            pass

    monkeypatch.setattr(middleware, "logger", CaptureLogger())
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/agent")
    async def agent(request: Request) -> dict[str, str | None]:
        context = history_context.get()
        return {
            "state": request.state.user_agent,
            "history": context.user_agent if context else None,
        }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        request_without_agent = client.build_request("GET", "/agent")
        del request_without_agent.headers["user-agent"]
        missing = await client.send(request_without_agent)
        empty = await client.get("/agent", headers={"User-Agent": ""})
        mixed = await client.get("/agent", headers={"uSeR-aGeNt": "Native/2.0"})
        long = await client.get("/agent", headers={"User-Agent": "x" * 1100})

    assert missing.json() == {"state": None, "history": None}
    assert empty.json() == {"state": None, "history": None}
    assert mixed.json() == {"state": "Native/2.0", "history": "Native/2.0"}
    assert long.json() == {"state": "x" * 1024, "history": "x" * 1024}
    assert [event["user_agent"] for event in events] == [
        None,
        None,
        "Native/2.0",
        "x" * 1024,
    ]


@pytest.mark.anyio
async def test_optional_client_date_reports_signed_delta_without_changing_response(
    monkeypatch,
) -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    class CaptureLogger:
        def bind(self, **_: Any) -> CaptureLogger:
            return self

        async def ainfo(self, event: str, **fields: Any) -> None:
            events.append((event, fields))

        async def acritical(self, event: str, **fields: Any) -> None:
            pass

    monkeypatch.setattr(middleware, "logger", CaptureLogger())
    monkeypatch.setattr(
        middleware, "get_datetime_utc", lambda: datetime(2026, 9, 28, 12, 0, 0, tzinfo=UTC)
    )
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def chunks():
            yield b"one"
            yield b"two"

        return StreamingResponse(chunks(), media_type="text/plain")

    @app.get("/public")
    async def public() -> StreamingResponse:
        return StreamingResponse(iter([b"public"]), headers={"Cache-Control": "public, max-age=60"})

    @app.get("/max-age")
    async def max_age() -> StreamingResponse:
        return StreamingResponse(iter([b"cached"]), headers={"Cache-Control": "max-age=60"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        absent = await client.get("/stream")
        past = await client.get("/stream", headers={"Date": "Mon, 28 Sep 2026 11:54:59 GMT"})
        future = await client.get("/stream", headers={"Date": "Mon, 28 Sep 2026 12:05:01 GMT"})
        invalid = await client.get("/stream", headers={"Date": "yesterday"})
        oversized = await client.get("/stream", headers={"Date": "x" * 130})
        duplicate = await client.get(
            "/stream",
            headers=[
                ("Date", "Mon, 28 Sep 2026 12:00:00 GMT"),
                ("dAtE", "Mon, 28 Sep 2026 12:00:00 GMT"),
            ],
        )
        public_response = await client.get(
            "/public", headers={"Date": "Mon, 28 Sep 2026 11:54:59 GMT"}
        )
        max_age_response = await client.get("/max-age")
        monkeypatch.setattr(middleware.settings, "HTTP_CLIENT_DATE_ADVISORY_SECONDS", 302)
        below_threshold = await client.get(
            "/stream", headers={"Date": "Mon, 28 Sep 2026 11:54:59 GMT"}
        )

    assert all(
        response.status_code == 200 and response.content == b"onetwo"
        for response in (absent, past, future, invalid, oversized, duplicate)
    )
    assert absent.headers["x-client-date-status"] == "unavailable"
    assert past.headers["x-client-date-status"] == "available"
    assert past.headers["x-client-date-delta-seconds"] == "301"
    assert past.headers["x-client-date-advisory"] == "check-device-time"
    assert future.headers["x-client-date-delta-seconds"] == "-301"
    assert future.headers["x-client-date-advisory"] == "check-device-time"
    assert all(
        response.headers["x-client-date-status"] == "invalid"
        for response in (invalid, oversized, duplicate)
    )
    assert all(
        "x-client-date-advisory" not in response.headers
        for response in (absent, invalid, oversized, duplicate)
    )
    assert all(
        response.headers["cache-control"] == "private"
        for response in (absent, past, future, invalid, oversized, duplicate)
    )
    assert public_response.headers["cache-control"] == "public, max-age=60"
    assert max_age_response.headers["cache-control"] == "private, max-age=60"
    assert "x-client-date-status" not in public_response.headers
    assert "x-client-date-advisory" not in below_threshold.headers
    assert "date" not in past.headers
    assert past.headers["x-server-received-at"] == "2026-09-28T12:00:00Z"
    assert UUID(past.headers["x-request-id"]).version == 7
    assert events[2][1]["client_date_delta_seconds"] == 301
    assert events[2][1]["client_date_status"] == "available"
    assert "processing_duration_ms" in events[1][1]


def test_rfc9110_http_date_variants_and_bad_weekday() -> None:
    assert middleware.parse_client_date("Sunday, 06-Nov-94 08:49:37 GMT") == datetime(
        1994, 11, 6, 8, 49, 37, tzinfo=UTC
    )
    assert middleware.parse_client_date("Sun Nov  6 08:49:37 1994") == datetime(
        1994, 11, 6, 8, 49, 37, tzinfo=UTC
    )
    assert middleware.parse_client_date("Tue, 28 Sep 2026 12:00:00 GMT") is None
    future_year = datetime(2069, 11, 6, 8, 49, 37, tzinfo=UTC)
    weekday = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[
        future_year.weekday()
    ]
    assert middleware.parse_client_date(f"{weekday}, 06-Nov-69 08:49:37 GMT", 2026) == future_year
