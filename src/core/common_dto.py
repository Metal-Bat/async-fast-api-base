from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO
from core.i18n import _


class EntityReadDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID = Field(description=_("Time-sortable UUIDv7 primary key."))
    version: int = Field(description=_("Optimistic-lock version number."))
    created_at: datetime = Field(description=_("UTC creation timestamp."))
    updated_at: datetime | None = Field(description=_("UTC timestamp of the most recent update."))
    deleted_at: datetime | None = Field(description=_("UTC soft-deletion timestamp."))


class SlugCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=255, description=_("Human-readable title."))
    slug: str = Field(max_length=255, description=_("URL-safe identifier."))
    description: str | None = Field(default=None, description=_("Optional long-form description."))


class SlugUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255, description=_("Human-readable title."))
    slug: str | None = Field(default=None, max_length=255, description=_("URL-safe identifier."))
    description: str | None = Field(default=None, description=_("Optional long-form description."))
    version: int = Field(description=_("Version expected by the caller."))


class SlugDTO(EntityReadDTO, SlugCreateDTO):
    pass


class OrderCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=255, description=_("Human-readable title."))
    description: str | None = Field(default=None, description=_("Optional long-form description."))
    order_id: int = Field(description=_("User-controlled ordering position."))


class OrderUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=255, description=_("Human-readable title."))
    description: str | None = Field(default=None, description=_("Optional long-form description."))
    order_id: int | None = Field(default=None, description=_("User-controlled ordering position."))
    version: int = Field(description=_("Version expected by the caller."))


class OrderDTO(EntityReadDTO, OrderCreateDTO):
    pass
