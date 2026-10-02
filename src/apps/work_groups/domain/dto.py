"""Snake-case work-group HTTP contracts."""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from apps.users.domain.dto import UserQuery
from core.base_dto import BaseDTO
from core.ref_id import create_ref_id
from utils.pagination import SearchRequest, auto_query_model
from utils.select import SelectOption


class WorkGroupCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    is_active: bool = True


class WorkGroupUpdateDTO(WorkGroupCreateDTO):
    """Full replacement of client-managed group fields."""


class WorkGroupDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    ref_id: str
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None

    @model_validator(mode="before")
    @classmethod
    def add_ref_id(cls, value: Any) -> Any:
        if isinstance(value, dict):
            data = value.copy()
            if "ref_id" not in data:
                data["ref_id"] = create_ref_id(data.pop("id"), data.pop("version"))
            return data
        return {name: getattr(value, name) for name in cls.model_fields if name != "ref_id"} | {
            "ref_id": create_ref_id(value.id, value.version)
        }


class WorkGroupQuery(SearchRequest):
    __query_fields__ = auto_query_model(WorkGroupDTO, exclude={"ref_id"}).__query_fields__


class WorkGroupSelectQuery(WorkGroupQuery):
    """Selector search with administrator-only lifecycle overrides."""

    include_inactive: bool = False
    include_deleted: bool = False


class UserSelectQuery(UserQuery):
    """User selector search with an administrator-only deletion override."""

    include_deleted: bool = False


class MemberChangeDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    user_ref_id: str


class WorkGroupSelectDTO(SelectOption[str]):
    """Resource select option using the shared wire contract."""
