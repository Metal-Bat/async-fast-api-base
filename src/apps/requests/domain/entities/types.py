"""Pinned request types, business requests, and form submissions."""

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlmodel import Field

from core.base_entity import BaseEntity


class RequestTypeEntity(BaseEntity, table=True):
    __tablename__ = "REQUEST_TYPE"
    __table_args__ = (
        Index(
            "uq_REQUEST_TYPE_code_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index("ix_REQUEST_TYPE_workflow_active", "WORKFLOW_DEFINITION_ID", "IS_ACTIVE"),
        Index("ix_REQUEST_TYPE_form", "FORM_DEFINITION_ID"),
        CheckConstraint('length("CODE") > 0 AND length("NAME") > 0', name="ck_REQUEST_TYPE_names"),
        CheckConstraint(
            '"DEFAULT_PRIORITY" IS NULL OR "DEFAULT_PRIORITY" BETWEEN 0 AND 9',
            name="ck_REQUEST_TYPE_priority",
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
    is_active: bool = Field(
        default=True,
        sa_column=Column(
            "IS_ACTIVE",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )
    allow_cross_client_resume: bool = Field(
        default=False,
        sa_column=Column(
            "ALLOW_CROSS_CLIENT_RESUME",
            Boolean,
            nullable=False,
            server_default=text("false"),
        ),
    )
    default_priority: int | None = Field(
        default=None,
        sa_column=Column(
            "DEFAULT_PRIORITY",
            Integer,
        ),
    )
    extension_contract: str | None = Field(
        default=None,
        sa_column=Column(
            "EXTENSION_CONTRACT",
            String(128),
        ),
    )


class RequestTypeClientTargetEntity(BaseEntity, table=True):
    __tablename__ = "REQUEST_TYPE_CLIENT_TARGET"
    __table_args__ = (
        Index(
            "uq_REQUEST_TYPE_CLIENT_TARGET_active",
            "REQUEST_TYPE_ID",
            "CLIENT_ID",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index("ix_REQUEST_TYPE_CLIENT_TARGET_client", "CLIENT_ID"),
    )
    request_type_id: UUID = Field(
        sa_column=Column(
            "REQUEST_TYPE_ID",
            Uuid,
            ForeignKey(
                "REQUEST_TYPE.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    client_id: UUID = Field(
        sa_column=Column(
            "CLIENT_ID",
            Uuid,
            ForeignKey(
                "CLIENT.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    minimum_release: str | None = Field(
        default=None,
        sa_column=Column(
            "MINIMUM_RELEASE",
            String(64),
        ),
    )
    maximum_release_exclusive: str | None = Field(
        default=None,
        sa_column=Column(
            "MAXIMUM_RELEASE_EXCLUSIVE",
            String(64),
        ),
    )
