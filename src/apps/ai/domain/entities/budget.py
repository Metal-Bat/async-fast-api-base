"""Durable per-logical-task AI limits and per-dispatch reservations."""

from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity


class AITaskBudgetEntity(BaseEntity, table=True):
    __tablename__ = "AI_TASK_BUDGET"
    __table_args__ = (
        Index("uq_AI_TASK_BUDGET_execution", "STEP_EXECUTION_ID", unique=True),
        CheckConstraint("\"CURRENCY\" = 'USD'", name="ck_AI_TASK_BUDGET_currency"),
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
    effective_limits: dict[str, Any] = Field(
        sa_column=Column(
            "EFFECTIVE_LIMITS",
            JSONB,
            nullable=False,
        ),
    )
    used: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "USED",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    reserved: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "RESERVED",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    currency: str = Field(
        default="USD",
        sa_column=Column(
            "CURRENCY",
            String(3),
            nullable=False,
        ),
    )
    price_version: str = Field(
        sa_column=Column(
            "PRICE_VERSION",
            String(128),
            nullable=False,
        ),
    )


class AIReservationEntity(BaseEntity, table=True):
    __tablename__ = "AI_RESERVATION"
    __table_args__ = (
        Index("uq_AI_RESERVATION_task_key", "TASK_BUDGET_ID", "RESERVATION_KEY", unique=True),
        CheckConstraint(
            "\"STATUS\" IN ('RESERVED', 'SETTLED', 'UNKNOWN', 'NOT_DISPATCHED')",
            name="ck_AI_RESERVATION_status",
        ),
    )
    task_budget_id: UUID = Field(
        sa_column=Column(
            "TASK_BUDGET_ID",
            Uuid,
            ForeignKey(
                "AI_TASK_BUDGET.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    reservation_key: str = Field(
        sa_column=Column(
            "RESERVATION_KEY",
            String(128),
            nullable=False,
        ),
    )
    status: str = Field(
        default="RESERVED",
        sa_column=Column(
            "STATUS",
            String(24),
            nullable=False,
        ),
    )
    upper: dict[str, Any] = Field(
        sa_column=Column(
            "UPPER_BOUND",
            JSONB,
            nullable=False,
        ),
    )
    actual: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "ACTUAL_USAGE",
            JSONB,
        ),
    )
    model_used: str | None = Field(
        default=None,
        sa_column=Column(
            "MODEL_USED",
            String(255),
        ),
    )
