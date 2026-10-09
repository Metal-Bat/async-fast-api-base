"""Source-owned reminder state; PeriodicTask remains the sole timer owner."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, String, Uuid
from sqlmodel import Field

from core.base_entity import BaseEntity


class CalendarReminderEntity(BaseEntity, table=True):
    __tablename__ = "CALENDAR_REMINDER"
    __table_args__ = (
        CheckConstraint(
            "\"STATUS\" IN ('PENDING','SENT','CANCELLED','EXPIRED')",
            name="ck_CALENDAR_REMINDER_status",
        ),
        CheckConstraint(
            '"OFFSET_SECONDS" BETWEEN 0 AND 2592000', name="ck_CALENDAR_REMINDER_offset"
        ),
        CheckConstraint(
            "\"SOURCE_KIND\" IN ('manual','work_item')", name="ck_CALENDAR_REMINDER_source"
        ),
    )
    source_kind: str = Field(
        sa_type=String(16),
        nullable=False,
        sa_column_kwargs={"name": "SOURCE_KIND"},
    )
    source_id: UUID = Field(
        sa_type=Uuid,
        nullable=False,
        index=True,
        sa_column_kwargs={"name": "SOURCE_ID"},
    )
    source_revision: str = Field(
        sa_type=String(64),
        nullable=False,
        sa_column_kwargs={"name": "SOURCE_REVISION"},
    )
    recipient_id: UUID = Field(
        foreign_key="USER.ID",
        sa_type=Uuid,
        nullable=False,
        index=True,
        sa_column_kwargs={"name": "RECIPIENT_ID"},
    )
    schedule_id: UUID = Field(
        foreign_key="PERIODIC_TASK.ID",
        sa_type=Uuid,
        nullable=False,
        unique=True,
        sa_column_kwargs={"name": "SCHEDULE_ID"},
    )
    command_key: str = Field(
        sa_type=String(128),
        nullable=False,
        sa_column_kwargs={"name": "COMMAND_KEY"},
    )
    offset_seconds: int = Field(
        nullable=False,
        sa_column_kwargs={"name": "OFFSET_SECONDS"},
    )
    due_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
        sa_column_kwargs={"name": "DUE_AT"},
    )
    status: str = Field(
        default="PENDING",
        sa_type=String(16),
        nullable=False,
        sa_column_kwargs={"name": "STATUS"},
    )
