"""Versioned form definitions and generated authoring history."""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity


class FormVersionEntity(BaseEntity, table=True):
    __tablename__ = "FORM_VERSION"
    __table_args__ = (
        UniqueConstraint("FORM_DEFINITION_ID", "NUMBER", name="uq_FORM_VERSION_number"),
        Index("ix_FORM_VERSION_definition_status_number", "FORM_DEFINITION_ID", "STATUS", "NUMBER"),
        Index("ix_FORM_VERSION_publisher", "PUBLISHED_BY_USER_ID"),
        CheckConstraint('"NUMBER" > 0', name="ck_FORM_VERSION_number"),
        CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="ck_FORM_VERSION_status"
        ),
        CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "CHECKSUM" IS NULL AND "PUBLISHED_AT" IS NULL AND "PUBLISHED_BY_USER_ID" IS NULL) OR ("STATUS" IN (\'PUBLISHED\', \'RETIRED\') AND "CHECKSUM" IS NOT NULL AND length("CHECKSUM") = 64 AND "PUBLISHED_AT" IS NOT NULL AND "PUBLISHED_BY_USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL)',
            name="ck_FORM_VERSION_publication",
        ),
    )
    form_definition_id: UUID = Field(
        sa_column=Column(
            "FORM_DEFINITION_ID",
            Uuid,
            ForeignKey(
                "FORM_DEFINITION.ID",
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
    data_dialect: str = Field(
        sa_column=Column(
            "DATA_DIALECT",
            String(128),
            nullable=False,
        ),
    )
    render_dialect: str = Field(
        sa_column=Column(
            "RENDER_DIALECT",
            String(64),
            nullable=False,
        ),
    )
    data_schema: dict[str, Any] = Field(
        sa_column=Column(
            "DATA_SCHEMA",
            JSONB,
            nullable=False,
        ),
    )
    behavior_dialect: str | None = Field(
        default=None,
        sa_column=Column(
            "BEHAVIOR_DIALECT",
            String(64),
            nullable=True,
        ),
    )
    render_schema: dict[str, Any] = Field(
        sa_column=Column(
            "RENDER_SCHEMA",
            JSONB,
            nullable=False,
        ),
    )
    page_settings: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "PAGE_SETTINGS",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    variants: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(
            "VARIANTS",
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
    )
    localization: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "LOCALIZATION",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    reuse_instances: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(
            "REUSE_INSTANCES",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    reuse_source: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "REUSE_SOURCE",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    reuse_manifest: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(
            "REUSE_MANIFEST",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    template_source: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "TEMPLATE_SOURCE",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    checksum: str | None = Field(
        default=None,
        sa_column=Column(
            "CHECKSUM",
            String(64),
        ),
    )
    published_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "PUBLISHED_BY_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "PUBLISHED_AT",
            DateTime(timezone=True),
        ),
    )
