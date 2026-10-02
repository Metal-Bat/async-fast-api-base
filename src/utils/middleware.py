import json
import re
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any, Protocol, cast, override
from uuid import UUID, uuid7

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from core.history import HistoryContext, history_context
from core.i18n import reset_language, resolve_language, set_language
from core.settings import settings
from utils.date_utils import get_datetime_utc

logger = structlog.get_logger("json_logger")

_REDACTED = "[REDACTED]"
_SENSITIVE_FIELD_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "correlation_key",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
_HTTP_DATE_FORMS = (
    re.compile(
        r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun), [0-9]{2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2} GMT$"
    ),
    re.compile(
        r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), [0-9]{2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} GMT$"
    ),
    re.compile(
        r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) ( [0-9]|[0-9]{2}) [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4}$"
    ),
)
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class _StreamingBodyResponse(Protocol):
    """Describe the response body iterator returned by Starlette middleware."""

    body_iterator: AsyncIterable[bytes]


def _is_json_content_type(content_type: str | None) -> bool:
    """Return whether a media type contains a JSON document."""
    media_type = (content_type or "").partition(";")[0].strip().casefold()
    return media_type == "application/json" or media_type.endswith("+json")


def mask_sensitive_json(value: Any) -> Any:
    """Recursively redact credentials and tokens from a JSON-compatible value."""
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).casefold().replace("-", "_")
            masked[str(key)] = (
                _REDACTED
                if any(part in normalized_key for part in _SENSITIVE_FIELD_PARTS)
                else mask_sensitive_json(item)
            )
        return masked
    if isinstance(value, list):
        return [mask_sensitive_json(item) for item in value]
    return value


def _parse_json_body(body: bytes) -> tuple[bool, Any]:
    """Decode and redact a JSON body without exposing malformed input."""
    if not body:
        return False, None
    try:
        return True, mask_sensitive_json(json.loads(body))
    except json.JSONDecodeError, UnicodeDecodeError:
        return False, None


def _content_length(headers: Any) -> int | None:
    """Read a valid content length from a header mapping when available."""
    try:
        return int(headers.get("content-length"))
    except TypeError, ValueError:
        return None


def resolve_request_id(value: str | None) -> str:
    """Return an incoming UUIDv7 request ID or generate a fresh one."""
    try:
        request_id = UUID(value) if value else None
    except ValueError:
        request_id = None
    if request_id is None or request_id.version != 7:
        request_id = uuid7()
    return str(request_id)


def normalize_user_agent(value: str | None) -> str | None:
    """Bound caller-controlled agent metadata to persisted column width."""
    return value[:1024] if value else None


def parse_client_date(value: str, reference_year: int | None = None) -> datetime | None:
    """Parse only the three HTTP-date forms allowed by RFC 9110."""
    if len(value) > 128 or not any(pattern.fullmatch(value) for pattern in _HTTP_DATE_FORMS):
        return None
    if _HTTP_DATE_FORMS[1].fullmatch(value):
        reference_year = reference_year or get_datetime_utc().year
        year_fragment = value.split("-", 2)[2][:2]
        year = (reference_year // 100) * 100 + int(year_fragment)
        if year > reference_year + 50:
            year -= 100
        elif year < reference_year - 50:
            year += 100
        value = value.replace(f"-{year_fragment} ", f"-{year:04d} ", 1)
    try:
        parsed = parsedate_to_datetime(value)
    except TypeError, ValueError, OverflowError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed = parsed.astimezone(UTC)
    if value.split()[0].rstrip(",")[:3] != _WEEKDAYS[parsed.weekday()]:
        return None
    return parsed


def observe_client_date(
    request: Request, received_at: datetime
) -> tuple[str, datetime | None, int | None]:
    """Return bounded status and signed apparent receipt-minus-client seconds."""
    values = request.headers.getlist("date")
    if not values:
        return "unavailable", None, None
    if len(values) != 1:
        return "invalid", None, None
    parsed = parse_client_date(values[0], received_at.year)
    if parsed is None:
        return "invalid", None, None
    return "available", parsed, round((received_at - parsed).total_seconds())


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log requests and responses while propagating a UUIDv7 request ID."""

    @override
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process one request and attach its correlation ID to the response."""
        request_id = resolve_request_id(request.headers.get("X-Request-ID"))
        received_at = get_datetime_utc()
        started_at = perf_counter()
        client_date_status, client_date, client_date_delta = observe_client_date(
            request, received_at
        )
        request.state.request_id = request_id
        user_agent = normalize_user_agent(request.headers.get("user-agent"))
        request.state.user_agent = user_agent
        language = resolve_language(request.headers.get("Accept-Language"))
        request.state.language = language
        language_token = set_language(language)
        span_context = trace.get_current_span().get_span_context()
        trace_id = f"{span_context.trace_id:032x}" if span_context.is_valid else None
        history_token = history_context.set(
            HistoryContext(
                request_id=request_id,
                trace_id=trace_id,
                reason=request.headers.get("X-Audit-Reason"),
                source_ip=request.client.host if request.client else None,
                user_agent=user_agent,
            )
        )
        bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        request_logger = logger.bind(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        try:
            request_fields: dict[str, Any] = {
                "content_length": request.headers.get("content-length"),
                "content_type": request.headers.get("content-type"),
                "user_agent": user_agent,
                "server_received_at": received_at.isoformat(),
                "client_date_status": client_date_status,
                "client_date": client_date.isoformat() if client_date else None,
                "client_date_delta_seconds": client_date_delta,
            }
            if _is_json_content_type(request.headers.get("content-type")):
                declared_length = _content_length(request.headers)
                if (
                    declared_length is not None
                    and declared_length > settings.HTTP_LOG_BODY_MAX_BYTES
                ):
                    request_fields["body_truncated"] = True
                else:
                    request_body = await request.body()
                    if len(request_body) > settings.HTTP_LOG_BODY_MAX_BYTES:
                        request_fields["body_truncated"] = True
                    else:
                        parsed, body = _parse_json_body(request_body)
                        if parsed:
                            request_fields["body"] = body

            await request_logger.ainfo("REQUEST", **request_fields)
            response = await call_next(request)

            streaming_response = cast(_StreamingBodyResponse, response)
            response_iterator = streaming_response.body_iterator
            response_is_json = _is_json_content_type(response.headers.get("content-type"))
            response_status = response.status_code

            async def body_with_logging() -> AsyncIterator[bytes]:
                """Forward response chunks while retaining a bounded JSON copy for logging."""
                captured = bytearray()
                body_truncated = False
                try:
                    async for chunk in response_iterator:
                        if response_is_json and not body_truncated:
                            if len(captured) + len(chunk) <= settings.HTTP_LOG_BODY_MAX_BYTES:
                                captured.extend(chunk)
                            else:
                                captured.clear()
                                body_truncated = True
                        yield chunk
                finally:
                    response_fields: dict[str, Any] = {
                        "status_code": response_status,
                        "processing_duration_ms": round((perf_counter() - started_at) * 1000, 3),
                    }
                    if body_truncated:
                        response_fields["body_truncated"] = True
                    elif response_is_json:
                        parsed, body = _parse_json_body(bytes(captured))
                        if parsed:
                            response_fields["body"] = body
                    await request_logger.ainfo("RESPONSE", **response_fields)

            streaming_response.body_iterator = body_with_logging()

        except Exception as e:
            await request_logger.acritical("UNHANDLED_ERROR", error=e)
            raise
        finally:
            history_context.reset(history_token)
            reset_language(language_token)
            clear_contextvars()

        response.headers["X-Request-ID"] = request_id
        response.headers["Content-Language"] = language
        cache_policy = response.headers.get("Cache-Control", "").lower()
        if "public" not in cache_policy and "s-maxage" not in cache_policy:
            response.headers["X-Client-Date-Status"] = client_date_status
            response.headers["X-Server-Received-At"] = received_at.isoformat().replace(
                "+00:00", "Z"
            )
            if client_date_delta is not None:
                response.headers["X-Client-Date-Delta-Seconds"] = str(client_date_delta)
                if abs(client_date_delta) >= settings.HTTP_CLIENT_DATE_ADVISORY_SECONDS:
                    response.headers["X-Client-Date-Advisory"] = "check-device-time"
            if "private" not in cache_policy and "no-store" not in cache_policy:
                existing_policy = response.headers.get("Cache-Control")
                response.headers["Cache-Control"] = (
                    f"private, {existing_policy}" if existing_policy else "private"
                )
        vary = {
            item.strip() for item in response.headers.get("Vary", "").split(",") if item.strip()
        }
        vary.add("Accept-Language")
        response.headers["Vary"] = ", ".join(sorted(vary))
        return response
