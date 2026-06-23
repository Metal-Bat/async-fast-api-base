from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from utils.pagination import auto_query_model


class UserCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str
    is_active: bool = True
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None


class UserUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class UserUpdatePasswordDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_password: str
    new_password: str


class UserDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: UUID

    email: EmailStr

    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None

    first_name: str | None = None
    last_name: str | None = None

    is_active: bool


UserQuery = auto_query_model(UserDTO)
