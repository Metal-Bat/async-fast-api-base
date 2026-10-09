"""Immutable replay receipt for a reviewed workflow restore command."""

from uuid import UUID

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint, Uuid
from sqlmodel import Field

from core.base_entity import BaseEntity


class WorkflowRestoreEntity(BaseEntity, table=True):
    __tablename__ = "WORKFLOW_RESTORE"
    __table_args__ = (
        UniqueConstraint(
            "ACTOR_ID", "TARGET_ID", "COMMAND_KEY", name="uq_WORKFLOW_RESTORE_command"
        ),
    )
    actor_id: UUID = Field(
        sa_column=Column(
            "ACTOR_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
            ),
            nullable=False,
        ),
    )
    target_id: UUID = Field(
        sa_column=Column(
            "TARGET_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_VERSION.ID",
            ),
            nullable=False,
        ),
    )
    command_key: str = Field(
        sa_column=Column(
            "COMMAND_KEY",
            String(128),
            nullable=False,
        ),
    )
    plan_hash: str = Field(
        sa_column=Column(
            "PLAN_HASH",
            String(64),
            nullable=False,
        ),
    )
    result_id: UUID = Field(
        sa_column=Column(
            "RESULT_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_VERSION.ID",
            ),
            nullable=False,
        ),
    )
