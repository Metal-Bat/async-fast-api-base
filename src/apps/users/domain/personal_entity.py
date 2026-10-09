"""Personal state stores canonical favorite identity and bounded private view snapshots."""

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table


class PersonalItemEntity(BaseEntity, table=True):
    __tablename__ = "PERSONAL_ITEM"
    __table_args__ = (
        CheckConstraint("\"KIND\" IN ('view', 'favorite')", name="ck_PERSONAL_ITEM_kind"),
        CheckConstraint(
            'jsonb_typeof("DOCUMENT") = \'object\' AND octet_length("DOCUMENT"::text) <= 24576',
            name="ck_PERSONAL_ITEM_document",
        ),
        CheckConstraint(
            '("KIND" = \'view\' AND "NAME" IS NOT NULL AND "TARGET_ID" IS NULL) OR ("KIND" = \'favorite\' AND "NAME" IS NULL AND "TARGET_ID" IS NOT NULL AND NOT "IS_DEFAULT")',
            name="ck_PERSONAL_ITEM_shape",
        ),
        Index(
            "uq_PERSONAL_ITEM_default",
            "USER_ID",
            "SCOPE",
            unique=True,
            postgresql_where=text('"IS_DEFAULT" AND "DELETED_AT" IS NULL'),
        ),
        Index(
            "uq_PERSONAL_ITEM_name",
            "USER_ID",
            "SCOPE",
            "NAME",
            unique=True,
            postgresql_where=text('"KIND" = \'view\' AND "DELETED_AT" IS NULL'),
        ),
        Index(
            "uq_PERSONAL_ITEM_target",
            "USER_ID",
            "SCOPE",
            "TARGET_ID",
            unique=True,
            postgresql_where=text("\"KIND\" = 'favorite'"),
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
    kind: str = Field(
        sa_column=Column(
            "KIND",
            String(16),
            nullable=False,
        ),
    )
    scope: str = Field(
        sa_column=Column(
            "SCOPE",
            String(32),
            nullable=False,
        ),
    )
    name: str | None = Field(
        default=None,
        sa_column=Column(
            "NAME",
            String(120),
            nullable=True,
        ),
    )
    target_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "TARGET_ID",
            Uuid,
            nullable=True,
        ),
    )
    document: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "DOCUMENT",
            JSONB(),
            nullable=False,
        ),
    )
    is_default: bool = Field(
        default=False,
        sa_column=Column(
            "IS_DEFAULT",
            Boolean,
            nullable=False,
        ),
    )


PersonalItemHistoryTable = create_history_table(getattr(PersonalItemEntity, "__table__"))  # noqa: B009
PersonalItemHistoryTable.info["self_only"] = True
