import structlog
from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger("json_logger")


async def custom_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    await logger.awarning(
        "HTTP_EXCEPTION",
        status=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
        method=request.method,
    )
    response = await http_exception_handler(request, exc)
    return response


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    await logger.awarning(
        "VALIDATION_ERROR",
        errors=exc.errors(),
        path=request.url.path,
        method=request.method,
    )
    response = JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
        },
    )
    return response


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    await logger.acritical(
        "UNHANDLED_EXCEPTION",
        path=request.url.path,
        method=request.method,
        exception=str(exc),
        exc_info=True,
    )
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )
    return response
