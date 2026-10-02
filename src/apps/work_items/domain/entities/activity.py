"""Normalized human work-item persistence."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from utils.date_utils import get_datetime_utc


class WorkItemActionEntity(SQLModel, table=True):
    __tablename__ = "WORK_ITEM_ACTION"
    __table_args__ = (
        UniqueConstraint("WORK_ITEM_ID", "COMMAND_KEY", name="uq_WORK_ITEM_ACTION_command"),
        Index("ix_WORK_ITEM_ACTION_timeline", "WORK_ITEM_ID", "OCCURRED_AT", "ID"),
        Index("ix_WORK_ITEM_ACTION_actor", "ACTOR_USER_ID"),
        Index("ix_WORK_ITEM_ACTION_submission", "FORM_SUBMISSION_ID"),
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
    action: str = Field(
        sa_column=Column(
            "ACTION",
            String(32),
            nullable=False,
        ),
    )
    outcome_key: str | None = Field(
        default=None,
        sa_column=Column(
            "OUTCOME_KEY",
            String(64),
        ),
    )
    form_submission_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "FORM_SUBMISSION_ID",
            Uuid,
            ForeignKey(
                "FORM_SUBMISSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    comment: str | None = Field(
        default=None,
        sa_column=Column(
            "COMMENT",
            String(4000),
        ),
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "DETAILS",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    command_key: str = Field(
        sa_column=Column(
            "COMMAND_KEY",
            String(128),
            nullable=False,
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


class UserWorkItemStateEntity(SQLModel, table=True):
    __tablename__ = "USER_WORK_ITEM_STATE"
    __table_args__ = (
        Index("ix_USER_WORK_ITEM_STATE_item_user", "WORK_ITEM_ID", "USER_ID"),
        Index("ix_USER_WORK_ITEM_STATE_user_pinned", "USER_ID", "PINNED_AT"),
        Index("ix_USER_WORK_ITEM_STATE_user_watching", "USER_ID", "WATCHING_AT"),
    )
    user_id: UUID = Field(
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            primary_key=True,
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
            primary_key=True,
        ),
    )
    read_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "READ_AT",
            DateTime(timezone=True),
        ),
    )
    pinned_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "PINNED_AT",
            DateTime(timezone=True),
        ),
    )
    archived_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "ARCHIVED_AT",
            DateTime(timezone=True),
        ),
    )
    watching_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "WATCHING_AT",
            DateTime(timezone=True),
        ),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "UPDATED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
