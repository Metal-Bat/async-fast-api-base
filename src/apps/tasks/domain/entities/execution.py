from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, Uuid
from sqlmodel import Field

from core.base_entity import BaseEntity


class TaskExecutionEntity(BaseEntity, table=True):
    __tablename__ = "TASK_EXECUTION"

    task_id: str = Field(
        sa_column=Column(
            "TASK_ID",
            String(255),
            unique=True,
            index=True,
            nullable=False,
            comment="CELERY TASK IDENTIFIER.",
        ),
    )
    task_name: str = Field(
        sa_column=Column(
            "TASK_NAME",
            String(255),
            index=True,
            nullable=False,
            comment="REGISTERED TASK NAME.",
        ),
    )
    queue: str | None = Field(
        default=None,
        sa_column=Column(
            "QUEUE",
            String(255),
            nullable=True,
            comment="QUEUE USED FOR EXECUTION.",
        ),
    )
    status: str = Field(
        sa_column=Column(
            "STATUS",
            String(32),
            index=True,
            nullable=False,
            comment="CURRENT CELERY TASK STATE.",
        ),
    )
    args: list[object] | None = Field(
        default=None,
        sa_column=Column(
            "ARGS",
            JSON,
            nullable=True,
            comment="SUBMITTED POSITIONAL ARGUMENTS.",
        ),
    )
    kwargs: dict[str, object] | None = Field(
        default=None,
        sa_column=Column(
            "KWARGS",
            JSON,
            nullable=True,
            comment="SUBMITTED KEYWORD ARGUMENTS.",
        ),
    )
    result: object | None = Field(
        default=None,
        sa_column=Column(
            "RESULT",
            JSON,
            nullable=True,
            comment="JSON-COMPATIBLE TASK RESULT.",
        ),
    )
    traceback: str | None = Field(
        default=None,
        sa_column=Column(
            "TRACEBACK",
            Text,
            nullable=True,
            comment="FAILURE TRACEBACK.",
        ),
    )
    worker: str | None = Field(
        default=None,
        sa_column=Column(
            "WORKER",
            String(255),
            nullable=True,
            comment="WORKER HOSTNAME.",
        ),
    )
    retries: int = Field(
        default=0,
        sa_column=Column(
            "RETRIES",
            Integer,
            nullable=False,
            default=0,
            comment="RETRY COUNT.",
        ),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "STARTED_AT",
            DateTime(timezone=True),
            nullable=True,
            comment="UTC EXECUTION START.",
        ),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "FINISHED_AT",
            DateTime(timezone=True),
            nullable=True,
            comment="UTC EXECUTION FINISH.",
        ),
    )
    duration_seconds: float | None = Field(
        default=None,
        sa_column=Column(
            "DURATION_SECONDS",
            Float,
            nullable=True,
            comment="EXECUTION DURATION IN SECONDS.",
        ),
    )


class TaskIdempotencyEntity(BaseEntity, table=True):
    __tablename__ = "TASK_IDEMPOTENCY"

    key: UUID = Field(
        sa_column=Column(
            "KEY",
            Uuid,
            unique=True,
            index=True,
            nullable=False,
            comment="INTERNAL TIME-SORTABLE UUIDV7 IDEMPOTENCY KEY.",
        ),
    )
    task_id: str = Field(
        sa_column=Column(
            "TASK_ID",
            String(255),
            nullable=False,
            comment="TASK THAT OWNS THE CLAIM.",
        ),
    )
    owner_token: UUID | None = Field(
        default=None,
        sa_column=Column(
            "OWNER_TOKEN",
            Uuid,
            nullable=True,
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
    result: object | None = Field(
        default=None,
        sa_column=Column(
            "RESULT",
            JSON,
            nullable=True,
        ),
    )
    expires_at: datetime = Field(
        sa_column=Column(
            "EXPIRES_AT",
            DateTime(timezone=True),
            nullable=False,
            index=True,
            comment="UTC CLAIM EXPIRATION.",
        ),
    )


class TaskOutboxEntity(BaseEntity, table=True):
    __tablename__ = "TASK_OUTBOX"

    task_id: str = Field(
        sa_column=Column(
            "TASK_ID",
            String(255),
            unique=True,
            nullable=False,
        ),
    )
    task_name: str = Field(
        sa_column=Column(
            "TASK_NAME",
            String(255),
            nullable=False,
        ),
    )
    queue: str = Field(
        sa_column=Column(
            "QUEUE",
            String(255),
            nullable=False,
        ),
    )
    args: list[object] = Field(
        default_factory=list,
        sa_column=Column(
            "ARGS",
            JSON,
            nullable=False,
        ),
    )
    kwargs: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(
            "KWARGS",
            JSON,
            nullable=False,
        ),
    )
    headers: dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(
            "HEADERS",
            JSON,
            nullable=False,
        ),
    )
    priority: int = Field(
        default=0,
        sa_column=Column(
            "PRIORITY",
            Integer,
            nullable=False,
            default=0,
            comment="AMQP MESSAGE PRIORITY.",
        ),
    )
    available_at: datetime = Field(
        sa_column=Column(
            "AVAILABLE_AT",
            DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "PUBLISHED_AT",
            DateTime(timezone=True),
            nullable=True,
            index=True,
        ),
    )
    attempts: int = Field(
        default=0,
        sa_column=Column(
            "ATTEMPTS",
            Integer,
            nullable=False,
        ),
    )
    last_error: str | None = Field(
        default=None,
        sa_column=Column(
            "LAST_ERROR",
            String(255),
            nullable=True,
        ),
    )
