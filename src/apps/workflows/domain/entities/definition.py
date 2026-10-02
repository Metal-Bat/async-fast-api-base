"""Persisted workflow definitions, immutable versions, and graph snapshots."""

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
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity


class WorkflowDefinitionEntity(BaseEntity, table=True):
    __tablename__ = "WORKFLOW_DEFINITION"
    __table_args__ = (
        Index(
            "uq_WORKFLOW_DEFINITION_code_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index("ix_WORKFLOW_DEFINITION_owner_active", "OWNER_USER_ID", "IS_ACTIVE"),
        Index("ix_WORKFLOW_DEFINITION_access_active", "ACCESS_MODE", "IS_ACTIVE"),
        CheckConstraint(
            'length("CODE") > 0 AND length("NAME") > 0', name="ck_WORKFLOW_DEFINITION_names"
        ),
        CheckConstraint(
            "\"ACCESS_MODE\" IN ('OPEN', 'RESTRICTED')", name="ck_WORKFLOW_DEFINITION_access"
        ),
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
    access_mode: str = Field(
        default="RESTRICTED",
        sa_column=Column(
            "ACCESS_MODE",
            String(16),
            nullable=False,
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


class WorkflowAccessGrantEntity(BaseEntity, table=True):
    __tablename__ = "WORKFLOW_ACCESS_GRANT"
    __table_args__ = (
        CheckConstraint(
            '(num_nonnulls("USER_ID", "WORK_GROUP_ID") = 1)', name="ck_WORKFLOW_ACCESS_GRANT_target"
        ),
        CheckConstraint('("CAN_VIEW" OR "CAN_START")', name="ck_WORKFLOW_ACCESS_GRANT_capability"),
        CheckConstraint(
            '(NOT "CAN_START" OR "CAN_VIEW")', name="ck_WORKFLOW_ACCESS_GRANT_start_implies_view"
        ),
        Index(
            "uq_WORKFLOW_ACCESS_GRANT_user",
            "WORKFLOW_DEFINITION_ID",
            "USER_ID",
            unique=True,
            postgresql_where=text('"USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
        ),
        Index(
            "uq_WORKFLOW_ACCESS_GRANT_group",
            "WORKFLOW_DEFINITION_ID",
            "WORK_GROUP_ID",
            unique=True,
            postgresql_where=text('"WORK_GROUP_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
        ),
        Index("ix_WORKFLOW_ACCESS_GRANT_user_definition", "USER_ID", "WORKFLOW_DEFINITION_ID"),
        Index(
            "ix_WORKFLOW_ACCESS_GRANT_group_definition",
            "WORK_GROUP_ID",
            "WORKFLOW_DEFINITION_ID",
        ),
    )

    workflow_definition_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_DEFINITION_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_DEFINITION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    work_group_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "WORK_GROUP_ID",
            Uuid,
            ForeignKey(
                "WORK_GROUP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    can_view: bool = Field(
        default=True,
        sa_column=Column(
            "CAN_VIEW",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )
    can_start: bool = Field(
        default=False,
        sa_column=Column(
            "CAN_START",
            Boolean,
            nullable=False,
            server_default=text("false"),
        ),
    )


class WorkflowVersionEntity(BaseEntity, table=True):
    __tablename__ = "WORKFLOW_VERSION"
    __table_args__ = (
        UniqueConstraint("WORKFLOW_DEFINITION_ID", "NUMBER", name="uq_WORKFLOW_VERSION_number"),
        Index(
            "ix_WORKFLOW_VERSION_definition_status", "WORKFLOW_DEFINITION_ID", "STATUS", "NUMBER"
        ),
        Index("ix_WORKFLOW_VERSION_publisher", "PUBLISHED_BY_USER_ID"),
        CheckConstraint('"NUMBER" > 0', name="ck_WORKFLOW_VERSION_number"),
        CheckConstraint('"DEFAULT_PRIORITY" BETWEEN 0 AND 9', name="ck_WORKFLOW_VERSION_priority"),
        CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="ck_WORKFLOW_VERSION_status"
        ),
        CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "GRAPH_CHECKSUM" IS NULL AND "PUBLISHED_AT" IS NULL AND "PUBLISHED_BY_USER_ID" IS NULL) OR ("STATUS" IN (\'PUBLISHED\', \'RETIRED\') AND length("GRAPH_CHECKSUM") = 64 AND "PUBLISHED_AT" IS NOT NULL AND "PUBLISHED_BY_USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL)',
            name="ck_WORKFLOW_VERSION_publication",
        ),
    )

    workflow_definition_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_DEFINITION_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_DEFINITION.ID",
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
    default_priority: int = Field(
        default=0,
        sa_column=Column(
            "DEFAULT_PRIORITY",
            Integer,
            nullable=False,
            server_default=text("0"),
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
    graph_checksum: str | None = Field(
        default=None,
        sa_column=Column(
            "GRAPH_CHECKSUM",
            String(64),
        ),
    )
    subprocess_interface: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "SUBPROCESS_INTERFACE",
            JSONB(none_as_null=True),
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
