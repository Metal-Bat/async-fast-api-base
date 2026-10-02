"""Tests for authentication presentation routes."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid7

import pytest
from fastapi import Request
from fastapi.security import OAuth2PasswordRequestFormStrict

from apps.users.domain.auth_dto import ChangePasswordDTO, LoginDTO, RefreshDTO, TokenPairDTO
from apps.users.domain.entity import UserEntity
from apps.users.presentation import login as routes
from core.settings import settings
from utils.exceptions import InvalidCredentialError
from utils.pagination import PageRequest


def request_context() -> Request:
    return Request({"type": "http", "headers": []})


def admin() -> UserEntity:
    return UserEntity(
        id=uuid7(), username=f"admin-{uuid7()}", hashed_password="hash", is_superuser=True
    )


@pytest.mark.anyio
async def test_authentication_routes_delegate_to_service() -> None:
    """Authentication endpoints pass validated data to their service."""
    service = Mock()
    assert isinstance(routes.get_auth_service(Mock()), routes.AuthService)
    pair = TokenPairDTO(access_token="access", refresh_token="refresh", expires_in=900)
    service.login = AsyncMock(return_value=pair)
    service.refresh = AsyncMock(return_value=pair)
    service.logout = AsyncMock()
    service.logout_all = AsyncMock()
    service.change_password = AsyncMock()
    request = Mock(spec=Request)
    request.state.request_id = "request"
    request.state.user_agent = "pytest"
    request.client = None
    request.headers = {"user-agent": "pytest"}
    user = admin()

    assert (await routes.login(LoginDTO(username="a", password="b"), request, service)).data == pair
    assert service.login.call_args.kwargs["user_agent"] == "pytest"
    assert (
        await routes.refresh(request_context(), RefreshDTO(refresh_token="r"), service)
    ).data == pair
    assert (
        await routes.logout(request_context(), RefreshDTO(refresh_token="r"), service)
    ).code == 204
    assert (await routes.logout_all(request_context(), user, service)).code == 204
    response = await routes.change_password(
        request_context(),
        ChangePasswordDTO(current_password="old", new_password="new-value"),
        user,
        service,
    )
    assert response.code == 204
    permission_result = Mock()
    permission_result.all.return_value = []
    permission_session = Mock()
    permission_session.exec = AsyncMock(return_value=permission_result)
    permissions = await routes.current_permissions(
        request_context(), PageRequest(), user, permission_session
    )
    assert permissions.result.items == ["*"]
    assert (await routes.me(request_context(), user)).data.username == user.username


@pytest.mark.anyio
async def test_swagger_token_uses_prefilled_client_credentials(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SWAGGER_CLIENT_ID", "swagger")
    monkeypatch.setattr(settings, "SWAGGER_CLIENT_SECRET", "swagger")
    form = OAuth2PasswordRequestFormStrict(
        grant_type="password",
        username="admin",
        password="admin",
        scope="",
        client_id="swagger",
        client_secret="swagger",
    )
    pair = TokenPairDTO(access_token="access", refresh_token="refresh", expires_in=900)
    service = Mock(login=AsyncMock(return_value=pair))
    request = Mock(spec=Request)
    request.state.request_id = "request"
    request.state.user_agent = "swagger"
    request.client = None
    request.headers = {"user-agent": "swagger"}

    assert await routes.token(form, request, service) == pair
    assert service.login.call_args.args[0] == LoginDTO(
        username="admin", password="admin", device_name="swagger"
    )

    form.client_secret = "wrong"
    with pytest.raises(InvalidCredentialError):
        await routes.token(form, request, service)
