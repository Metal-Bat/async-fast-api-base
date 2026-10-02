"""Versioned form definitions and generated authoring history."""

from sqlalchemy import (
    Index,
)

from apps.forms.domain.entities.definition import FormDefinitionEntity
from apps.forms.domain.entities.version import FormVersionEntity
from core.history import create_history_table

for entity in (FormDefinitionEntity, FormVersionEntity):
    table = create_history_table(entity.__table__, ondelete="RESTRICT", onupdate="RESTRICT")  # ty:ignore[unresolved-attribute]
    Index(f"ix_{table.name}_entity_changed", table.c.ENTITY_ID, table.c.CHANGED_AT)

__all__ = ["FormDefinitionEntity", "FormVersionEntity"]
