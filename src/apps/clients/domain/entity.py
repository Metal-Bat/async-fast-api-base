"""Registered client identities and their explicitly supported releases."""

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table


class ClientEntity(BaseEntity, table=True):
    __tablename__ = "CLIENT"
    __table_args__ = (
        Index(
            "uq_CLIENT_code_active",
            "CODE",
            unique=True,
            postgresql_where=text('"DELETED_AT" IS NULL'),
        ),
        CheckConstraint(
            "\"KIND\" IN ('ANDROID','IOS','DESKTOP','WEB','B2B','SDK')", name="ck_CLIENT_kind"
        ),
        CheckConstraint('length("CODE") > 0 AND length("NAME") > 0', name="ck_CLIENT_names"),
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
    kind: str = Field(
        sa_column=Column(
            "KIND",
            String(16),
            nullable=False,
        ),
    )
    platform: str = Field(
        sa_column=Column(
            "PLATFORM",
            String(64),
            nullable=False,
        ),
    )
    secret_hash: str | None = Field(
        default=None,
        sa_column=Column(
            "SECRET_HASH",
            String(64),
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


class ClientReleaseEntity(BaseEntity, table=True):
    __tablename__ = "CLIENT_RELEASE"
    __table_args__ = (
        Index("uq_CLIENT_RELEASE_client_version", "CLIENT_ID", "RELEASE_VERSION", unique=True),
        Index("ix_CLIENT_RELEASE_client_enabled", "CLIENT_ID", "IS_ENABLED"),
        CheckConstraint('length("RELEASE_VERSION") > 0', name="ck_CLIENT_RELEASE_release_version"),
    )
    client_id: UUID = Field(
        sa_column=Column(
            "CLIENT_ID",
            Uuid,
            ForeignKey(
                "CLIENT.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    release_version: str = Field(
        sa_column=Column(
            "RELEASE_VERSION",
            String(64),
            nullable=False,
        ),
    )
    api_version: str = Field(
        sa_column=Column(
            "API_VERSION",
            String(32),
            nullable=False,
        ),
    )
    renderer_capabilities: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "RENDERER_CAPABILITIES",
            JSONB,
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
    )
    is_enabled: bool = Field(
        default=True,
        sa_column=Column(
            "IS_ENABLED",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )


for entity in (ClientEntity, ClientReleaseEntity):
    table = create_history_table(entity.__table__, ondelete="RESTRICT", onupdate="RESTRICT")  # ty:ignore[unresolved-attribute]
    Index(f"ix_{table.name}_entity_changed", table.c.ENTITY_ID, table.c.CHANGED_AT)
