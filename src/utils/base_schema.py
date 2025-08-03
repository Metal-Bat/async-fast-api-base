from typing import Literal

from fastapi import Header
from pydantic import BaseModel


class BaseHeaders(BaseModel):
    version: str = Header(
        default="1.0.0",
        alias="Version",
        example="1.0.0",
    )
    version_name: str | None = Header(
        default=None,
        alias="Version-Name",
        example="ALPHA",
    )
    user_agent: str = Header(
        default="1.0.0",
        alias="User-Agent",
        example="Mozilla",
    )
    platform: Literal["ANDROID", "IOS", "PWA", None] = Header(
        default=None,
        alias="Platform",
    )
    language: Literal["ENGLISH", "PERSIAN", "ARABIC", "TURKISH", None] = (
        Header(  # noqa: E501
            default=None,
            alias="Language",
        )
    )


async def get_base_headers(
    authorization: str = Header(
        default="",
        alias="Authorization",
    ),
    version: str = Header(
        default="1.0.0",
        alias="Version",
    ),
    version_name: str = Header(
        default="",
        alias="Version-Name",
    ),
    package_name: str = Header(
        default="",
        alias="Package-Name",
    ),
    platform: Literal["ANDROID", "IOS", "PWA"] | None = Header(  # noqa: E501
        default=None,
        alias="Platform",
    ),
    language: (
        Literal["ENGLISH", "PERSIAN", "ARABIC", "TURKISH"] | None
    ) = Header(  # noqa: E501
        default=None,
        alias="Language",
    ),
) -> BaseHeaders:
    headers: BaseHeaders = BaseHeaders(
        authorization=authorization,
        version=version,
        version_name=version_name,
        package_name=package_name,
        platform=platform,
        language=language,
    )
    return headers


ERROR_CODES = frozenset([400, 401, 403, 404, 422, 429])


class ErrorSchema(BaseModel):
    error_code: int = 1
    message: str = "Error"


def response_schema(
    success_schema: BaseModel | None = None,
) -> dict[int, BaseModel]:
    response_schema_format = {code: {"model": ErrorSchema} for code in ERROR_CODES}
    if success_schema is not None:
        response_schema_format[200] = {"model": success_schema}
    return response_schema_format
