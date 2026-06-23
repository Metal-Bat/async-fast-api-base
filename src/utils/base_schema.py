from fastapi import Header
from pydantic import BaseModel, ConfigDict

from core.types import LanguagesTypes, PlatformTypes

ERROR_CODES = frozenset([400, 401, 403, 404, 422, 429])


class PaginatedResponse[T](BaseModel):
    items: list[T] = []
    total: int

    model_config = ConfigDict(from_attributes=True)


class BaseHeaders(BaseModel):
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

    user_agent: str = Header(
        default="1.0.0",
        alias="User-Agent",
        examples=["Mozilla"],
    )

    platform: PlatformTypes = Header(
        default=None,
        alias="Platform",
    )

    package_name: str = Header(
        default=None,
        alias="Package-Name",
    )

    language: LanguagesTypes = Header(
        default=None,
        alias="Language",
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
    platform: PlatformTypes = Header(
        default=None,
        alias="Platform",
    ),
    language: LanguagesTypes = Header(
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


class ErrorSchema(BaseModel):
    error_code: int = 1
    message: str = "Error"


def response_schema(
    success_schema: type[BaseModel] | None = None,
) -> dict[int | str, dict[str, type[BaseModel]]]:
    response_schema_format: dict[int | str, dict[str, type[BaseModel]]] = {}

    for code in ERROR_CODES:
        response_schema_format[code] = {"model": ErrorSchema}

    if success_schema is not None:
        response_schema_format[200] = {"model": success_schema}

    return response_schema_format
