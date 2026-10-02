from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.application.service import ClientService
from apps.clients.domain.contracts import ClientContext
from apps.users.domain.auth_entity import AuthSessionEntity
from apps.users.domain.entity import UserEntity
from core.base_dto import TokenPayload
from core.cache_session import CacheInvalidatingSession
from core.history import HistoryContext, history_context, history_modifier
from core.observability import annotate_authenticated_user
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    InactiveUserException,
    InvalidCredentialError,
    NotAllowedException,
    UserNotFoundException,
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


engine = create_async_engine(
    settings.DATABASE_DSN,
    echo=False,
    hide_parameters=True,
    future=True,
)


reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


SessionFactory = async_sessionmaker(
    bind=engine,
    class_=CacheInvalidatingSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: SessionDep, token: TokenDep, request: Request) -> UserEntity:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
        if token_data.type != "access":
            raise InvalidCredentialError("Could not validate credentials")
        user_id = UUID(token_data.sub)
        session_id = UUID(token_data.sid)

    except jwt.PyJWTError, ValidationError, TypeError, ValueError:
        raise InvalidCredentialError("Could not validate credentials")

    user = await session.get(UserEntity, user_id)
    auth_session = await session.get(AuthSessionEntity, session_id)

    if not user or auth_session is None or auth_session.user_id != user.id:
        raise UserNotFoundException("User not found")

    if auth_session.revoked_at or auth_session.expires_at <= get_datetime_utc():
        raise InvalidCredentialError("Session is expired or revoked")

    if user.deleted_at:
        raise InactiveUserException("Inactive user")

    await ClientService(session).for_session(auth_session)
    request.state.auth_session_id = auth_session.id
    annotate_authenticated_user(user.id, user.username)
    history_modifier.set(("user", str(user.id)))
    current_history = history_context.get() or HistoryContext()
    history_context.set(
        HistoryContext(
            modifier_type="user",
            modifier_id=str(user.id),
            request_id=current_history.request_id,
            trace_id=current_history.trace_id,
            reason=current_history.reason,
            source_ip=current_history.source_ip,
            user_agent=current_history.user_agent,
        )
    )
    return user


CurrentUser = Annotated[UserEntity, Depends(get_current_user)]


async def get_current_active_superuser(current_user: CurrentUser) -> UserEntity:
    if not current_user.is_superuser:
        raise NotAllowedException("The user doesn't have enough privileges")

    return current_user


async def get_current_client_context(
    request: Request, session: SessionDep, user: CurrentUser
) -> ClientContext:
    """Resolve only the server-bound session client, never caller-supplied headers."""
    auth_session_id = getattr(request.state, "auth_session_id", None)
    auth_session = await session.get(AuthSessionEntity, auth_session_id)
    if auth_session is None or auth_session.user_id != user.id:
        raise InvalidCredentialError("Client session is unavailable")
    return await ClientService(session).for_session(auth_session)


ClientContextDep = Annotated[ClientContext, Depends(get_current_client_context)]
