from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from core.ref_id import create_ref_id
from utils.pagination import SearchRequest, auto_query_model


class LoginDTO(BaseDTO):
    username: str = Field(max_length=255)
    password: str
    device_name: str | None = Field(default=None, max_length=255)
    client_key: str | None = Field(default=None, max_length=64)
    client_secret: str | None = Field(default=None, max_length=128)
    client_release: str | None = Field(default=None, max_length=64)


class TokenPairDTO(BaseDTO):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshDTO(BaseDTO):
    refresh_token: str


class ForgotPasswordDTO(BaseDTO):
    username_or_email: str


class ResetPasswordDTO(BaseDTO):
    token: str
    new_password: str = Field(min_length=8)


class ChangePasswordDTO(BaseDTO):
    current_password: str
    new_password: str = Field(min_length=8)


class SessionDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned session reference."),
    )
    device_name: str | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime

    @model_validator(mode="before")
    @classmethod
    def create_public_reference(cls, value: Any) -> Any:
        if isinstance(value, dict):
            data = value.copy()
            if "refId" not in data and "ref_id" not in data:
                data["ref_id"] = create_ref_id(data.pop("id"), data.pop("version"))
            return data
        return {field: getattr(value, field) for field in cls.model_fields if field != "ref_id"} | {
            "ref_id": create_ref_id(value.id, value.version)
        }


class SessionQuery(SearchRequest):
    __query_fields__ = auto_query_model(SessionDTO, exclude={"ref_id"}).__query_fields__


class PermissionDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned permission reference."),
    )
    name: str = Field(max_length=255)
    description: str | None = None
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None

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
            "name": value.name,
            "description": value.description,
            "created_at": value.created_at,
            "updated_at": value.updated_at,
            "deleted_at": value.deleted_at,
        }


class PermissionCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=255)
    description: str | None = None


class PermissionUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=255)
    description: str | None = None


class PermissionQuery(SearchRequest):
    __query_fields__ = auto_query_model(PermissionDTO, exclude={"ref_id"}).__query_fields__


class AuthAuditEventDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned audit-event reference."),
    )
    user_id: UUID | None
    event_type: str
    success: bool
    request_id: str | None
    ip_address: str | None
    user_agent: str | None
    details: dict[str, object]
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def create_public_reference(cls, value: Any) -> Any:
        if isinstance(value, dict):
            data = value.copy()
            if "refId" not in data and "ref_id" not in data:
                data["ref_id"] = create_ref_id(data.pop("id"), data.pop("version"))
            return data
        return {field: getattr(value, field) for field in cls.model_fields if field != "ref_id"} | {
            "ref_id": create_ref_id(value.id, value.version)
        }


class AuthAuditEventQuery(SearchRequest):
    __query_fields__ = auto_query_model(
        AuthAuditEventDTO, exclude={"ref_id", "details"}
    ).__query_fields__


class RoleDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned role reference."),
    )
    name: str = Field(max_length=255)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None


class RoleCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=255)
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    permissions: list[str] | None = None


class RoleQuery(SearchRequest):
    __query_fields__ = auto_query_model(RoleDTO, exclude={"ref_id", "permissions"}).__query_fields__


class AssignRoleDTO(BaseDTO):
    role_name: str


class AdminResetPasswordDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    new_password: str = Field(min_length=8)
