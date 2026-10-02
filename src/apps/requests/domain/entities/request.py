"""Pinned request types, business requests, and form submissions."""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity


class BusinessRequestEntity(BaseEntity, table=True):
    __tablename__ = "BUSINESS_REQUEST"
    __table_args__ = (
        Index(
            "uq_BUSINESS_REQUEST_submit",
            "REQUESTER_USER_ID",
            "SUBMIT_KEY",
            unique=True,
            postgresql_where=text('"SUBMIT_KEY" IS NOT NULL'),
        ),
        Index(
            "ix_BUSINESS_REQUEST_requester_status_created",
            "REQUESTER_USER_ID",
            "STATUS",
            text('"CREATED_AT" DESC'),
            "ID",
        ),
        Index(
            "ix_BUSINESS_REQUEST_status_priority_created",
            "STATUS",
            text('"PRIORITY" DESC'),
            "CREATED_AT",
            "ID",
        ),
        Index("ix_BUSINESS_REQUEST_type", "REQUEST_TYPE_ID"),
        Index("ix_BUSINESS_REQUEST_workflow_version", "WORKFLOW_VERSION_ID"),
        CheckConstraint(
            "\"STATUS\" IN ('DRAFT','SUBMITTED','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_BUSINESS_REQUEST_status",
        ),
        CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_BUSINESS_REQUEST_priority"),
        CheckConstraint(
            '("SUBMIT_KEY" IS NULL) = ("SUBMIT_PAYLOAD_HASH" IS NULL)',
            name="ck_BUSINESS_REQUEST_submit_pair",
        ),
        CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "SUBMITTED_AT" IS NULL AND "CLOSED_AT" IS NULL '
            'AND "START_COMMAND" IS NULL) OR '
            "(\"STATUS\" IN ('SUBMITTED','RUNNING') AND \"SUBMITTED_AT\" IS NOT NULL "
            'AND "CLOSED_AT" IS NULL AND "START_COMMAND" IS NOT NULL) OR '
            "(\"STATUS\" IN ('COMPLETED','FAILED','CANCELLED') AND \"CLOSED_AT\" IS NOT NULL)",
            name="ck_BUSINESS_REQUEST_lifecycle",
        ),
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
    requester_user_id: UUID = Field(
        sa_column=Column(
            "REQUESTER_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    workflow_version_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_VERSION_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_VERSION.ID",
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
    priority: int = Field(
        sa_column=Column(
            "PRIORITY",
            Integer,
            nullable=False,
        ),
    )
    submitted_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "SUBMITTED_AT",
            DateTime(timezone=True),
        ),
    )
    closed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "CLOSED_AT",
            DateTime(timezone=True),
        ),
    )
    submit_key: str | None = Field(
        default=None,
        sa_column=Column(
            "SUBMIT_KEY",
            String(128),
        ),
    )
    submit_payload_hash: str | None = Field(
        default=None,
        sa_column=Column(
            "SUBMIT_PAYLOAD_HASH",
            String(64),
        ),
    )
    origin_client_context: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "ORIGIN_CLIENT_CONTEXT",
            JSONB,
        ),
    )
    start_command: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "START_COMMAND",
            JSONB(none_as_null=True),
        ),
    )
