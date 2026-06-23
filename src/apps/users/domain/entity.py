from pydantic import EmailStr
from sqlmodel import Field

from core.base_entity import BaseEntity


class UserEntity(BaseEntity, table=True):
    __tablename__ = "user"

    username: str = Field(unique=True, index=True, max_length=255)
    email: EmailStr | None = Field(unique=True, default=None, max_length=255)
    is_superuser: bool = False
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    hashed_password: str
