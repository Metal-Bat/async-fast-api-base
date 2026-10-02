"""Durable per-logical-task AI limits and per-dispatch reservations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Uuid,
)
from sqlmodel import Field

from core.base_entity import BaseEntity


class AIToolApprovalEntity(BaseEntity, table=True):
    """Encrypted transient checkpoint, audited separately through its work item."""

    __tablename__ = "AI_TOOL_APPROVAL"
    __table_args__ = (
        Index("uq_AI_TOOL_APPROVAL_work_item", "WORK_ITEM_ID", unique=True),
        Index(
            "uq_AI_TOOL_APPROVAL_attempt_call",
            "STEP_EXECUTION_ATTEMPT_ID",
            "TOOL_CALL_ID",
            unique=True,
        ),
        Index("ix_AI_TOOL_APPROVAL_due", "STATUS", "EXPIRES_AT"),
        CheckConstraint(
            "\"STATUS\" IN ('PENDING', 'APPROVED', 'DENIED', 'EXPIRED', 'CANCELLED', 'CONSUMED')",
            name="ck_AI_TOOL_APPROVAL_status",
        ),
        CheckConstraint(
            "(\"STATUS\" IN ('PENDING','APPROVED')) = (\"PAYLOAD_CIPHERTEXT\" IS NOT NULL)",
            name="ck_AI_TOOL_APPROVAL_payload_lifecycle",
        ),
    )
    step_execution_attempt_id: UUID = Field(
        sa_column=Column(
            "STEP_EXECUTION_ATTEMPT_ID",
            Uuid,
            ForeignKey(
                "STEP_EXECUTION_ATTEMPT.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    work_item_id: UUID = Field(
        sa_column=Column(
            "WORK_ITEM_ID",
            Uuid,
            ForeignKey(
                "WORK_ITEM.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    tool_key: str = Field(
        sa_column=Column(
            "TOOL_KEY",
            String(64),
            nullable=False,
        ),
    )
    tool_version: str = Field(
        sa_column=Column(
            "TOOL_VERSION",
            String(128),
            nullable=False,
        ),
    )
    tool_call_id: str = Field(
        sa_column=Column(
            "TOOL_CALL_ID",
            String(128),
            nullable=False,
        ),
    )
    payload_ciphertext: bytes | None = Field(
        default=None,
        sa_column=Column(
            "PAYLOAD_CIPHERTEXT",
            LargeBinary,
        ),
    )
    payload_hash: str = Field(
        sa_column=Column(
            "PAYLOAD_HASH",
            String(64),
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
    expires_at: datetime = Field(
        sa_column=Column(
            "EXPIRES_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
    decided_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "DECIDED_BY_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    decided_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "DECIDED_AT",
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
