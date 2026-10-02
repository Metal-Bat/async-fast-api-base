"""Normalized work-group and membership entities."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from utils.date_utils import get_datetime_utc


class WorkGroupMemberEntity(SQLModel, table=True):
    __tablename__ = "WORK_GROUP_MEMBER"
    __table_args__ = (
        CheckConstraint(
            '("IS_ACTIVE" AND "LEFT_AT" IS NULL) OR NOT "IS_ACTIVE"',
            name="ck_WORK_GROUP_MEMBER_lifecycle",
        ),
        Index("ix_WORK_GROUP_MEMBER_user_active_group", "USER_ID", "IS_ACTIVE", "WORK_GROUP_ID"),
        Index("ix_WORK_GROUP_MEMBER_added_by", "ADDED_BY_USER_ID"),
    )

    work_group_id: UUID = Field(
        sa_column=Column(
            "WORK_GROUP_ID",
            Uuid,
            ForeignKey(
                "WORK_GROUP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            primary_key=True,
        ),
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
    is_active: bool = Field(
        default=True,
        sa_column=Column(
            "IS_ACTIVE",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )
    joined_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(
            "JOINED_AT",
            DateTime(timezone=True),
            nullable=False,
        ),
    )
    left_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "LEFT_AT",
            DateTime(timezone=True),
        ),
    )
    added_by_user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "ADDED_BY_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "UPDATED_AT",
            DateTime(timezone=True),
        ),
    )
