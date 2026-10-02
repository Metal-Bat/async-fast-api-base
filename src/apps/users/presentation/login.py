import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestFormStrict
from pydantic import TypeAdapter
from sqlmodel import col

from apps.users.application.auth_service import AuthService
from apps.users.application.authorization import user_permissions
from apps.users.domain.auth_dto import (
    ChangePasswordDTO,
    ForgotPasswordDTO,
    LoginDTO,
    RefreshDTO,
    ResetPasswordDTO,
    SessionDTO,
    SessionQuery,
    TokenPairDTO,
)
from apps.users.domain.auth_entity import AuthSessionEntity
from apps.users.domain.dto import UserDTO
from apps.users.domain.entity import UserEntity
from core.deps import CurrentUser, SessionDep
from core.ref_id import open_ref_id
from core.settings import settings
from utils.base_schema import response_schema
from utils.date_utils import get_datetime_utc
from utils.exceptions import InvalidCredentialError, NotFoundException, VersionConflictException
from utils.middleware import normalize_user_agent
from utils.pagination import Page, PageRequest, paginate_entities, paginate_values
from utils.presenter import PageResponse, SuccessResponse, page_response, success_response

router = APIRouter(responses=response_schema(), prefix="/auth", tags=["auth"])


def get_auth_service(session: SessionDep) -> AuthService:
    """Build a request-scoped authentication service."""
    return AuthService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
OAuthForm = Annotated[OAuth2PasswordRequestFormStrict, Depends()]


def _request_metadata(request: Request) -> dict[str, str | None]:
    return {
        "request_id": getattr(request.state, "request_id", None),
        "ip_address": request.client.host if request.client else None,
        "user_agent": getattr(
            request.state, "user_agent", normalize_user_agent(request.headers.get("user-agent"))
        ),
    }


@router.post("/login", response_model=SuccessResponse[TokenPairDTO])
async def login(
    data: LoginDTO, request: Request, service: AuthServiceDep
) -> SuccessResponse[TokenPairDTO]:
    """Authenticate and establish a rotating device session."""
    return success_response(
        request,
        TypeAdapter(TokenPairDTO).validate_python(
            await service.login(data, **_request_metadata(request)), from_attributes=True
        ),
        code=200,
    )


@router.post("/token", response_model=TokenPairDTO)
async def token(form: OAuthForm, request: Request, service: AuthServiceDep) -> TokenPairDTO:
    expected_id = settings.SWAGGER_CLIENT_ID or ""
    expected_secret = settings.SWAGGER_CLIENT_SECRET or ""
    valid_client = bool(expected_id and expected_secret)
    valid_client &= hmac.compare_digest(form.client_id or "", expected_id)
    valid_client &= hmac.compare_digest(form.client_secret or "", expected_secret)
    if not valid_client:
        raise InvalidCredentialError("Invalid OAuth client credentials")

    return TypeAdapter(TokenPairDTO).validate_python(
        await service.login(
            LoginDTO(username=form.username, password=form.password, device_name="swagger"),
            **_request_metadata(request),
        ),
        from_attributes=True,
    )


@router.post("/refresh", response_model=SuccessResponse[TokenPairDTO])
async def refresh(
    request: Request, data: RefreshDTO, service: AuthServiceDep
) -> SuccessResponse[TokenPairDTO]:
    """Rotate a refresh token and issue a new access token."""
    return success_response(
        request,
        TypeAdapter(TokenPairDTO).validate_python(
            await service.refresh(data.refresh_token), from_attributes=True
        ),
        code=200,
    )


@router.post("/logout", status_code=200)
async def logout(
    request: Request, data: RefreshDTO, service: AuthServiceDep
) -> SuccessResponse[None]:
    """Revoke one device session."""
    await service.logout(data.refresh_token)
    return success_response(request, None, code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=200)
async def logout_all(
    request: Request, user: CurrentUser, service: AuthServiceDep
) -> SuccessResponse[None]:
    """Revoke all device sessions owned by the current user."""
    await service.logout_all(user.id)
    return success_response(request, None, code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    request: Request, data: ForgotPasswordDTO
) -> SuccessResponse[dict[str, str]]:
    """Direct users to administrator-assisted recovery without revealing account existence."""
    return success_response(
        request,
        {"detail": "Contact an administrator to reset your password."},
        code=status.HTTP_202_ACCEPTED,
    )


@router.post("/reset-password", status_code=200)
async def reset_password(
    request: Request, data: ResetPasswordDTO, service: AuthServiceDep
) -> SuccessResponse[None]:
    """Consume a password-reset token and revoke existing sessions."""
    await service.reset_password(data.token, data.new_password)
    return success_response(request, None, code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=200)
async def change_password(
    request: Request, data: ChangePasswordDTO, user: CurrentUser, service: AuthServiceDep
) -> SuccessResponse[None]:
    """Replace the current user's password and revoke existing sessions."""
    await service.change_password(user, data.current_password, data.new_password)
    return success_response(request, None, code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=SuccessResponse[UserDTO])
async def me(request: Request, user: CurrentUser) -> SuccessResponse[UserDTO]:
    """Return the authenticated user's public profile."""
    return success_response(
        request, TypeAdapter(UserDTO).validate_python(user, from_attributes=True), code=200
    )


@router.post("/sessions/search", response_model=PageResponse[Page[SessionDTO]])
async def list_sessions(
    request: Request, query: SessionQuery, user: CurrentUser, session: SessionDep
) -> PageResponse[Page[SessionDTO]]:
    """Return a filtered page of active sessions for the current user."""
    page = await paginate_entities(
        session,
        AuthSessionEntity,
        query,
        criteria=(
            AuthSessionEntity.user_id == user.id,
            col(AuthSessionEntity.revoked_at).is_(None),
        ),
    )
    return page_response(
        request, TypeAdapter(Page[SessionDTO]).validate_python(page, from_attributes=True)
    )


@router.post("/sessions/report", response_model=PageResponse[Page[SessionDTO]])
async def report_sessions(
    request: Request, query: SessionQuery, user: CurrentUser, session: SessionDep
) -> PageResponse[Page[SessionDTO]]:
    """Return sessions using the same filters and page contract as search."""
    return await list_sessions(request, query, user, session)


async def _owned_session(ref_id: str, user: UserEntity, session: SessionDep) -> AuthSessionEntity:
    session_id = open_ref_id(ref_id)[0]
    auth_session = await session.get(AuthSessionEntity, session_id)
    if auth_session is None or auth_session.user_id != user.id:
        raise NotFoundException("Session not found")
    return auth_session


@router.get("/sessions/{ref_id}", response_model=SuccessResponse[SessionDTO])
async def get_session(
    request: Request, ref_id: str, user: CurrentUser, session: SessionDep
) -> SuccessResponse[SessionDTO]:
    """Return one device session owned by the current user."""
    auth_session = await _owned_session(ref_id, user, session)
    return success_response(
        request, TypeAdapter(SessionDTO).validate_python(auth_session, from_attributes=True)
    )


@router.post("/permissions/search", response_model=PageResponse[Page[str]])
async def current_permissions(
    request: Request, query: PageRequest, user: CurrentUser, session: SessionDep
) -> PageResponse[Page[str]]:
    """Return one page of permission scopes granted through roles."""
    return page_response(
        request, paginate_values(sorted(await user_permissions(user, session)), query)
    )


@router.post("/permissions/report", response_model=PageResponse[Page[str]])
async def report_current_permissions(
    request: Request, query: PageRequest, user: CurrentUser, session: SessionDep
) -> PageResponse[Page[str]]:
    """Return current permissions using the shared report envelope."""
    return await current_permissions(request, query, user, session)


@router.delete("/sessions/{ref_id}", status_code=200)
async def revoke_session(
    request: Request,
    ref_id: str,
    user: CurrentUser,
    session: SessionDep,
    service: AuthServiceDep,
) -> SuccessResponse[None]:
    """Revoke one device session owned by the current user."""
    session_id, version = open_ref_id(ref_id)
    auth_session = await _owned_session(ref_id, user, session)
    if auth_session.version != version:
        raise VersionConflictException("Session version is stale")
    auth_session.revoked_at = get_datetime_utc()
    session.add(auth_session)
    await service.audit("session.revoked", user_id=user.id, details={"session_id": str(session_id)})
    await session.commit()
    return success_response(request, None, code=status.HTTP_204_NO_CONTENT)
