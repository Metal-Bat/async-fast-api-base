"""Private event rows; actual workflow deadlines remain owned by work items."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table


class CalendarEventEntity(BaseEntity, table=True):
    __tablename__ = "CALENDAR_EVENT"
    __table_args__ = (
        CheckConstraint(
            '("KIND" = \'timed\' AND "START_AT" IS NOT NULL AND "END_AT" IS NOT NULL AND "END_AT" > "START_AT" AND "START_DATE" IS NULL AND "END_DATE" IS NULL) OR ("KIND" = \'all_day\' AND "START_DATE" IS NOT NULL AND "END_DATE" IS NOT NULL AND "END_DATE" > "START_DATE" AND "START_AT" IS NULL AND "END_AT" IS NULL)',
            name="ck_CALENDAR_EVENT_shape",
        ),
    )
    owner_id: UUID = Field(
        foreign_key="USER.ID",
        sa_type=Uuid,
        nullable=False,
        index=True,
        sa_column_kwargs={"name": "OWNER_ID"},
    )
    work_group_id: UUID | None = Field(
        default=None,
        foreign_key="WORK_GROUP.ID",
        sa_type=Uuid,
        nullable=True,
        index=True,
        sa_column_kwargs={"name": "WORK_GROUP_ID"},
    )
    title: str = Field(
        sa_type=String(120),
        nullable=False,
        sa_column_kwargs={"name": "TITLE"},
    )
    kind: str = Field(
        sa_type=String(16),
        nullable=False,
        sa_column_kwargs={"name": "KIND"},
    )
    timezone: str = Field(
        sa_type=String(64),
        nullable=False,
        sa_column_kwargs={"name": "TIMEZONE"},
    )
    start_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
        index=True,
        sa_column_kwargs={"name": "START_AT"},
    )
    end_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
        sa_column_kwargs={"name": "END_AT"},
    )
    start_date: date | None = Field(
        default=None,
        sa_type=Date,
        nullable=True,
        index=True,
        sa_column_kwargs={"name": "START_DATE"},
    )
    end_date: date | None = Field(
        default=None,
        sa_type=Date,
        nullable=True,
        sa_column_kwargs={"name": "END_DATE"},
    )
    document: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSONB,
        nullable=False,
        sa_column_kwargs={"name": "DOCUMENT"},
    )


CalendarEventHistory = create_history_table(getattr(CalendarEventEntity, "__table__"))  # noqa: B009
CalendarEventHistory.info["self_only"] = True
