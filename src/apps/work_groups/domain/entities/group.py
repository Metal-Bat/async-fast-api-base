"""Normalized work-group and membership entities."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Index,
    String,
    text,
)
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table


class WorkGroupEntity(BaseEntity, table=True):
    __tablename__ = "WORK_GROUP"
    __table_args__ = (
        Index(
            "uq_WORK_GROUP_CODE_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index(
            "ix_WORK_GROUP_active_code",
            "IS_ACTIVE",
            "CODE",
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        CheckConstraint('length("CODE") > 0', name="ck_WORK_GROUP_code_nonempty"),
        CheckConstraint('length("NAME") > 0', name="ck_WORK_GROUP_name_nonempty"),
    )

    code: str = Field(
        sa_column=Column(
            "CODE",
            String(64),
            nullable=False,
        ),
    )
    name: str = Field(
        sa_column=Column(
            "NAME",
            String(255),
            nullable=False,
        ),
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(
            "DESCRIPTION",
            String(1024),
        ),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(
            "IS_ACTIVE",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )


WorkGroupHistoryTable = create_history_table(
    WorkGroupEntity.__table__,  # ty:ignore[unresolved-attribute]
    ondelete="RESTRICT",
    onupdate="RESTRICT",
)
Index(
    "ix_WORK_GROUP_HISTORY_entity_changed",
    WorkGroupHistoryTable.c.ENTITY_ID,
    WorkGroupHistoryTable.c.CHANGED_AT,
)
