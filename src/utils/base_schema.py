from typing import Annotated
from uuid import uuid7

from fastapi import Header, Request
from pydantic import UUID7, BaseModel, ConfigDict, Field

from core.i18n import _
from core.types import PlatformTypes
from utils.localization import resolve_language
from utils.middleware import normalize_user_agent
from utils.presenter import ErrorResponse

ERROR_CODES = frozenset([400, 401, 403, 404, 409, 413, 422, 423, 429, 500, 503])


class BaseHeaders(BaseModel):
    """Validated headers shared by versioned API endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    version: str = Header(
        default="1.0.0",
        alias="Version",
        examples=["1.0.0"],
    )

    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    )

    version_name: str | None = Header(
        default=None,
        alias="Version-Name",
        examples=["ALPHA"],
    )

    user_agent: str | None = Header(
        default=None,
        alias="User-Agent",
        description=_(
            "Optional caller-controlled client software identifier. Captured for diagnostics "
            "and audit, truncated to 1024 characters; never used for authorization or trusted "
            "client identity. Browsers supply their own value and may ignore manual overrides."
        ),
        examples=["MyNativeClient/2.3", "python-httpx/0.28.1"],
    )

    platform: PlatformTypes = Header(
        default=None,
        alias="Platform",
    )

    package_name: str = Header(
        default=None,
        alias="Package-Name",
    )

    language: str | None = Header(
        default=None,
        alias="Accept-Language",
    )

    request_id: UUID7 = Field(
        default_factory=uuid7,
        alias="X-Request-ID",
        description=_("UUIDv7 request correlation identifier."),
    )


async def get_base_headers(
    authorization: Annotated[
        str,
        Header(
            alias="Authorization",
        ),
    ] = "",
    version: Annotated[
        str,
        Header(
            alias="Version",
        ),
    ] = "1.0.0",
    version_name: Annotated[
        str,
        Header(
            alias="Version-Name",
        ),
    ] = "",
    package_name: Annotated[
        str,
        Header(
            alias="Package-Name",
        ),
    ] = "",
    platform: Annotated[
        PlatformTypes,
        Header(
            alias="Platform",
        ),
    ] = None,
    accept_language: Annotated[
        str | None,
        Header(
            alias="Accept-Language",
        ),
    ] = None,
    user_agent: Annotated[
        str | None,
        Header(alias="User-Agent"),
    ] = None,
    request_id: Annotated[
        UUID7 | None,
        Header(
            alias="X-Request-ID",
            description=_("Optional UUIDv7 correlation ID; generated when omitted."),
        ),
    ] = None,
) -> BaseHeaders:
    """Collect and validate headers shared by API endpoints.

    Returns:
        A normalized header model with a generated UUIDv7 request ID when omitted.
    """
    headers: BaseHeaders = BaseHeaders(
        authorization=authorization,
        version=version,
        version_name=version_name,
        package_name=package_name,
        platform=platform,
        language=resolve_language(accept_language),
        user_agent=normalize_user_agent(user_agent),
        request_id=request_id or uuid7(),
    )
    return headers


def get_request_user_agent(
    request: Request,
    user_agent: Annotated[
        str | None,
        Header(
            alias="User-Agent",
            description=_(
                "Optional caller-controlled client software identifier for audit and diagnostics; "
                "captured up to 1024 characters. Browsers supply their own value and may ignore "
                "manual Swagger overrides. Not trusted client identity or authorization."
            ),
            examples=["MyNativeClient/2.3", "python-httpx/0.28.1"],
        ),
    ] = None,
) -> None:
    """Expose the captured request metadata as a shared optional API input."""
    request.state.user_agent = normalize_user_agent(user_agent)


ErrorSchema = ErrorResponse


def response_schema(
    success_schema: type[BaseModel] | None = None,
) -> dict[int | str, dict[str, type[BaseModel]]]:
    """Build FastAPI response-model declarations for common status codes.

    Args:
        success_schema: Optional model returned for a successful response.

    Returns:
        A mapping suitable for a FastAPI route's ``responses`` argument.
    """
    response_schema_format: dict[int | str, dict[str, type[BaseModel]]] = {}

    for code in ERROR_CODES:
        response_schema_format[code] = {"model": ErrorSchema}

    if success_schema is not None:
        response_schema_format[200] = {"model": success_schema}

    return response_schema_format
