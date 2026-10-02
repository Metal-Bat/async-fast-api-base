import structlog
from amqp.exceptions import AMQPError
from asyncpg.exceptions import PostgresError
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from utils import exceptions
from utils.errors import AuthError, CommonError, ErrorCode, InfrastructureError, MediaError
from utils.postgresql_errors import postgresql_constraint_name, postgresql_sqlstate
from utils.presenter import error_response, request_id

logger = structlog.get_logger(__name__)

EXCEPTION_ERRORS: dict[type[Exception], tuple[ErrorCode, int]] = {
    exceptions.ValidationDetailsException: (CommonError.VALIDATION_FAILED, 422),
    exceptions.ServiceUnavailableException: (CommonError.SERVICE_UNAVAILABLE, 503),
    SQLAlchemyError: (CommonError.INTERNAL_ERROR, 500),
    PostgresError: (CommonError.INTERNAL_ERROR, 500),
    RedisError: (InfrastructureError.CACHE_UNAVAILABLE, 503),
    BotoCoreError: (InfrastructureError.STORAGE_UNAVAILABLE, 503),
    ClientError: (InfrastructureError.STORAGE_UNAVAILABLE, 503),
    AMQPError: (InfrastructureError.BROKER_UNAVAILABLE, 503),
    exceptions.NotFoundException: (CommonError.NOT_FOUND, 404),
    exceptions.UserNotFoundException: (AuthError.USER_NOT_FOUND, 404),
    exceptions.NotAllowedException: (AuthError.NOT_ALLOWED, 403),
    exceptions.VersionConflictException: (CommonError.VERSION_CONFLICT, 409),
    exceptions.InvalidReferenceException: (CommonError.INVALID_REFERENCE, 422),
    exceptions.InvalidCredentialError: (AuthError.INVALID_CREDENTIALS, 401),
    exceptions.AccountLockedException: (AuthError.ACCOUNT_LOCKED, 423),
    exceptions.InvalidTokenException: (AuthError.INVALID_TOKEN, 401),
    exceptions.InactiveUserException: (AuthError.INACTIVE_USER, 401),
    exceptions.UploadTooLargeException: (MediaError.UPLOAD_TOO_LARGE, 413),
    exceptions.InvalidImageException: (MediaError.INVALID_IMAGE, 422),
    exceptions.InvalidFileException: (MediaError.INVALID_FILE, 422),
    exceptions.UploadRateLimitException: (MediaError.UPLOAD_RATE_LIMIT, 429),
}

_CLIENT_UNIQUE_CONSTRAINTS = frozenset(
    {
        "ix_USER_USERNAME",
        "ix_ROLE_NAME",
        "ix_PERMISSION_NAME",
        "USER_EMAIL_key",
        "uq_WORK_GROUP_CODE_active",
        "uq_FORM_DEFINITION_CODE_active",
        "uq_FORM_VERSION_number",
        "uq_INTEGRATION_CONNECTION_CODE_active",
    }
)


def _postgresql_public_error(exc: BaseException) -> tuple[ErrorCode, int]:
    """Map only known, safe SQLSTATE cases to client-facing failures."""
    sqlstate = postgresql_sqlstate(exc)
    if sqlstate == "23505" and postgresql_constraint_name(exc) in _CLIENT_UNIQUE_CONSTRAINTS:
        return InfrastructureError.DATA_CONFLICT, 409
    if sqlstate in {"40001", "40P01", "53300", "57P01"} or (
        sqlstate is not None and sqlstate.startswith("08")
    ):
        return InfrastructureError.DATABASE_UNAVAILABLE, 503
    return CommonError.INTERNAL_ERROR, 500


async def application_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map application exceptions to a safe enum identity and HTTP status."""
    if isinstance(exc, exceptions.ValidationDetailsException):
        return error_response(
            request, CommonError.VALIDATION_FAILED, status_code=422, data={"issues": exc.issues}
        )
    if isinstance(exc, SQLAlchemyError | PostgresError):
        error, status = _postgresql_public_error(exc)
        await logger.awarning(
            "database.failure",
            request_id=request_id(request),
            sqlstate=postgresql_sqlstate(exc) or "unknown",
            code=error.number,
        )
        return error_response(request, error, status_code=status)
    for cls in type(exc).__mro__:
        if issubclass(cls, Exception) and cls in EXCEPTION_ERRORS:
            error, status = EXCEPTION_ERRORS[cls]
            return error_response(request, error, status_code=status)
    return await unhandled_exception_handler(request, exc)


async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Preserve HTTP status and protocol headers while localizing the message."""
    error = {
        401: AuthError.INVALID_CREDENTIALS,
        403: AuthError.NOT_ALLOWED,
        404: CommonError.NOT_FOUND,
        409: CommonError.VERSION_CONFLICT,
        413: MediaError.UPLOAD_TOO_LARGE,
        422: CommonError.VALIDATION_FAILED,
        429: CommonError.RATE_LIMITED,
        503: CommonError.SERVICE_UNAVAILABLE,
    }.get(
        exc.status_code,
        CommonError.INTERNAL_ERROR if exc.status_code >= 500 else CommonError.INVALID_REQUEST,
    )
    return error_response(request, error, status_code=exc.status_code, headers=exc.headers)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Present validation failure without echoing passwords or other input values."""
    return error_response(request, CommonError.VALIDATION_FAILED, status_code=422)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures and return a safe localized error."""
    await logger.aerror("request.failed", path=request.url.path, exc_info=exc)
    return error_response(request, CommonError.INTERNAL_ERROR, status_code=500)


# Existing callers can use the named handlers while registration stays centralized.
not_found_exception_handler = application_exception_handler
version_conflict_exception_handler = application_exception_handler
invalid_reference_exception_handler = application_exception_handler
upload_exception_handler = application_exception_handler
authentication_exception_handler = application_exception_handler


def configure_exception_handlers(app: FastAPI) -> None:
    """Install the complete error contract with one call from the application entrypoint."""
    app.add_exception_handler(HTTPException, custom_http_exception_handler)  # ty:ignore[invalid-argument-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # ty:ignore[invalid-argument-type]
    for exception_type in EXCEPTION_ERRORS:
        app.add_exception_handler(exception_type, application_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
