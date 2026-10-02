"""Durable notification and external delivery entities."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlmodel import Field

from core.base_entity import BaseEntity


class NotificationEntity(BaseEntity, table=True):
    __tablename__ = "NOTIFICATION"
    __table_args__ = (
        UniqueConstraint(
            "STEP_EXECUTION_ID", "RECIPIENT_USER_ID", name="uq_NOTIFICATION_execution_recipient"
        ),
        Index("ix_NOTIFICATION_recipient_created", "RECIPIENT_USER_ID", "CREATED_AT", "ID"),
        Index("ix_NOTIFICATION_process", "PROCESS_INSTANCE_ID"),
        CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_NOTIFICATION_priority"),
        CheckConstraint(
            "\"STATUS\" IN ('ACTIVE','CANCELLED','EXPIRED')", name="ck_NOTIFICATION_status"
        ),
        CheckConstraint(
            '("CONTENT" IS NOT NULL)::int + ("CONTENT_REF" IS NOT NULL)::int = 1',
            name="ck_NOTIFICATION_content",
        ),
    )
    recipient_user_id: UUID = Field(
        sa_column=Column(
            "RECIPIENT_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    business_request_id: UUID = Field(
        sa_column=Column(
            "BUSINESS_REQUEST_ID",
            Uuid,
            ForeignKey(
                "BUSINESS_REQUEST.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    process_instance_id: UUID = Field(
        sa_column=Column(
            "PROCESS_INSTANCE_ID",
            Uuid,
            ForeignKey(
                "PROCESS_INSTANCE.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    step_execution_id: UUID = Field(
        sa_column=Column(
            "STEP_EXECUTION_ID",
            Uuid,
            ForeignKey(
                "STEP_EXECUTION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    template_key: str = Field(
        sa_column=Column(
            "TEMPLATE_KEY",
            String(128),
            nullable=False,
        ),
    )
    template_version: str = Field(
        sa_column=Column(
            "TEMPLATE_VERSION",
            String(32),
            nullable=False,
        ),
    )
    locale: str = Field(
        sa_column=Column(
            "LOCALE",
            String(16),
            nullable=False,
        ),
    )
    subject: str = Field(
        sa_column=Column(
            "SUBJECT",
            String(512),
            nullable=False,
        ),
    )
    content: str | None = Field(
        default=None,
        sa_column=Column(
            "CONTENT",
            Text,
        ),
    )
    content_ref: str | None = Field(
        default=None,
        sa_column=Column(
            "CONTENT_REF",
            String(512),
        ),
    )
    priority: int = Field(
        default=0,
        sa_column=Column(
            "PRIORITY",
            Integer,
            nullable=False,
        ),
    )
    status: str = Field(
        default="ACTIVE",
        sa_column=Column(
            "STATUS",
            String(16),
            nullable=False,
        ),
    )
    read_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "READ_AT",
            DateTime(timezone=True),
        ),
    )
