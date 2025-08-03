import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

logger = structlog.get_logger("json_logger")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        try:
            response: Response = await call_next(request)
        except Exception as e:
            await logger.acritical("UNHANDLED_ERROR", error=e)
            raise
        finally:
            clear_contextvars()

        response.headers["X-Request-ID"] = request_id
        return response
