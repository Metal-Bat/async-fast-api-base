"""Normalized human work-item persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
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
from sqlmodel import Field, SQLModel

from core.base_entity import BaseEntity
from utils.date_utils import get_datetime_utc


class WorkItemEntity(BaseEntity, table=True):
    __tablename__ = "WORK_ITEM"
    __table_args__ = (
        Index(
            "uq_WORK_ITEM_live_execution",
            "STEP_EXECUTION_ID",
            unique=True,
            postgresql_where=text("\"STATUS\" IN ('OPEN','CLAIMED','IN_PROGRESS')"),
        ),
        Index(
            "ix_WORK_ITEM_cartable",
            "STATUS",
            text('"PRIORITY" DESC'),
            text('"DUE_AT" ASC NULLS LAST'),
            "CREATED_AT",
            "ID",
        ),
        Index("ix_WORK_ITEM_claimant_status", "CLAIMED_BY_USER_ID", "STATUS"),
        Index("ix_WORK_ITEM_request", "BUSINESS_REQUEST_ID"),
        Index("ix_WORK_ITEM_form", "FORM_VERSION_ID"),
        CheckConstraint(
            "\"STATUS\" IN ('OPEN','CLAIMED','IN_PROGRESS','COMPLETED','REJECTED','RETURNED','CANCELLED','EXPIRED')",
            name="ck_WORK_ITEM_status",
        ),
        CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_WORK_ITEM_priority"),
        CheckConstraint(
            '(("CLAIMED_BY_USER_ID" IS NULL) = ("CLAIMED_AT" IS NULL))',
            name="ck_WORK_ITEM_claim_pair",
        ),
        CheckConstraint(
            "\"STATUS\" NOT IN ('CLAIMED','IN_PROGRESS') OR \"CLAIMED_BY_USER_ID\" IS NOT NULL",
            name="ck_WORK_ITEM_active_claimant",
        ),
        CheckConstraint(
            "(\"STATUS\" IN ('OPEN','CLAIMED','IN_PROGRESS')) = (\"CLOSED_AT\" IS NULL)",
            name="ck_WORK_ITEM_closed",
        ),
        CheckConstraint('"DELETED_AT" IS NULL', name="ck_WORK_ITEM_not_deleted"),
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
    status: str = Field(
        default="OPEN",
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
    claimed_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "CLAIMED_BY_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    claimed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "CLAIMED_AT",
            DateTime(timezone=True),
        ),
    )
    due_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "DUE_AT",
            DateTime(timezone=True),
        ),
    )
    form_version_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "FORM_VERSION_ID",
            Uuid,
            ForeignKey(
                "FORM_VERSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    outcome_key: str | None = Field(
        default=None,
        sa_column=Column(
            "OUTCOME_KEY",
            String(64),
        ),
    )
    closed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "CLOSED_AT",
            DateTime(timezone=True),
        ),
    )


class WorkItemCandidateEntity(SQLModel, table=True):
    __tablename__ = "WORK_ITEM_CANDIDATE"
    __table_args__ = (
        CheckConstraint(
            '(num_nonnulls("USER_ID", "WORK_GROUP_ID") = 1)',
            name="ck_WORK_ITEM_CANDIDATE_principal",
        ),
        Index(
            "uq_WORK_ITEM_CANDIDATE_user",
            "WORK_ITEM_ID",
            "USER_ID",
            unique=True,
            postgresql_where=text('"USER_ID" IS NOT NULL'),
        ),
        Index(
            "uq_WORK_ITEM_CANDIDATE_group",
            "WORK_ITEM_ID",
            "WORK_GROUP_ID",
            unique=True,
            postgresql_where=text('"WORK_GROUP_ID" IS NOT NULL'),
        ),
        Index("ix_WORK_ITEM_CANDIDATE_user_item", "USER_ID", "WORK_ITEM_ID"),
        Index("ix_WORK_ITEM_CANDIDATE_group_item", "WORK_GROUP_ID", "WORK_ITEM_ID"),
        Index("ix_WORK_ITEM_CANDIDATE_source", "SOURCE_TARGET_ID"),
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
    user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    work_group_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "WORK_GROUP_ID",
            Uuid,
            ForeignKey(
                "WORK_GROUP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    source_target_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "SOURCE_TARGET_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_STEP_TARGET.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    can_claim: bool = Field(
        default=True,
        sa_column=Column(
            "CAN_CLAIM",
            Boolean,
            nullable=False,
            server_default=text("true"),
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
