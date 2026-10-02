"""Normalized step identities, pinned handler versions, and typed ports."""

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


class StepTypeEntity(BaseEntity, table=True):
    __tablename__ = "STEP_TYPE"
    __table_args__ = (
        Index(
            "uq_STEP_TYPE_CODE_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index("ix_STEP_TYPE_enabled_code", "IS_ENABLED", "CODE"),
        CheckConstraint('length("CODE") > 0', name="ck_STEP_TYPE_code"),
        CheckConstraint('length("NAME") > 0', name="ck_STEP_TYPE_name"),
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
    is_enabled: bool = Field(
        default=True,
        sa_column=Column(
            "IS_ENABLED",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )


StepTypeHistoryTable = create_history_table(
    StepTypeEntity.__table__,  # ty:ignore[unresolved-attribute]
    ondelete="RESTRICT",
    onupdate="RESTRICT",
)
Index(
    "ix_STEP_TYPE_HISTORY_entity_changed",
    StepTypeHistoryTable.c.ENTITY_ID,
    StepTypeHistoryTable.c.CHANGED_AT,
)
