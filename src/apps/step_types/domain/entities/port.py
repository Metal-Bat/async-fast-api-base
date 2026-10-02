"""Normalized step identities, pinned handler versions, and typed ports."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from utils.date_utils import get_datetime_utc


class StepTypePortEntity(SQLModel, table=True):
    __tablename__ = "STEP_TYPE_PORT"
    __table_args__ = (
        UniqueConstraint(
            "STEP_TYPE_VERSION_ID", "DIRECTION", "PORT_KEY", name="uq_STEP_TYPE_PORT_key"
        ),
        Index("ix_STEP_TYPE_PORT_version_direction", "STEP_TYPE_VERSION_ID", "DIRECTION"),
        CheckConstraint("\"DIRECTION\" IN ('INPUT', 'OUTPUT')", name="ck_STEP_TYPE_PORT_direction"),
        CheckConstraint(
            "\"CARDINALITY\" IN ('SCALAR', 'LIST')", name="ck_STEP_TYPE_PORT_cardinality"
        ),
        CheckConstraint('length("PORT_KEY") > 0', name="ck_STEP_TYPE_PORT_key"),
        CheckConstraint(
            "jsonb_typeof(\"VALUE_SCHEMA\") = 'object'", name="ck_STEP_TYPE_PORT_schema"
        ),
    )

    id: UUID = Field(
        default=None,
        sa_column=Column(
            "ID",
            Uuid,
            primary_key=True,
            server_default=text("uuidv7()"),
        ),
    )
    step_type_version_id: UUID = Field(
        sa_column=Column(
            "STEP_TYPE_VERSION_ID",
            Uuid,
            ForeignKey(
                "STEP_TYPE_VERSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    direction: str = Field(
        sa_column=Column(
            "DIRECTION",
            String(8),
            nullable=False,
        ),
    )
    port_key: str = Field(
        sa_column=Column(
            "PORT_KEY",
            String(64),
            nullable=False,
        ),
    )
    value_schema: dict[str, Any] = Field(
        sa_column=Column(
            "VALUE_SCHEMA",
            JSONB,
            nullable=False,
        ),
    )
    required: bool = Field(
        sa_column=Column(
            "REQUIRED",
            Boolean,
            nullable=False,
        ),
    )
    nullable: bool = Field(
        sa_column=Column(
            "NULLABLE",
            Boolean,
            nullable=False,
        ),
    )
    cardinality: str = Field(
        sa_column=Column(
            "CARDINALITY",
            String(8),
            nullable=False,
        ),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "CREATED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
