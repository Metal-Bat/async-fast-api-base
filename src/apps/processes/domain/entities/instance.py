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
from core.base_entity import BaseEntity
from utils.date_utils import get_datetime_utc


class ProcessInstanceEntity(BaseEntity, table=True):
    __tablename__ = "PROCESS_INSTANCE"
    __table_args__ = (
        Index(
            "uq_PROCESS_INSTANCE_root_request",
            "BUSINESS_REQUEST_ID",
            unique=True,
            postgresql_where=text('"PARENT_STEP_EXECUTION_ID" IS NULL'),
        ),
        Index(
            "uq_PROCESS_INSTANCE_parent_execution",
            "PARENT_STEP_EXECUTION_ID",
            unique=True,
            postgresql_where=text('"PARENT_STEP_EXECUTION_ID" IS NOT NULL'),
        ),
        Index("ix_PROCESS_INSTANCE_status_started", "STATUS", "STARTED_AT", "ID"),
        Index("ix_PROCESS_INSTANCE_workflow", "WORKFLOW_VERSION_ID"),
        CheckConstraint(
            "\"STATUS\" IN ('RUNNING','WAITING','PAUSED','COMPLETED','FAILED','CANCELLED','COMPENSATING','COMPENSATION_FAILED','COMPENSATED')",
            name="ck_PROCESS_INSTANCE_status",
        ),
        CheckConstraint('"EVENT_SEQUENCE" >= 0', name="ck_PROCESS_INSTANCE_sequence"),
        CheckConstraint('"DELETED_AT" IS NULL', name="ck_PROCESS_INSTANCE_not_deleted"),
        CheckConstraint(
            "(\"STATUS\" IN ('COMPLETED','FAILED','CANCELLED','COMPENSATION_FAILED','COMPENSATED')) = (\"ENDED_AT\" IS NOT NULL)",
            name="ck_PROCESS_INSTANCE_terminal",
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
    parent_step_execution_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "PARENT_STEP_EXECUTION_ID",
            Uuid,
            ForeignKey(
                "STEP_EXECUTION.ID",
                name="fk_PROCESS_INSTANCE_parent_execution",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
                use_alter=True,
            ),
        ),
    )
    input_context: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "INPUT_CONTEXT",
            JSONB(none_as_null=True),
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
        default="RUNNING",
        sa_column=Column(
            "STATUS",
            String(32),
            nullable=False,
        ),
    )
    started_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "STARTED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
    ended_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "ENDED_AT",
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
    event_sequence: int = Field(
        default=0,
        sa_column=Column(
            "EVENT_SEQUENCE",
            Integer,
            nullable=False,
            server_default=text("0"),
        ),
    )


class ExecutionTokenEntity(BaseEntity, table=True):
    __tablename__ = "EXECUTION_TOKEN"
    __table_args__ = (
        Index(
            "uq_EXECUTION_TOKEN_root_live_process",
            "PROCESS_INSTANCE_ID",
            unique=True,
            postgresql_where=text(
                "\"STATUS\" IN ('ACTIVE','WAITING') AND \"PARENT_TOKEN_ID\" IS NULL"
            ),
        ),
        Index(
            "uq_EXECUTION_TOKEN_branch_key",
            "PARENT_TOKEN_ID",
            "BRANCH_KEY",
            unique=True,
            postgresql_where=text('"PARENT_TOKEN_ID" IS NOT NULL'),
        ),
        Index("ix_EXECUTION_TOKEN_process_status", "PROCESS_INSTANCE_ID", "STATUS", "ID"),
        Index("ix_EXECUTION_TOKEN_step", "CURRENT_STEP_ID"),
        Index("ix_EXECUTION_TOKEN_parent", "PARENT_TOKEN_ID"),
        CheckConstraint(
            "\"STATUS\" IN ('ACTIVE','WAITING','COMPLETED','CANCELLED','FAILED')",
            name="ck_EXECUTION_TOKEN_status",
        ),
        CheckConstraint('"DELETED_AT" IS NULL', name="ck_EXECUTION_TOKEN_not_deleted"),
        CheckConstraint(
            '"BRANCH_KEY" IS NULL AND "PARENT_TOKEN_ID" IS NULL',
            name="ck_EXECUTION_TOKEN_phase1_single_path",
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
    current_step_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "CURRENT_STEP_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_STEP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
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
    branch_key: str | None = Field(
        default=None,
        sa_column=Column(
            "BRANCH_KEY",
            String(128),
        ),
    )
    parent_token_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "PARENT_TOKEN_ID",
            Uuid,
            ForeignKey(
                "EXECUTION_TOKEN.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )


class StepExecutionEntity(BaseEntity, table=True):
    __tablename__ = "STEP_EXECUTION"
    __table_args__ = (
        UniqueConstraint(
            "EXECUTION_TOKEN_ID", "WORKFLOW_STEP_ID", "VISIT_NUMBER", name="uq_STEP_EXECUTION_visit"
        ),
        Index("ix_STEP_EXECUTION_process_status", "PROCESS_INSTANCE_ID", "STATUS", "ID"),
        Index("ix_STEP_EXECUTION_token", "EXECUTION_TOKEN_ID"),
        Index("ix_STEP_EXECUTION_step_status", "WORKFLOW_STEP_ID", "STATUS"),
        CheckConstraint('"VISIT_NUMBER" > 0', name="ck_STEP_EXECUTION_visit"),
        CheckConstraint(
            "\"STATUS\" IN ('PENDING','RUNNING','WAITING','COMPLETED','FAILED','CANCELLED','TIMED_OUT')",
            name="ck_STEP_EXECUTION_status",
        ),
        CheckConstraint(
            "\"WAIT_KIND\" IS NULL OR \"WAIT_KIND\" IN ('HUMAN','EVENT','TIMER','BACKGROUND','SUBPROCESS')",
            name="ck_STEP_EXECUTION_wait_kind",
        ),
        CheckConstraint('"DELETED_AT" IS NULL', name="ck_STEP_EXECUTION_not_deleted"),
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
    execution_token_id: UUID = Field(
        sa_column=Column(
            "EXECUTION_TOKEN_ID",
            Uuid,
            ForeignKey(
                "EXECUTION_TOKEN.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    workflow_step_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_STEP_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_STEP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    visit_number: int = Field(
        sa_column=Column(
            "VISIT_NUMBER",
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
    wait_kind: str | None = Field(
        default=None,
        sa_column=Column(
            "WAIT_KIND",
            String(16),
        ),
    )
    input_snapshot: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "INPUT_SNAPSHOT",
            JSONB(none_as_null=True),
        ),
    )
    output_snapshot: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "OUTPUT_SNAPSHOT",
            JSONB(none_as_null=True),
        ),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "STARTED_AT",
            DateTime(timezone=True),
        ),
    )
    ended_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "ENDED_AT",
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


class StepExecutionAttemptEntity(SQLModel, table=True):
    __tablename__ = "STEP_EXECUTION_ATTEMPT"
    __table_args__ = (
        UniqueConstraint("STEP_EXECUTION_ID", "NUMBER", name="uq_STEP_EXECUTION_ATTEMPT_number"),
        UniqueConstraint("DISPATCH_KEY", name="uq_STEP_EXECUTION_ATTEMPT_dispatch"),
        Index("ix_STEP_EXECUTION_ATTEMPT_status_started", "STATUS", "STARTED_AT"),
        Index("ix_STEP_EXECUTION_ATTEMPT_task", "TASK_EXECUTION_ID"),
        CheckConstraint('"NUMBER" > 0', name="ck_STEP_EXECUTION_ATTEMPT_number"),
        CheckConstraint(
            "\"STATUS\" IN ('RUNNING','WAITING','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')",
            name="ck_STEP_EXECUTION_ATTEMPT_status",
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
    number: int = Field(
        sa_column=Column(
            "NUMBER",
            Integer,
            nullable=False,
        ),
    )
    status: str = Field(
        default="RUNNING",
        sa_column=Column(
            "STATUS",
            String(16),
            nullable=False,
        ),
    )
    dispatch_key: str = Field(
        sa_column=Column(
            "DISPATCH_KEY",
            String(160),
            nullable=False,
        ),
    )
    started_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "STARTED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
    ended_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "ENDED_AT",
            DateTime(timezone=True),
        ),
    )
    error_code: str | None = Field(
        default=None,
        sa_column=Column(
            "ERROR_CODE",
            String(128),
        ),
    )
    error_details: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "ERROR_DETAILS",
            JSONB(none_as_null=True),
        ),
    )
    automation_snapshot: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "AUTOMATION_SNAPSHOT",
            JSONB(none_as_null=True),
        ),
    )
    task_execution_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "TASK_EXECUTION_ID",
            Uuid,
            ForeignKey(
                "TASK_EXECUTION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
