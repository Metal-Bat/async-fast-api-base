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


class FormSubmissionEntity(BaseEntity, table=True):
    __tablename__ = "FORM_SUBMISSION"
    __table_args__ = (
        Index(
            "uq_FORM_SUBMISSION_request_initial",
            "BUSINESS_REQUEST_ID",
            unique=True,
            postgresql_where=text('"STEP_EXECUTION_ID" IS NULL'),
        ),
        Index(
            "uq_FORM_SUBMISSION_step_execution",
            "STEP_EXECUTION_ID",
            unique=True,
            postgresql_where=text('"STEP_EXECUTION_ID" IS NOT NULL'),
        ),
        Index("ix_FORM_SUBMISSION_form", "FORM_VERSION_ID"),
        Index("ix_FORM_SUBMISSION_actor", "SUBMITTED_BY_USER_ID"),
        Index(
            "uq_FORM_SUBMISSION_correction_source",
            "CORRECTION_SOURCE_SUBMISSION_ID",
            unique=True,
            postgresql_where=text('"CORRECTION_SOURCE_SUBMISSION_ID" IS NOT NULL'),
        ),
        CheckConstraint(
            "\"STATUS\" IN ('DRAFT','SUBMITTED','ABANDONED')",
            name="ck_FORM_SUBMISSION_status",
        ),
        CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "SUBMITTED_AT" IS NULL AND '
            '"SUBMITTED_BY_USER_ID" IS NULL) OR '
            '("STATUS" = \'SUBMITTED\' AND "SUBMITTED_AT" IS NOT NULL AND '
            '"SUBMITTED_BY_USER_ID" IS NOT NULL) OR "STATUS" = \'ABANDONED\'',
            name="ck_FORM_SUBMISSION_lifecycle",
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
    form_version_id: UUID = Field(
        sa_column=Column(
            "FORM_VERSION_ID",
            Uuid,
            ForeignKey(
                "FORM_VERSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
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
    submitted_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "SUBMITTED_BY_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
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
    data: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "DATA",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    item_identity: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "ITEM_IDENTITY",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    override_provenance: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "OVERRIDE_PROVENANCE",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    correction_source_submission_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "CORRECTION_SOURCE_SUBMISSION_ID",
            Uuid,
            ForeignKey(
                "FORM_SUBMISSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=True,
        ),
    )
    correction_feedback: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(
            "CORRECTION_FEEDBACK",
            JSONB(none_as_null=True),
            nullable=True,
        ),
    )
    design_snapshot: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            "DESIGN_SNAPSHOT",
            JSONB,
        ),
    )
    submitted_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "SUBMITTED_AT",
            DateTime(timezone=True),
        ),
    )


class FormSubmissionAttachmentEntity(BaseEntity, table=True):
    """Audited ordered link between a form field and one user-owned upload."""

    __tablename__ = "FORM_SUBMISSION_ATTACHMENT"
    __table_args__ = (
        Index(
            "uq_FORM_SUBMISSION_ATTACHMENT_active_position",
            "FORM_SUBMISSION_ID",
            "FIELD_PATH",
            "POSITION",
            unique=True,
            postgresql_where=text("\"STATUS\" = 'ACTIVE'"),
        ),
        Index(
            "ix_FORM_SUBMISSION_ATTACHMENT_collection",
            "FORM_SUBMISSION_ID",
            "FIELD_PATH",
            "STATUS",
            "POSITION",
        ),
        Index("ix_FORM_SUBMISSION_ATTACHMENT_upload", "USER_UPLOAD_ID"),
        Index("ix_FORM_SUBMISSION_ATTACHMENT_added_by", "ADDED_BY_USER_ID"),
        Index("ix_FORM_SUBMISSION_ATTACHMENT_group", "CONTRIBUTING_GROUP_ID"),
        CheckConstraint('"POSITION" >= 0', name="ck_FORM_SUBMISSION_ATTACHMENT_position"),
        CheckConstraint(
            "\"STATUS\" IN ('ACTIVE','REMOVED')",
            name="ck_FORM_SUBMISSION_ATTACHMENT_status",
        ),
        CheckConstraint(
            '("STATUS" = \'ACTIVE\' AND "REMOVED_AT" IS NULL AND '
            '"REMOVED_BY_USER_ID" IS NULL) OR '
            '("STATUS" = \'REMOVED\' AND "REMOVED_AT" IS NOT NULL AND '
            '"REMOVED_BY_USER_ID" IS NOT NULL)',
            name="ck_FORM_SUBMISSION_ATTACHMENT_lifecycle",
        ),
    )
    form_submission_id: UUID = Field(
        sa_column=Column(
            "FORM_SUBMISSION_ID",
            Uuid,
            ForeignKey(
                "FORM_SUBMISSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    field_path: str = Field(
        sa_column=Column(
            "FIELD_PATH",
            String(1024),
            nullable=False,
        ),
    )
    user_upload_id: UUID = Field(
        sa_column=Column(
            "USER_UPLOAD_ID",
            Uuid,
            ForeignKey(
                "USER_UPLOAD.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    added_by_user_id: UUID = Field(
        sa_column=Column(
            "ADDED_BY_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    contributing_group_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "CONTRIBUTING_GROUP_ID",
            Uuid,
            ForeignKey(
                "WORK_GROUP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    position: int = Field(
        sa_column=Column(
            "POSITION",
            Integer,
            nullable=False,
        ),
    )
    caption: str | None = Field(
        default=None,
        sa_column=Column(
            "CAPTION",
            String(1024),
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
    removed_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "REMOVED_BY_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    removed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "REMOVED_AT",
            DateTime(timezone=True),
        ),
    )
