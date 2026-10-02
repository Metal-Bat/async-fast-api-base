"""Durable per-logical-task AI limits and per-dispatch reservations."""

from sqlalchemy import (
    Index,
)

from apps.ai.domain.entities.agent import AIAgentEntity
from apps.ai.domain.entities.approval import AIToolApprovalEntity
from apps.ai.domain.entities.budget import AIReservationEntity, AITaskBudgetEntity
from core.history import create_history_table

for entity in (AITaskBudgetEntity, AIReservationEntity, AIAgentEntity):
    table = create_history_table(entity.__table__, ondelete="RESTRICT", onupdate="RESTRICT")  # ty:ignore[unresolved-attribute]
    Index(f"ix_{table.name}_entity_changed", table.c.ENTITY_ID, table.c.CHANGED_AT)


__all__ = ["AIAgentEntity", "AIReservationEntity", "AITaskBudgetEntity", "AIToolApprovalEntity"]
