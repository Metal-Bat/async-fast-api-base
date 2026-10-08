"""Independently revisioned workflow authoring persistence."""

from typing import Any
from uuid import UUID

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table


class WorkflowWorkspaceEntity(BaseEntity, table=True):
    __tablename__ = "WORKFLOW_WORKSPACE"
    __table_args__ = (
        UniqueConstraint("WORKFLOW_VERSION_ID", name="uq_WORKFLOW_WORKSPACE_version"),
    )
    workflow_version_id: UUID = Field(
        sa_column=Column(
            "WORKFLOW_VERSION_ID",
            Uuid,
            ForeignKey(
                "WORKFLOW_VERSION.ID",
                ondelete="RESTRICT",
                onupdate="RESTRICT",
            ),
            nullable=False,
        ),
    )
    document: dict[str, Any] = Field(
        sa_column=Column(
            "DOCUMENT",
            JSONB,
            nullable=False,
        ),
    )
    promoted_graph_checksum: str | None = Field(
        default=None,
        sa_column=Column(
            "PROMOTED_GRAPH_CHECKSUM",
            String(64),
            nullable=True,
        ),
    )


create_history_table(WorkflowWorkspaceEntity.__table__, ondelete="RESTRICT", onupdate="RESTRICT")  # ty:ignore[unresolved-attribute]
