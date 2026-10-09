"""Bounded failure episodes; no exception text, stack, body or provider snapshot."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table
from utils.date_utils import get_datetime_utc


class SupportIncidentEntity(BaseEntity, table=True):
    __tablename__ = "SUPPORT_INCIDENT"
    __table_args__ = (
        UniqueConstraint("FINGERPRINT", "EPISODE", name="uq_SUPPORT_INCIDENT_episode"),
        CheckConstraint(
            "\"STATE\" IN ('OPEN','ACKNOWLEDGED','RESOLVED')", name="ck_SUPPORT_INCIDENT_state"
        ),
        CheckConstraint(
            '"OCCURRENCE_COUNT" BETWEEN 1 AND 1000000', name="ck_SUPPORT_INCIDENT_count"
        ),
    )

    fingerprint: str = Field(
        sa_type=String(64),
        nullable=False,
        index=True,
        sa_column_kwargs={"name": "FINGERPRINT"},
    )
    episode: int = Field(
        default=1,
        sa_type=Integer,
        nullable=False,
        sa_column_kwargs={"name": "EPISODE"},
    )
    category: str = Field(
        sa_type=String(20),
        nullable=False,
        sa_column_kwargs={"name": "CATEGORY"},
    )
    error_code: int = Field(
        sa_type=Integer,
        nullable=False,
        sa_column_kwargs={"name": "ERROR_CODE"},
    )
    operation: str = Field(
        sa_type=String(80),
        nullable=False,
        sa_column_kwargs={"name": "OPERATION"},
    )
    state: str = Field(
        default="OPEN",
        sa_type=String(16),
        nullable=False,
        sa_column_kwargs={"name": "STATE"},
    )
    occurrence_count: int = Field(
        default=1,
        sa_type=Integer,
        nullable=False,
        sa_column_kwargs={"name": "OCCURRENCE_COUNT"},
    )
    last_seen_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"name": "LAST_SEEN_AT"},
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
        sa_column_kwargs={"name": "EXPIRES_AT"},
    )
    request_id: UUID = Field(
        sa_type=Uuid,
        nullable=False,
        sa_column_kwargs={"name": "REQUEST_ID"},
    )
    actor_id: UUID | None = Field(
        default=None,
        sa_type=Uuid,
        nullable=True,
        index=True,
        sa_column_kwargs={"name": "ACTOR_ID"},
    )
    build: str | None = Field(
        default=None,
        sa_type=String(80),
        nullable=True,
        sa_column_kwargs={"name": "BUILD"},
    )
    recent_request_ids: list[str] = Field(
        default_factory=list,
        sa_type=JSONB,
        nullable=False,
        sa_column_kwargs={"name": "RECENT_REQUEST_IDS"},
    )
    rate_window_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"name": "RATE_WINDOW_AT"},
    )
    rate_count: int = Field(
        default=1,
        sa_type=Integer,
        nullable=False,
        sa_column_kwargs={"name": "RATE_COUNT"},
    )


SupportIncidentHistory = create_history_table(
    getattr(SupportIncidentEntity, "__table__"),  # noqa: B009
    ondelete="CASCADE",
)
SupportIncidentHistory.info["self_only"] = True
