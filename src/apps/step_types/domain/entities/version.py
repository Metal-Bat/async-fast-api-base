"""Normalized step identities, pinned handler versions, and typed ports."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity


class StepTypeVersionEntity(BaseEntity, table=True):
    __tablename__ = "STEP_TYPE_VERSION"
    __table_args__ = (
        UniqueConstraint("STEP_TYPE_ID", "NUMBER", name="uq_STEP_TYPE_VERSION_number"),
        Index("ix_STEP_TYPE_VERSION_type_status", "STEP_TYPE_ID", "STATUS"),
        CheckConstraint('"NUMBER" > 0', name="ck_STEP_TYPE_VERSION_number"),
        CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="ck_STEP_TYPE_VERSION_status"
        ),
        CheckConstraint(
            "\"EXECUTION_MODE\" IN ('SYNC', 'HUMAN', 'BACKGROUND', 'WAIT')",
            name="ck_STEP_TYPE_VERSION_mode",
        ),
        CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "PUBLISHED_AT" IS NULL) OR ("STATUS" IN (\'PUBLISHED\', \'RETIRED\') AND "PUBLISHED_AT" IS NOT NULL)',
            name="ck_STEP_TYPE_VERSION_publication",
        ),
        CheckConstraint(
            "jsonb_typeof(\"CONFIG_SCHEMA\") = 'object'", name="ck_STEP_TYPE_VERSION_schema"
        ),
        CheckConstraint(
            '"STATUS" = \'DRAFT\' OR "DELETED_AT" IS NULL', name="ck_STEP_TYPE_VERSION_not_deleted"
        ),
    )

    step_type_id: UUID = Field(
        sa_column=Column(
            "STEP_TYPE_ID",
            Uuid,
            ForeignKey(
                "STEP_TYPE.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    number: int = Field(
        sa_column=Column(
            "NUMBER",
            Integer,
            nullable=False,
        ),
    )
    status: str = Field(
        default="DRAFT",
        sa_column=Column(
            "STATUS",
            String(16),
            nullable=False,
        ),
    )
    handler_key: str = Field(
        sa_column=Column(
            "HANDLER_KEY",
            String(64),
            nullable=False,
        ),
    )
    handler_version: str = Field(
        sa_column=Column(
            "HANDLER_VERSION",
            String(64),
            nullable=False,
        ),
    )
    execution_mode: str = Field(
        sa_column=Column(
            "EXECUTION_MODE",
            String(16),
            nullable=False,
        ),
    )
    config_schema: dict[str, Any] = Field(
        sa_column=Column(
            "CONFIG_SCHEMA",
            JSONB,
            nullable=False,
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "PUBLISHED_AT",
            DateTime(timezone=True),
        ),
    )
