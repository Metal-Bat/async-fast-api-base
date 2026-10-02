"""Tests for response-envelope presenters."""

from unittest.mock import AsyncMock
from uuid import uuid7

import pytest
from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient
from pydantic import TypeAdapter

from apps.users.application.service import get_user_service
from apps.users.domain.dto import UserDTO
from apps.users.domain.entity import UserEntity
from apps.users.presentation.admin import router
from core.deps import get_current_user, get_db
from utils.errors import AuthError, CommonError
from utils.exception_handlers import configure_exception_handlers
from utils.exceptions import InvalidCredentialError
from utils.localization import localize_error
from utils.pagination import Page, SortOperation
from utils.presenter import SuccessResponse, success_response
from utils.select import SelectOption, select_options


@pytest.mark.anyio
async def test_search_returns_go_page_envelope_and_filters_private_fields() -> None:
    app = FastAPI()
    app.include_router(router)
    service = AsyncMock()
    visible = UserEntity(id=uuid7(), username="visible", hashed_password="private-secret")
    service.list_public.return_value = Page(
        items=[TypeAdapter(UserDTO).validate_python(visible, from_attributes=True)],
        page=2,
        size=10,
        total=21,
    )

    async def override_service():
        return service

    async def authenticated_admin():
        return UserEntity(id=uuid7(), username="admin", hashed_password="hash", is_superuser=True)

    async def database():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = authenticated_admin
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_user_service] = override_service
    correlation = str(uuid7())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/admin/users/search",
            json={"page": 2, "size": 10},
            headers={"X-Request-ID": correlation},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"success", "request_id", "error", "code", "result"}
    assert body["request_id"] == correlation
    assert body["success"] is True and body["error"] is None
    assert body["result"]["total_pages"] == 3
    assert body["result"]["page"] == 2 and body["result"]["size"] == 10
    assert body["result"]["items"][0]["username"] == "visible"
    assert "private-secret" not in response.text
    assert "hashed_password" not in response.text

    service.get_public_by_id.return_value = service.list_public.return_value.items[0]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        detail = await client.get("/admin/users/reference")
    assert detail.status_code == 200
    assert detail.json()["data"]["username"] == "visible"


@pytest.mark.anyio
async def test_error_handler_localizes_and_preserves_http_headers() -> None:
    app = FastAPI()
    configure_exception_handlers(app)

    @app.get("/auth")
    async def auth() -> None:
        raise HTTPException(401, "private-secret", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/failure")
    async def failure() -> None:
        raise InvalidCredentialError("private-secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        expected_codes = {
            "/auth": AuthError.INVALID_CREDENTIALS.number,
            "/failure": AuthError.INVALID_CREDENTIALS.number,
            "/unknown": CommonError.NOT_FOUND.number,
        }
        for path, expected_code in expected_codes.items():
            response = await client.get(path, headers={"Accept-Language": "fa-IR"})
            body = response.json()
            assert set(body) == {"success", "request_id", "error", "code", "data"}
            assert body["success"] is False and body["data"] is None
            assert body["code"] == expected_code
            assert body["request_id"] == response.headers["X-Request-ID"]
            assert "private-secret" not in response.text
            if path == "/auth":
                assert response.headers["WWW-Authenticate"] == "Bearer"
            if path == "/unknown":
                assert response.status_code == 404
                assert body["error"] == localize_error(CommonError.NOT_FOUND, "fa")


@pytest.mark.anyio
async def test_select_options_are_success_data() -> None:
    app = FastAPI()

    @app.get("/options")
    async def options(request: Request) -> SuccessResponse[list[SelectOption[SortOperation]]]:
        return success_response(request, select_options(*SortOperation))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/options")
    assert response.json()["data"] == [
        {"key": "asc", "value": "asc"},
        {"key": "desc", "value": "desc"},
    ]
