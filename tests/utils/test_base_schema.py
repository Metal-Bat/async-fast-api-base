"""Tests for shared HTTP headers and response schemas."""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from utils.base_schema import BaseHeaders, ErrorSchema, get_base_headers, response_schema


@pytest.mark.anyio
async def test_accept_language_header_uses_standard_name_and_falls_back() -> None:
    """Language negotiation binds the standard Accept-Language header."""
    app = FastAPI()

    @app.get("/")
    async def endpoint(
        headers: Annotated[BaseHeaders, Depends(get_base_headers)],
    ) -> dict[str, str | None]:
        return {"language": headers.language}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/", headers={"Accept-Language": "PERSIAN"})
        invalid = await client.get("/", headers={"Accept-Language": "INVALID"})
    assert response.json() == {"language": "fa"}
    assert invalid.json() == {"language": "en"}


@pytest.mark.anyio
async def test_base_headers_and_response_schema() -> None:
    headers = await get_base_headers(version="2", package_name="mobile", accept_language="ENGLISH")
    assert headers.version == "2" and headers.package_name == "mobile"
    assert headers.language == "en"
    assert headers.user_agent is None
    assert headers.request_id.version == 7
    explicit = await get_base_headers(user_agent="Native/2.0")
    assert explicit.user_agent == "Native/2.0"
    responses = response_schema(ErrorSchema)
    assert responses[200]["model"] is ErrorSchema
    assert all(code in responses for code in (400, 401, 403, 404, 422, 429))
