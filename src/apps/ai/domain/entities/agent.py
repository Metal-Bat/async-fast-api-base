"""Durable per-logical-task AI limits and per-dispatch reservations."""

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
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity


class AIAgentEntity(BaseEntity, table=True):
    """One immutable published agent version or mutable authoring draft."""

    __tablename__ = "AI_AGENT"
    __table_args__ = (
        Index("uq_AI_AGENT_code_number", "CODE", "NUMBER", unique=True),
        Index("ix_AI_AGENT_owner", "OWNER_USER_ID"),
        CheckConstraint('"NUMBER" > 0', name="ck_AI_AGENT_number"),
        CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_AI_AGENT_status",
        ),
    )
    code: str = Field(
        sa_column=Column(
            "CODE",
            String(64),
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
    name: str = Field(
        sa_column=Column(
            "NAME",
            String(255),
            nullable=False,
        ),
    )
    owner_user_id: UUID = Field(
        sa_column=Column(
            "OWNER_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
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
    spec: dict[str, Any] = Field(
        sa_column=Column(
            "SPEC",
            JSONB,
            nullable=False,
        ),
    )
    checksum: str | None = Field(
        default=None,
        sa_column=Column(
            "CHECKSUM",
            String(64),
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "PUBLISHED_AT",
            DateTime(timezone=True),
        ),
    )
