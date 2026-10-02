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
    UniqueConstraint,
    Uuid,
)
from sqlmodel import Field

from core.base_entity import BaseEntity


class NotificationDeliveryEntity(BaseEntity, table=True):
    __tablename__ = "NOTIFICATION_DELIVERY"
    __table_args__ = (
        UniqueConstraint("NOTIFICATION_ID", "CHANNEL", name="uq_NOTIFICATION_DELIVERY_channel"),
        Index("ix_NOTIFICATION_DELIVERY_due", "STATUS", "NEXT_ATTEMPT_AT", "ID"),
        Index("ix_NOTIFICATION_DELIVERY_connection", "INTEGRATION_CONNECTION_ID"),
        CheckConstraint("\"CHANNEL\" IN ('EMAIL')", name="ck_NOTIFICATION_DELIVERY_channel"),
        CheckConstraint(
            "\"STATUS\" IN ('PENDING','RUNNING','RETRY','DELIVERED','BOUNCED','FAILED','CANCELLED')",
            name="ck_NOTIFICATION_DELIVERY_status",
        ),
        CheckConstraint('"ATTEMPT_COUNT" >= 0', name="ck_NOTIFICATION_DELIVERY_attempts"),
    )
    notification_id: UUID = Field(
        sa_column=Column(
            "NOTIFICATION_ID",
            Uuid,
            ForeignKey(
                "NOTIFICATION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    channel: str = Field(
        sa_column=Column(
            "CHANNEL",
            String(16),
            nullable=False,
        ),
    )
    destination_fingerprint: str = Field(
        sa_column=Column(
            "DESTINATION_FINGERPRINT",
            String(64),
            nullable=False,
        ),
    )
    integration_connection_id: UUID = Field(
        sa_column=Column(
            "INTEGRATION_CONNECTION_ID",
            Uuid,
            ForeignKey(
                "INTEGRATION_CONNECTION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    provider_message_ref: str | None = Field(
        default=None,
        sa_column=Column(
            "PROVIDER_MESSAGE_REF",
            String(255),
        ),
    )
    status: str = Field(
        default="PENDING",
        sa_column=Column(
            "STATUS",
            String(16),
            nullable=False,
        ),
    )
    attempt_count: int = Field(
        default=0,
        sa_column=Column(
            "ATTEMPT_COUNT",
            Integer,
            nullable=False,
        ),
    )
    next_attempt_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "NEXT_ATTEMPT_AT",
            DateTime(timezone=True),
        ),
    )
    last_error_code: str | None = Field(
        default=None,
        sa_column=Column(
            "LAST_ERROR_CODE",
            String(128),
        ),
    )
    delivered_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "DELIVERED_AT",
            DateTime(timezone=True),
        ),
    )
    terminal_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "TERMINAL_AT",
            DateTime(timezone=True),
        ),
    )
