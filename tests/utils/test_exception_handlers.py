"""Tests for HTTP exception presentation."""

import json
from collections.abc import Awaitable, Callable
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException

import utils.exception_handlers as handlers
from utils.errors import CommonError, InfrastructureError
from utils.exceptions import (
    InvalidReferenceException,
    NotFoundException,
    UploadTooLargeException,
    VersionConflictException,
)


def request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/test", "headers": []})


@pytest.mark.anyio
async def test_exception_handlers_return_safe_statuses(monkeypatch) -> None:
    logger = AsyncMock()
    monkeypatch.setattr(handlers, "logger", logger)
    cases = [
        (handlers.custom_http_exception_handler, HTTPException(418, "secret"), 418, 1001),
        (handlers.not_found_exception_handler, NotFoundException("missing"), 404, 1003),
        (handlers.version_conflict_exception_handler, VersionConflictException("stale"), 409, 1004),
        (handlers.invalid_reference_exception_handler, InvalidReferenceException("bad"), 422, 1005),
        (handlers.unhandled_exception_handler, RuntimeError("secret"), 500, 1099),
        (handlers.upload_exception_handler, UploadTooLargeException("large"), 413, 3001),
    ]
    for handler, error, status, code in cases:
        generic_handler = cast(Callable[[Request, Exception], Awaitable[Any]], handler)
        response = await generic_handler(request(), error)
        assert response.status_code == status
        assert json.loads(bytes(response.body))["code"] == code


@pytest.mark.anyio
async def test_validation_handler_returns_safe_localized_envelope(monkeypatch) -> None:
    monkeypatch.setattr(handlers, "logger", AsyncMock())
    error = RequestValidationError(
        [{"type": "missing", "loc": ("body", "name"), "msg": "Required"}]
    )
    response = await handlers.validation_exception_handler(request(), error)
    assert response.status_code == 422
    body = json.loads(bytes(response.body))
    assert body["code"] == 1002
    assert body["error"] == "Request validation failed."
    assert body["data"] is None


@pytest.mark.anyio
async def test_document_validation_details_preserve_safe_error_envelope() -> None:
    from utils.exceptions import ServiceUnavailableException, ValidationDetailsException

    issues = [{"pointer": "/data_schema/type", "code": "schema.invalid"}]
    response = await handlers.application_exception_handler(
        request(), ValidationDetailsException(issues)
    )
    body = json.loads(bytes(response.body))
    assert response.status_code == 422 and body["code"] == 1002
    assert body["data"] == {"issues": issues}
    response = await handlers.application_exception_handler(
        request(), ServiceUnavailableException("private provider exception")
    )
    assert response.status_code == 503 and b"private" not in bytes(response.body)


class DriverError(Exception):
    def __init__(self, sqlstate: str, constraint_name: str | None = None) -> None:
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name
        super().__init__("secret database details")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("sqlstate", "constraint", "expected_status", "expected_code"),
    [
        ("23505", "ix_USER_USERNAME", 409, InfrastructureError.DATA_CONFLICT.number),
        ("23505", "uq_WORK_GROUP_CODE_active", 409, InfrastructureError.DATA_CONFLICT.number),
        ("23505", "uq_FORM_DEFINITION_CODE_active", 409, InfrastructureError.DATA_CONFLICT.number),
        ("23505", "uq_FORM_VERSION_number", 409, InfrastructureError.DATA_CONFLICT.number),
        (
            "23505",
            "uq_INTEGRATION_CONNECTION_CODE_active",
            409,
            InfrastructureError.DATA_CONFLICT.number,
        ),
        ("23505", "private_unknown_key", 500, CommonError.INTERNAL_ERROR.number),
        ("23503", None, 500, CommonError.INTERNAL_ERROR.number),
        ("40001", None, 503, InfrastructureError.DATABASE_UNAVAILABLE.number),
        ("40P01", None, 503, InfrastructureError.DATABASE_UNAVAILABLE.number),
        ("08006", None, 503, InfrastructureError.DATABASE_UNAVAILABLE.number),
        ("23502", None, 500, CommonError.INTERNAL_ERROR.number),
        ("23514", None, 500, CommonError.INTERNAL_ERROR.number),
        ("XX999", None, 500, CommonError.INTERNAL_ERROR.number),
    ],
)
async def test_wrapped_postgresql_failures_have_safe_public_codes(
    monkeypatch, sqlstate, constraint, expected_status, expected_code
) -> None:
    monkeypatch.setattr(handlers, "logger", AsyncMock())
    error = IntegrityError(
        "secret query", {"password": "secret"}, DriverError(sqlstate, constraint)
    )
    response = await handlers.application_exception_handler(request(), error)
    body = json.loads(bytes(response.body))

    assert response.status_code == expected_status
    assert body["code"] == expected_code
    assert "secret" not in bytes(response.body).decode()
    assert sqlstate not in bytes(response.body).decode()


@pytest.mark.anyio
async def test_unknown_sqlalchemy_failure_is_internal_error(monkeypatch) -> None:
    monkeypatch.setattr(handlers, "logger", AsyncMock())
    error = OperationalError("secret query", None, DriverError("XX999"))
    response = await handlers.application_exception_handler(request(), error)
    assert response.status_code == 500
    assert json.loads(bytes(response.body))["code"] == CommonError.INTERNAL_ERROR.number
