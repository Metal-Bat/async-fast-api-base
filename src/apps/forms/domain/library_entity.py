"""Authored reusable component/type versions and scoped use grants."""

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
from core.history import create_history_table


class DataTypeEntity(BaseEntity, table=True):
    __tablename__ = "FORM_DATA_TYPE"
    __table_args__ = (
        Index(
            "uq_FORM_DATA_TYPE_CODE_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index("ix_FORM_DATA_TYPE_owner_created", "OWNER_USER_ID", "CREATED_AT"),
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
    is_active: bool = Field(
        default=True,
        sa_column=Column(
            "IS_ACTIVE",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )


class DataTypeVersionEntity(BaseEntity, table=True):
    __tablename__ = "FORM_DATA_TYPE_VERSION"
    __table_args__ = (
        UniqueConstraint("ROOT_ID", "NUMBER", name="uq_FORM_DATA_TYPE_VERSION_number"),
        Index("ix_FORM_DATA_TYPE_VERSION_root_status", "ROOT_ID", "STATUS", "NUMBER"),
        CheckConstraint('"NUMBER" > 0', name="ck_FORM_DATA_TYPE_VERSION_number"),
        CheckConstraint(
            """( "STATUS" = 'DRAFT' AND "CHECKSUM" IS NULL AND "RESOLVED" IS NULL AND "PUBLISHED_AT" IS NULL AND "PUBLISHED_BY_USER_ID" IS NULL ) OR ( "STATUS" IN ('PUBLISHED', 'RETIRED') AND "CHECKSUM" IS NOT NULL AND length("CHECKSUM") = 64 AND "RESOLVED" IS NOT NULL AND "PUBLISHED_AT" IS NOT NULL AND "PUBLISHED_BY_USER_ID" IS NOT NULL )""",
            name="ck_FORM_DATA_TYPE_VERSION_publication",
        ),
        CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_FORM_DATA_TYPE_VERSION_status",
        ),
    )

    root_id: UUID = Field(
        sa_column=Column(
            "ROOT_ID",
            Uuid,
            ForeignKey(
                "FORM_DATA_TYPE.ID",
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
    document: dict[str, Any] = Field(
        sa_column=Column(
            "DOCUMENT",
            JSONB,
            nullable=False,
        ),
    )
    resolved: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "RESOLVED",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    dependencies: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(
            "DEPENDENCIES",
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
    )
    checksum: str | None = Field(
        default=None,
        sa_column=Column(
            "CHECKSUM",
            String(64),
            nullable=True,
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "PUBLISHED_AT",
            DateTime(timezone=True),
            nullable=True,
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
            nullable=True,
        ),
    )


class ComponentEntity(BaseEntity, table=True):
    __tablename__ = "FORM_COMPONENT"
    __table_args__ = (
        Index(
            "uq_FORM_COMPONENT_CODE_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index("ix_FORM_COMPONENT_owner_created", "OWNER_USER_ID", "CREATED_AT"),
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
    is_active: bool = Field(
        default=True,
        sa_column=Column(
            "IS_ACTIVE",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )


class ComponentVersionEntity(BaseEntity, table=True):
    __tablename__ = "FORM_COMPONENT_VERSION"
    __table_args__ = (
        UniqueConstraint("ROOT_ID", "NUMBER", name="uq_FORM_COMPONENT_VERSION_number"),
        Index("ix_FORM_COMPONENT_VERSION_root_status", "ROOT_ID", "STATUS", "NUMBER"),
        CheckConstraint('"NUMBER" > 0', name="ck_FORM_COMPONENT_VERSION_number"),
        CheckConstraint(
            """( "STATUS" = 'DRAFT' AND "CHECKSUM" IS NULL AND "RESOLVED" IS NULL AND "PUBLISHED_AT" IS NULL AND "PUBLISHED_BY_USER_ID" IS NULL ) OR ( "STATUS" IN ('PUBLISHED', 'RETIRED') AND "CHECKSUM" IS NOT NULL AND length("CHECKSUM") = 64 AND "RESOLVED" IS NOT NULL AND "PUBLISHED_AT" IS NOT NULL AND "PUBLISHED_BY_USER_ID" IS NOT NULL )""",
            name="ck_FORM_COMPONENT_VERSION_publication",
        ),
        CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_FORM_COMPONENT_VERSION_status",
        ),
    )

    root_id: UUID = Field(
        sa_column=Column(
            "ROOT_ID",
            Uuid,
            ForeignKey(
                "FORM_COMPONENT.ID",
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
    document: dict[str, Any] = Field(
        sa_column=Column(
            "DOCUMENT",
            JSONB,
            nullable=False,
        ),
    )
    resolved: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "RESOLVED",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    dependencies: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(
            "DEPENDENCIES",
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
    )
    checksum: str | None = Field(
        default=None,
        sa_column=Column(
            "CHECKSUM",
            String(64),
            nullable=True,
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "PUBLISHED_AT",
            DateTime(timezone=True),
            nullable=True,
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
            nullable=True,
        ),
    )


class LibraryGrantEntity(BaseEntity, table=True):
    __tablename__ = "FORM_LIBRARY_GRANT"
    __table_args__ = (
        CheckConstraint(
            '(CASE WHEN "COMPONENT_ID" IS NULL THEN 0 ELSE 1 END) + (CASE WHEN "DATA_TYPE_ID" IS NULL THEN 0 ELSE 1 END) = 1',
            name="ck_FORM_LIBRARY_GRANT_resource",
        ),
        CheckConstraint(
            '(CASE WHEN "USER_ID" IS NULL THEN 0 ELSE 1 END) + (CASE WHEN "WORK_GROUP_ID" IS NULL THEN 0 ELSE 1 END) = 1',
            name="ck_FORM_LIBRARY_GRANT_target",
        ),
        Index("ix_FORM_LIBRARY_GRANT_component", "COMPONENT_ID"),
        Index("ix_FORM_LIBRARY_GRANT_data_type", "DATA_TYPE_ID"),
        Index("ix_FORM_LIBRARY_GRANT_user", "USER_ID"),
        Index("ix_FORM_LIBRARY_GRANT_group", "WORK_GROUP_ID"),
        Index(
            "uq_FORM_LIBRARY_GRANT_component_user_active",
            "COMPONENT_ID",
            "USER_ID",
            unique=True,
            postgresql_where=text(
                '"COMPONENT_ID" IS NOT NULL AND "USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL'
            ),
        ),
        Index(
            "uq_FORM_LIBRARY_GRANT_component_group_active",
            "COMPONENT_ID",
            "WORK_GROUP_ID",
            unique=True,
            postgresql_where=text(
                '"COMPONENT_ID" IS NOT NULL AND "WORK_GROUP_ID" IS NOT NULL AND "DELETED_AT" IS NULL'
            ),
        ),
        Index(
            "uq_FORM_LIBRARY_GRANT_type_user_active",
            "DATA_TYPE_ID",
            "USER_ID",
            unique=True,
            postgresql_where=text(
                '"DATA_TYPE_ID" IS NOT NULL AND "USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL'
            ),
        ),
        Index(
            "uq_FORM_LIBRARY_GRANT_type_group_active",
            "DATA_TYPE_ID",
            "WORK_GROUP_ID",
            unique=True,
            postgresql_where=text(
                '"DATA_TYPE_ID" IS NOT NULL AND "WORK_GROUP_ID" IS NOT NULL AND "DELETED_AT" IS NULL'
            ),
        ),
    )

    component_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "COMPONENT_ID",
            Uuid,
            ForeignKey(
                "FORM_COMPONENT.ID",
                ondelete="RESTRICT",
            ),
            nullable=True,
        ),
    )
    data_type_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "DATA_TYPE_ID",
            Uuid,
            ForeignKey(
                "FORM_DATA_TYPE.ID",
                ondelete="RESTRICT",
            ),
            nullable=True,
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
            ),
            nullable=True,
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
            ),
            nullable=True,
        ),
    )
    can_use: bool = Field(
        default=True,
        sa_column=Column(
            "CAN_USE",
            Boolean,
            nullable=False,
        ),
    )


for entity in (
    DataTypeEntity,
    DataTypeVersionEntity,
    ComponentEntity,
    ComponentVersionEntity,
    LibraryGrantEntity,
):
    table = create_history_table(entity.__table__, ondelete="RESTRICT", onupdate="RESTRICT")  # ty:ignore[unresolved-attribute]
    Index(f"ix_{table.name}_entity_changed", table.c.ENTITY_ID, table.c.CHANGED_AT)
