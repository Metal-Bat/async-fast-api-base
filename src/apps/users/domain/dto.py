from datetime import datetime
from typing import Any

from pydantic import AliasChoices, ConfigDict, EmailStr, Field, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from core.ref_id import create_ref_id
from utils.pagination import SearchRequest, auto_query_model


class UserCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(max_length=255, description=_("Unique username."))
    password: str = Field(min_length=8, description=_("Plaintext password accepted only as input."))
    is_superuser: bool = Field(default=False, description=_("Grant administrative privileges."))
    email: EmailStr | None = Field(default=None, description=_("Unique email address."))
    first_name: str | None = Field(default=None, max_length=255, description=_("Given name."))
    last_name: str | None = Field(default=None, max_length=255, description=_("Family name."))


class UserUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ref_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned user reference."),
    )
    username: str | None = Field(default=None, max_length=255, description=_("Unique username."))
    email: EmailStr | None = Field(default=None, description=_("Unique email address."))
    password: str | None = Field(
        default=None, min_length=8, description=_("Replacement plaintext password.")
    )
    is_superuser: bool | None = Field(default=None, description=_("Administrative privilege flag."))
    first_name: str | None = Field(default=None, max_length=255, description=_("Given name."))
    last_name: str | None = Field(default=None, max_length=255, description=_("Family name."))


class UserUpdatePasswordDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    old_password: str = Field(description=_("Current plaintext password."))
    new_password: str = Field(min_length=8, description=_("Replacement plaintext password."))


class UserDTO(BaseDTO):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned user reference."),
    )

    username: str = Field(description=_("Unique username."))
    email: EmailStr | None = Field(description=_("Unique email address."))

    created_at: datetime = Field(description=_("UTC creation timestamp."))
    updated_at: datetime | None = Field(description=_("UTC timestamp of the most recent update."))
    deleted_at: datetime | None = Field(description=_("UTC soft-deletion timestamp."))

    first_name: str | None = Field(default=None, description=_("Given name."))
    last_name: str | None = Field(default=None, description=_("Family name."))

    is_superuser: bool = Field(description=_("Administrative privilege flag."))
    is_active: bool = Field(description=_("Whether the user is not soft-deleted."))

    @model_validator(mode="before")
    @classmethod
    def create_public_reference(cls, value: Any) -> Any:
        if isinstance(value, dict):
            data = value.copy()
            if "refId" not in data and "ref_id" not in data:
                data["ref_id"] = create_ref_id(data.pop("id"), data.pop("version"))
            return data

        return {
            "ref_id": create_ref_id(value.id, value.version),
            "username": value.username,
            "email": value.email,
            "created_at": value.created_at,
            "updated_at": value.updated_at,
            "deleted_at": value.deleted_at,
            "first_name": value.first_name,
            "last_name": value.last_name,
            "is_superuser": value.is_superuser,
            "is_active": getattr(value, "is_active", value.deleted_at is None),
        }


class UserQuery(SearchRequest):
    __query_fields__ = auto_query_model(UserDTO, exclude={"ref_id", "is_active"}).__query_fields__
