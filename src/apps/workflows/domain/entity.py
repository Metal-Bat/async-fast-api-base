"""Persisted workflow definitions, immutable versions, and graph snapshots."""

from sqlalchemy import (
    Index,
)

from apps.workflows.domain.entities.definition import (
    WorkflowAccessGrantEntity,
    WorkflowDefinitionEntity,
    WorkflowVersionEntity,
)
from apps.workflows.domain.entities.graph import (
    WorkflowStepEntity,
    WorkflowStepInputBindingEntity,
    WorkflowStepTargetEntity,
    WorkflowTransitionEntity,
)
from core.history import create_history_table

for entity in (WorkflowDefinitionEntity, WorkflowVersionEntity):
    table = create_history_table(entity.__table__, ondelete="RESTRICT", onupdate="RESTRICT")  # ty:ignore[unresolved-attribute]
    Index(f"ix_{table.name}_entity_changed", table.c.ENTITY_ID, table.c.CHANGED_AT)


__all__ = [
    "WorkflowAccessGrantEntity",
    "WorkflowDefinitionEntity",
    "WorkflowStepEntity",
    "WorkflowStepInputBindingEntity",
    "WorkflowStepTargetEntity",
    "WorkflowTransitionEntity",
    "WorkflowVersionEntity",
]
