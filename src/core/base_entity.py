from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import DateTime, Integer, Uuid, text
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, SQLModel

from core.i18n import _
from utils.date_utils import get_datetime_utc


class BaseEntity(SQLModel):
    __default_ordering__: ClassVar[tuple[str, ...]] = ("id",)

    id: UUID = Field(
        default=None,
        primary_key=True,
        nullable=False,
        description=_("Time-sortable UUIDv7 primary key."),
        sa_type=Uuid,
        sa_column_kwargs={
            "name": "ID",
            "comment": "TIME-SORTABLE UUIDV7 PRIMARY KEY.",
            "server_default": text("uuidv7()"),
        },
    )

    version: int = Field(
        default=1,
        nullable=False,
        description=_("Optimistic-lock version number."),
        sa_type=Integer,
        sa_column_kwargs={
            "name": "VERSION",
            "comment": "OPTIMISTIC-LOCK VERSION NUMBER.",
        },
    )

    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        nullable=False,
        index=True,
        description=_("UTC timestamp at which the row was created."),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "name": "CREATED_AT",
            "comment": "UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        },
    )

    updated_at: datetime | None = Field(
        default=None,
        nullable=True,
        description=_("UTC timestamp of the most recent update."),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "name": "UPDATED_AT",
            "comment": "UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        },
    )

    deleted_at: datetime | None = Field(
        default=None,
        nullable=True,
        description=_("UTC soft-deletion timestamp; null means the row is active."),
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "name": "DELETED_AT",
            "comment": "UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        },
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, object]:
        return {"version_id_col": cls.version}
