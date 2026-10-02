"""Durable single-token process runtime entities."""

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
    text,
)
from sqlmodel import Field

from apps.tasks.domain import entity as task_entities  # noqa: F401
from core.base_entity import BaseEntity


class EventSubscriptionEntity(BaseEntity, table=True):
    __tablename__ = "EVENT_SUBSCRIPTION"
    __table_args__ = (
        UniqueConstraint(
            "EVENT_TYPE",
            "CORRELATION_HASH",
            "STEP_EXECUTION_ID",
            name="uq_EVENT_SUBSCRIPTION_identity",
        ),
        Index(
            "uq_EVENT_SUBSCRIPTION_delivery",
            "DELIVERY_KEY",
            unique=True,
            postgresql_where=text('"DELIVERY_KEY" IS NOT NULL'),
        ),
        Index(
            "ix_EVENT_SUBSCRIPTION_active",
            "EVENT_TYPE",
            "CORRELATION_HASH",
            postgresql_where=text("\"STATUS\" = 'ACTIVE'"),
        ),
        Index("ix_EVENT_SUBSCRIPTION_step", "STEP_EXECUTION_ID"),
        CheckConstraint(
            "\"STATUS\" IN ('ACTIVE','CONSUMED','EXPIRED','CANCELLED')",
            name="ck_EVENT_SUBSCRIPTION_status",
        ),
        CheckConstraint('"ATTEMPTS" >= 0', name="ck_EVENT_SUBSCRIPTION_attempts"),
        CheckConstraint('"DELETED_AT" IS NULL', name="ck_EVENT_SUBSCRIPTION_not_deleted"),
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
    event_type: str = Field(
        sa_column=Column(
            "EVENT_TYPE",
            String(64),
            nullable=False,
        ),
    )
    correlation_hash: str = Field(
        sa_column=Column(
            "CORRELATION_HASH",
            String(64),
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
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "EXPIRES_AT",
            DateTime(timezone=True),
        ),
    )
    consumed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "CONSUMED_AT",
            DateTime(timezone=True),
        ),
    )
    delivery_key: str | None = Field(
        default=None,
        sa_column=Column(
            "DELIVERY_KEY",
            String(128),
        ),
    )
    delivery_source: str | None = Field(
        default=None,
        sa_column=Column(
            "DELIVERY_SOURCE",
            String(32),
        ),
    )
    attempts: int = Field(
        default=0,
        sa_column=Column(
            "ATTEMPTS",
            Integer,
            nullable=False,
            server_default=text("0"),
        ),
    )


class ScheduledActionEntity(BaseEntity, table=True):
    __tablename__ = "SCHEDULED_ACTION"
    __table_args__ = (
        UniqueConstraint("ACTION_KEY", name="uq_SCHEDULED_ACTION_key"),
        Index(
            "ix_SCHEDULED_ACTION_due",
            "DUE_AT",
            "ID",
            postgresql_where=text("\"STATUS\" = 'PENDING'"),
        ),
        Index(
            "ix_SCHEDULED_ACTION_lease",
            "LEASE_UNTIL",
            "ID",
            postgresql_where=text("\"STATUS\" = 'LEASED'"),
        ),
        Index("ix_SCHEDULED_ACTION_step", "STEP_EXECUTION_ID"),
        CheckConstraint(
            "\"KIND\" IN ('DELAY','DEADLINE','RETRY','ESCALATION')",
            name="ck_SCHEDULED_ACTION_kind",
        ),
        CheckConstraint(
            "\"STATUS\" IN ('PENDING','LEASED','FIRED','CANCELLED','FAILED')",
            name="ck_SCHEDULED_ACTION_status",
        ),
        CheckConstraint('"ATTEMPTS" >= 0', name="ck_SCHEDULED_ACTION_attempts"),
        CheckConstraint('"MAX_ATTEMPTS" > 0', name="ck_SCHEDULED_ACTION_max_attempts"),
        CheckConstraint(
            '("STATUS" = \'LEASED\') = ("LEASE_OWNER" IS NOT NULL AND "LEASE_UNTIL" IS NOT NULL)',
            name="ck_SCHEDULED_ACTION_lease",
        ),
        CheckConstraint('"DELETED_AT" IS NULL', name="ck_SCHEDULED_ACTION_not_deleted"),
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
    kind: str = Field(
        sa_column=Column(
            "KIND",
            String(16),
            nullable=False,
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
    due_at: datetime = Field(
        sa_column=Column(
            "DUE_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
    attempts: int = Field(
        default=0,
        sa_column=Column(
            "ATTEMPTS",
            Integer,
            nullable=False,
            server_default=text("0"),
        ),
    )
    max_attempts: int = Field(
        default=5,
        sa_column=Column(
            "MAX_ATTEMPTS",
            Integer,
            nullable=False,
            server_default=text("5"),
        ),
    )
    lease_owner: UUID | None = Field(
        default=None,
        sa_column=Column(
            "LEASE_OWNER",
            Uuid,
        ),
    )
    lease_until: datetime | None = Field(
        default=None,
        sa_column=Column(
            "LEASE_UNTIL",
            DateTime(timezone=True),
        ),
    )
    fired_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "FIRED_AT",
            DateTime(timezone=True),
        ),
    )
    action_key: str = Field(
        sa_column=Column(
            "ACTION_KEY",
            String(160),
            nullable=False,
        ),
    )
    outcome_key: str = Field(
        sa_column=Column(
            "OUTCOME_KEY",
            String(64),
            nullable=False,
        ),
    )
    last_error_code: str | None = Field(
        default=None,
        sa_column=Column(
            "LAST_ERROR_CODE",
            String(128),
        ),
    )
