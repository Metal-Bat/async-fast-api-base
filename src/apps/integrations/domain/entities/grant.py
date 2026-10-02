"""Governed connection metadata and normalized user/group grants."""

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Index, Uuid, text
from sqlmodel import Field

from core.base_entity import BaseEntity


class IntegrationConnectionGrantEntity(BaseEntity, table=True):
    __tablename__ = "INTEGRATION_CONNECTION_GRANT"
    __table_args__ = (
        CheckConstraint(
            '("USER_ID" IS NOT NULL)::int + ("WORK_GROUP_ID" IS NOT NULL)::int = 1',
            name="ck_INTEGRATION_CONNECTION_GRANT_target",
        ),
        CheckConstraint(
            '"CAN_USE" OR "CAN_MANAGE"', name="ck_INTEGRATION_CONNECTION_GRANT_capability"
        ),
        Index(
            "uq_INTEGRATION_CONNECTION_GRANT_user",
            "INTEGRATION_CONNECTION_ID",
            "USER_ID",
            unique=True,
            postgresql_where=text('"USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
        ),
        Index(
            "uq_INTEGRATION_CONNECTION_GRANT_group",
            "INTEGRATION_CONNECTION_ID",
            "WORK_GROUP_ID",
            unique=True,
            postgresql_where=text('"WORK_GROUP_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
        ),
        Index("ix_INTEGRATION_CONNECTION_GRANT_user", "USER_ID"),
        Index("ix_INTEGRATION_CONNECTION_GRANT_group", "WORK_GROUP_ID"),
    )
    integration_connection_id: UUID = Field(
        sa_column=Column(
            "INTEGRATION_CONNECTION_ID",
            Uuid,
            ForeignKey(
                "INTEGRATION_CONNECTION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    user_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    work_group_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            "WORK_GROUP_ID",
            Uuid,
            ForeignKey(
                "WORK_GROUP.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
        ),
    )
    can_use: bool = Field(
        default=True,
        sa_column=Column(
            "CAN_USE",
            Boolean,
            nullable=False,
        ),
    )
    can_manage: bool = Field(
        default=False,
        sa_column=Column(
            "CAN_MANAGE",
            Boolean,
            nullable=False,
        ),
    )
