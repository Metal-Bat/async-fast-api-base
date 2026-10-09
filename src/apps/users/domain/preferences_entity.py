"""One compact settings row per identity, separate from authority and credentials."""

from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table


class UserPreferencesEntity(BaseEntity, table=True):
    __tablename__ = "USER_PREFERENCES"
    __table_args__ = (
        UniqueConstraint("USER_ID", name="uq_USER_PREFERENCES_user"),
        CheckConstraint(
            'jsonb_typeof("DOCUMENT") = \'object\' AND octet_length("DOCUMENT"::text) <= 4096',
            name="ck_USER_PREFERENCES_document",
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
            nullable=False,
        ),
    )
    document: dict[str, Any] = Field(
        sa_column=Column(
            "DOCUMENT",
            JSONB(),
            nullable=False,
        ),
    )
    avatar_upload_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "AVATAR_UPLOAD_ID",
            Uuid,
            ForeignKey(
                "USER_UPLOAD.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=True,
        ),
    )


UserPreferencesHistoryTable = create_history_table(getattr(UserPreferencesEntity, "__table__"))  # noqa: B009
UserPreferencesHistoryTable.info["self_only"] = True
