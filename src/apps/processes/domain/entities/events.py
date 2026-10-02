"""Durable single-token process runtime entities."""

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
from sqlmodel import Field, SQLModel

from apps.tasks.domain import entity as task_entities  # noqa: F401
from utils.date_utils import get_datetime_utc


class ProcessTransitionEntity(SQLModel, table=True):
    __tablename__ = "PROCESS_TRANSITION"
    __table_args__ = (
        UniqueConstraint(
            "FROM_STEP_EXECUTION_ID",
            "WORKFLOW_TRANSITION_ID",
            name="uq_PROCESS_TRANSITION_once",
        ),
        Index("ix_PROCESS_TRANSITION_process_taken", "PROCESS_INSTANCE_ID", "TAKEN_AT", "ID"),
        Index("ix_PROCESS_TRANSITION_to", "TO_STEP_EXECUTION_ID"),
        Index("ix_PROCESS_TRANSITION_workflow", "WORKFLOW_TRANSITION_ID"),
    )
    id: UUID = Field(
        default=None,
        sa_column=Column(
            "ID",
            Uuid,
            primary_key=True,
            server_default=text("uuidv7()"),
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
    from_step_execution_id: UUID = Field(
        sa_column=Column(
            "FROM_STEP_EXECUTION_ID",
            Uuid,
            ForeignKey(
                "STEP_EXECUTION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    to_step_execution_id: UUID = Field(
        sa_column=Column(
            "TO_STEP_EXECUTION_ID",
            Uuid,
            ForeignKey(
                "STEP_EXECUTION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    workflow_transition_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_TRANSITION_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_TRANSITION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
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
    taken_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "TAKEN_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )


class CompensationRecordEntity(SQLModel, table=True):
    """Durable reversal registration for one completed external effect."""

    __tablename__ = "COMPENSATION_RECORD"
    __table_args__ = (
        UniqueConstraint("SOURCE_EXECUTION_ID", name="uq_COMPENSATION_RECORD_source"),
        UniqueConstraint(
            "PROCESS_INSTANCE_ID", "DISPATCH_KEY", name="uq_COMPENSATION_RECORD_dispatch"
        ),
        Index("ix_COMPENSATION_RECORD_process_order", "PROCESS_INSTANCE_ID", "ORDINAL"),
        CheckConstraint('"ORDINAL" > 0', name="ck_COMPENSATION_RECORD_ordinal"),
        CheckConstraint(
            "\"STATUS\" IN ('PENDING','RUNNING','EXECUTING','COMPLETED','FAILED')",
            name="ck_COMPENSATION_RECORD_status",
        ),
    )
    id: UUID = Field(
        default=None,
        sa_column=Column(
            "ID",
            Uuid,
            primary_key=True,
            server_default=text("uuidv7()"),
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
    source_execution_id: UUID = Field(
        sa_column=Column(
            "SOURCE_EXECUTION_ID",
            Uuid,
            ForeignKey(
                "STEP_EXECUTION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    compensation_step_id: UUID = Field(
        sa_column=Column(
            "COMPENSATION_STEP_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_STEP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    ordinal: int = Field(
        sa_column=Column(
            "ORDINAL",
            Integer,
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
    dispatch_key: str | None = Field(
        default=None,
        sa_column=Column(
            "DISPATCH_KEY",
            String(160),
            nullable=True,
        ),
    )
    last_error_code: str | None = Field(
        default=None,
        sa_column=Column(
            "LAST_ERROR_CODE",
            String(128),
        ),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "COMPLETED_AT",
            DateTime(timezone=True),
        ),
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "CREATED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )


class ProcessEventEntity(SQLModel, table=True):
    """Immutable, redacted event in one process's ordered audit stream."""

    __tablename__ = "PROCESS_EVENT"
    __table_args__ = (
        UniqueConstraint("PROCESS_INSTANCE_ID", "SEQUENCE", name="uq_PROCESS_EVENT_sequence"),
        Index(
            "uq_PROCESS_EVENT_step_command",
            "STEP_EXECUTION_ID",
            "COMMAND_KEY",
            unique=True,
            postgresql_where=text('"COMMAND_KEY" IS NOT NULL'),
        ),
        Index("ix_PROCESS_EVENT_request_time", "BUSINESS_REQUEST_ID", "OCCURRED_AT", "ID"),
        Index("ix_PROCESS_EVENT_step", "STEP_EXECUTION_ID"),
        Index("ix_PROCESS_EVENT_work_item", "WORK_ITEM_ID"),
        Index("ix_PROCESS_EVENT_actor", "ACTOR_USER_ID"),
        CheckConstraint('"SEQUENCE" > 0', name="ck_PROCESS_EVENT_sequence"),
        CheckConstraint(
            '("COMMAND_KEY" IS NULL) = ("COMMAND_PAYLOAD_HASH" IS NULL)',
            name="ck_PROCESS_EVENT_command_pair",
        ),
    )
    id: UUID = Field(
        default=None,
        sa_column=Column(
            "ID",
            Uuid,
            primary_key=True,
            server_default=text("uuidv7()"),
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
    sequence: int = Field(
        sa_column=Column(
            "SEQUENCE",
            Integer,
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
    step_execution_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "STEP_EXECUTION_ID",
            Uuid,
            ForeignKey(
                "STEP_EXECUTION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    work_item_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "WORK_ITEM_ID",
            Uuid,
            ForeignKey(
                "WORK_ITEM.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    actor_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "ACTOR_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    public_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "PUBLIC_PAYLOAD",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    trace_id: str | None = Field(
        default=None,
        sa_column=Column(
            "TRACE_ID",
            String(64),
        ),
    )
    request_id: str | None = Field(
        default=None,
        sa_column=Column(
            "REQUEST_ID",
            String(64),
        ),
    )
    command_key: str | None = Field(
        default=None,
        sa_column=Column(
            "COMMAND_KEY",
            String(128),
        ),
    )
    command_payload_hash: str | None = Field(
        default=None,
        sa_column=Column(
            "COMMAND_PAYLOAD_HASH",
            String(64),
        ),
    )
    occurred_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "OCCURRED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
