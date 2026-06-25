from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt import decode
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.users.domain.entity import UserEntity
from core.base_dto import TokenPayload
from core.settings import settings
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
    str(settings.DATABASE_DSN),
    echo=True,
    future=True,
)


reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")


SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: SessionDep, token: TokenDep) -> UserEntity:
    try:
        payload = decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        token_data = TokenPayload(**payload)

    except Exception:
        raise InvalidCredentialError("Could not validate credentials")

    user = await session.get(UserEntity, token_data.sub)

    if not user:
        raise UserNotFoundException("User not found")

    if user.deleted_at:
        raise InactiveUserException("Inactive user")

    return user


CurrentUser = Annotated[UserEntity, Depends(get_current_user)]


async def get_current_active_superuser(current_user: CurrentUser) -> UserEntity:
    if not current_user.is_superuser:
        raise NotAllowedException("The user doesn't have enough privileges")

    return current_user
