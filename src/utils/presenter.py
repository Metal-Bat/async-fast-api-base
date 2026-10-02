from collections.abc import Mapping
from typing import Literal

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import ConfigDict

from core.base_dto import BaseDTO
from utils.errors import ErrorCode
from utils.localization import localize_error, resolve_language
from utils.middleware import resolve_request_id
from utils.pagination import Page
from utils.select import SelectResponseFormat


class SuccessResponse[T](BaseDTO):
    """Successful response containing a typed payload."""

    model_config = ConfigDict(populate_by_name=True)
    success: Literal[True] = True
    request_id: str
    error: None = None
    code: int = 200
    data: T


class ErrorResponse(BaseDTO):
    """Localized failure with a stable application error number."""

    model_config = ConfigDict(populate_by_name=True)
    success: Literal[False] = False
    request_id: str
    error: str
    code: int
    data: dict[str, object] | None = None


class PageResponse[T](BaseDTO):
    """Successful page under the Go presenter's result field."""

    model_config = ConfigDict(populate_by_name=True)
    success: Literal[True] = True
    request_id: str
    error: None = None
    code: int = 200
    result: T


def request_id(request: Request) -> str:
    """Reuse the middleware correlation ID or initialize it for a standalone app."""
    if not getattr(request.state, "request_id", None):
        request.state.request_id = resolve_request_id(request.headers.get("X-Request-ID"))
    return str(request.state.request_id)


def success_response[T](request: Request, data: T, *, code: int = 200) -> SuccessResponse[T]:
    """Wrap a public DTO or select option list in a success envelope."""
    return SuccessResponse(request_id=request_id(request), data=data, code=code)


def page_response[T](request: Request, page: T) -> PageResponse[T]:
    """Wrap a validated page as the result of a successful search."""
    return PageResponse(request_id=request_id(request), result=page)


def select_response[T](
    request: Request, page: Page[T], response_format: SelectResponseFormat
) -> PageResponse[Page[T]] | list[T]:
    """Present the same authorized, bounded page with or without its metadata."""
    return page.items if response_format == "items" else page_response(request, page)


def error_response(
    request: Request,
    error: ErrorCode,
    *,
    status_code: int = 422,
    headers: Mapping[str, str] | None = None,
    data: dict[str, object] | None = None,
) -> JSONResponse:
    """Localize an enum error without exposing exception text or request inputs."""
    language = resolve_language(request.headers.get("Accept-Language"))
    body = ErrorResponse(
        request_id=request_id(request),
        error=localize_error(error, language),
        code=error.number,
        data=data,
    )
    response_headers = {**(headers or {}), "X-Request-ID": body.request_id}
    response_headers["Content-Language"] = language
    vary = {item.strip() for item in response_headers.get("Vary", "").split(",") if item.strip()}
    vary.add("Accept-Language")
    response_headers["Vary"] = ", ".join(sorted(vary))
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers=response_headers,
    )


def private_no_store(response: Response) -> None:
    """Prevent reuse of protected documents across actors, clients or locales."""
    response.headers["Cache-Control"] = "private, no-store"
