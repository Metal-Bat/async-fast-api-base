"""Pinned request types, business requests, and form submissions."""

from sqlalchemy import (
    Index,
)

from apps.requests.domain.entities.request import BusinessRequestEntity
from apps.requests.domain.entities.submission import (
    FormSubmissionAttachmentEntity,
    FormSubmissionEntity,
)
from apps.requests.domain.entities.types import RequestTypeClientTargetEntity, RequestTypeEntity
from core.history import create_history_table

table = create_history_table(
    RequestTypeEntity.__table__,  # ty:ignore[unresolved-attribute]
    ondelete="RESTRICT",
    onupdate="RESTRICT",
)
Index(f"ix_{table.name}_entity_changed", table.c.ENTITY_ID, table.c.CHANGED_AT)

client_target_history = create_history_table(
    RequestTypeClientTargetEntity.__table__,  # ty:ignore[unresolved-attribute]
    ondelete="RESTRICT",
    onupdate="RESTRICT",
)
Index(
    f"ix_{client_target_history.name}_entity_changed",
    client_target_history.c.ENTITY_ID,
    client_target_history.c.CHANGED_AT,
)

attachment_history = create_history_table(
    FormSubmissionAttachmentEntity.__table__,  # ty:ignore[unresolved-attribute]
    ondelete="RESTRICT",
    onupdate="RESTRICT",
)
Index(
    f"ix_{attachment_history.name}_entity_changed",
    attachment_history.c.ENTITY_ID,
    attachment_history.c.CHANGED_AT,
)

submission_history = create_history_table(
    FormSubmissionEntity.__table__,  # ty:ignore[unresolved-attribute]
    ondelete="RESTRICT",
    onupdate="RESTRICT",
)
Index(
    f"ix_{submission_history.name}_entity_changed",
    submission_history.c.ENTITY_ID,
    submission_history.c.CHANGED_AT,
)


__all__ = [
    "BusinessRequestEntity",
    "FormSubmissionAttachmentEntity",
    "FormSubmissionEntity",
    "RequestTypeClientTargetEntity",
    "RequestTypeEntity",
]
