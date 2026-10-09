"""Compact self acknowledgment state: one row per actor/key/revision/locale."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, Uuid
from sqlmodel import Field, SQLModel


class HelpStateEntity(SQLModel, table=True):
    __tablename__ = "USER_HELP_STATE"
    __table_args__ = (
        CheckConstraint("\"LOCALE\" IN ('en', 'fa')", name="ck_USER_HELP_STATE_locale"),
        CheckConstraint(
            '("FIRST_VIEWED_AT" IS NULL AND "LAST_VIEWED_AT" IS NULL) OR ("FIRST_VIEWED_AT" IS NOT NULL AND "LAST_VIEWED_AT" >= "FIRST_VIEWED_AT")',
            name="ck_USER_HELP_STATE_viewed",
        ),
    )
    user_id: UUID = Field(
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="CASCADE",
                onupdate="RESTRICT",
            ),
            primary_key=True,
        ),
    )
    help_key: str = Field(
        sa_column=Column(
            "HELP_KEY",
            String(64),
            primary_key=True,
        ),
    )
    revision: str = Field(
        sa_column=Column(
            "REVISION",
            String(64),
            primary_key=True,
        ),
    )
    locale: str = Field(
        sa_column=Column(
            "LOCALE",
            String(2),
            primary_key=True,
        ),
    )
    first_viewed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "FIRST_VIEWED_AT",
            DateTime(timezone=True),
            nullable=True,
        ),
    )
    last_viewed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "LAST_VIEWED_AT",
            DateTime(timezone=True),
            nullable=True,
        ),
    )
    dismissed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "DISMISSED_AT",
            DateTime(timezone=True),
            nullable=True,
        ),
    )
