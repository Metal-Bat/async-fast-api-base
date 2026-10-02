"""Governed connection metadata and normalized user/group grants."""

from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table


class IntegrationConnectionEntity(BaseEntity, table=True):
    __tablename__ = "INTEGRATION_CONNECTION"
    __table_args__ = (
        Index(
            "uq_INTEGRATION_CONNECTION_CODE_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        Index("ix_INTEGRATION_CONNECTION_provider_kind_status", "PROVIDER", "KIND", "STATUS"),
        Index("ix_INTEGRATION_CONNECTION_owner", "OWNER_USER_ID"),
        CheckConstraint(
            "\"STATUS\" IN ('ACTIVE', 'DISABLED', 'REVOKED')",
            name="ck_INTEGRATION_CONNECTION_status",
        ),
        CheckConstraint(
            "\"VERIFICATION_STATUS\" IN ('UNVERIFIED', 'VERIFIED', 'FAILED')",
            name="ck_INTEGRATION_CONNECTION_verified",
        ),
    )
    code: str = Field(
        sa_column=Column(
            "CODE",
            String(64),
            nullable=False,
        ),
    )
    name: str = Field(
        sa_column=Column(
            "NAME",
            String(255),
            nullable=False,
        ),
    )
    provider: str = Field(
        sa_column=Column(
            "PROVIDER",
            String(64),
            nullable=False,
        ),
    )
    kind: str = Field(
        sa_column=Column(
            "KIND",
            String(32),
            nullable=False,
        ),
    )
    non_secret_config: dict[str, Any] = Field(
        sa_column=Column(
            "NON_SECRET_CONFIG",
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    secret_ref: str = Field(
        sa_column=Column(
            "SECRET_REF",
            String(64),
            nullable=False,
        ),
    )
    secret_version: str = Field(
        sa_column=Column(
            "SECRET_VERSION",
            String(64),
            nullable=False,
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
    verification_status: str = Field(
        default="UNVERIFIED",
        sa_column=Column(
            "VERIFICATION_STATUS",
            String(16),
            nullable=False,
        ),
    )
    owner_user_id: UUID = Field(
        sa_column=Column(
            "OWNER_USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )


ConnectionHistoryTable = create_history_table(
    IntegrationConnectionEntity.__table__,  # ty:ignore[unresolved-attribute]
    ondelete="RESTRICT",
    onupdate="RESTRICT",
)
Index(
    "ix_INTEGRATION_CONNECTION_HISTORY_entity_changed",
    ConnectionHistoryTable.c.ENTITY_ID,
    ConnectionHistoryTable.c.CHANGED_AT,
)
