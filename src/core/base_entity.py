from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from utils.date_utils import get_datetime_utc


class BaseEntity(SQLModel):
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # ty:ignore[invalid-argument-type]
    )

    updated_at: datetime | None = Field(
        default_factory=None,
        sa_type=DateTime(timezone=True),  # ty:ignore[invalid-argument-type]
    )

    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # ty:ignore[invalid-argument-type]
    )
