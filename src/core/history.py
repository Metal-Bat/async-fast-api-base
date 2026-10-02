from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    Uuid,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import Session

from utils.date_utils import get_datetime_utc

history_modifier: ContextVar[tuple[str, str]] = ContextVar(
    "history_modifier", default=("system", "system")
)


@dataclass(frozen=True, slots=True)
class HistoryContext:
    """Request and actor metadata copied into each audit-history row."""

    modifier_type: str = "system"
    modifier_id: str = "system"
    operation: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    reason: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None


history_context: ContextVar[HistoryContext | None] = ContextVar("history_context", default=None)
SENSITIVE_FIELDS = {
    "HASHED_PASSWORD",
    "PASSWORD",
    "TOKEN",
    "SECRET",
    "ACCESS_TOKEN",
    "REFRESH_TOKEN",
}
_HISTORY_TABLES: dict[str, Table] = {}


@contextmanager
def audit_context(**values: Any) -> Generator[None]:
    """Temporarily enrich ORM and explicit bulk history writes."""
    current = history_context.get() or HistoryContext()
    token: Token[HistoryContext | None] = history_context.set(replace(current, **values))
    try:
        yield
    finally:
        history_context.reset(token)


def create_history_table(
    source: Table,
    metadata: MetaData | None = None,
    *,
    ondelete: str | None = None,
    onupdate: str | None = None,
) -> Table:
    """Create an audit table containing ``FROM_*`` and ``TO_*`` for every business field.

    ``MODIFIER_TYPE`` plus ``MODIFIER_ID`` is an intentionally polymorphic reference. A
    database foreign key cannot target multiple possible tables, so referential validation
    belongs in the application (SQLAlchemy's ``composite()`` only groups values and does not
    provide a generic foreign key).
    """
    metadata = metadata or source.metadata
    source_id = source.c.ID
    history_columns: list[Column[Any]] = [
        Column(
            "ID",
            Uuid,
            primary_key=True,
            server_default=text("uuidv7()"),
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        Column(
            "ENTITY_ID",
            source_id.type,
            ForeignKey(source_id, ondelete=ondelete, onupdate=onupdate),
            nullable=False,
            index=True,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        Column(
            "MODIFIER_TYPE",
            String(255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        Column(
            "MODIFIER_ID",
            String(255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        Column(
            "CHANGED_AT",
            DateTime(timezone=True),
            nullable=False,
            index=True,
            default=get_datetime_utc,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        Column(
            "OPERATION",
            String(32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        Column(
            "REQUEST_ID",
            String(64),
            nullable=True,
            index=True,
            comment="REQUEST CORRELATION ID.",
        ),
        Column(
            "TRACE_ID",
            String(64),
            nullable=True,
            index=True,
            comment="OPENTELEMETRY TRACE ID.",
        ),
        Column(
            "REASON",
            String(1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        Column(
            "SOURCE_IP",
            String(64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        Column(
            "USER_AGENT",
            String(1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
    ]

    excluded = {"ID", "VERSION", "CREATED_AT", "UPDATED_AT", "DELETED_AT"}
    for field in source.columns:
        if field.name in excluded:
            continue
        for prefix in ("FROM", "TO"):
            cloned_type = field.type.copy()
            history_columns.append(
                Column(
                    f"{prefix}_{field.name}",
                    cloned_type,
                    nullable=True,
                    comment=f"{prefix} VALUE OF {field.name} FOR THIS CHANGE.",
                )
            )

    table = Table(f"{source.name}_HISTORY", metadata, *history_columns)
    _HISTORY_TABLES[source.name.lower()] = table
    return table


@event.listens_for(Session, "after_flush")
def write_history(session: Session, *_: Any) -> None:
    """Insert field-level audit rows in the same transaction as entity changes."""
    legacy_modifier_type, legacy_modifier_id = history_modifier.get()
    context = history_context.get() or HistoryContext()
    modifier_type = (
        context.modifier_type if context.modifier_id != "system" else legacy_modifier_type
    )
    modifier_id = context.modifier_id if context.modifier_id != "system" else legacy_modifier_id
    for entity in session.new.union(session.dirty).union(session.deleted):
        state = inspect(entity)
        source = state.mapper.local_table
        history_table = _HISTORY_TABLES.get(source.name.lower())
        if history_table is None or getattr(entity, "id", None) is None:
            continue
        values: dict[str, Any] = {
            "ENTITY_ID": entity.id,
            "MODIFIER_TYPE": modifier_type,
            "MODIFIER_ID": modifier_id,
            "CHANGED_AT": get_datetime_utc(),
            "REQUEST_ID": context.request_id,
            "TRACE_ID": context.trace_id,
            "REASON": context.reason,
            "SOURCE_IP": context.source_ip,
            "USER_AGENT": context.user_agent,
        }
        changed = entity in session.new or entity in session.deleted
        operation = context.operation or (
            "insert"
            if entity in session.new
            else "delete"
            if entity in session.deleted
            else "update"
        )
        deleted_state = state.attrs.get("deleted_at")
        if deleted_state is not None and deleted_state.history.has_changes():
            operation = "restore" if getattr(entity, "deleted_at", None) is None else "soft-delete"
        for field in source.columns:
            if field.name in {"ID", "VERSION", "CREATED_AT", "UPDATED_AT", "DELETED_AT"}:
                continue
            property_key = state.mapper.get_property_by_column(field).key
            attribute = state.attrs[property_key]
            history = attribute.history
            previous = history.deleted[0] if history.deleted else None
            current = getattr(entity, property_key)
            if any(secret in field.name.upper() for secret in SENSITIVE_FIELDS):
                previous = "[REDACTED]" if previous is not None else None
                current = "[REDACTED]" if current is not None else None
            values[f"FROM_{field.name}"] = previous
            values[f"TO_{field.name}"] = current
            changed = changed or history.has_changes()
        if changed:
            values["OPERATION"] = operation
            session.connection().execute(history_table.insert().values(**values))


def history_tables() -> dict[str, Table]:
    """Return a copy of registered history tables for querying and retention jobs."""
    return _HISTORY_TABLES.copy()


def write_bulk_history(
    session: Session,
    source_name: str,
    changes: list[tuple[Any, dict[str, Any], dict[str, Any]]],
    *,
    operation: str = "update",
) -> None:
    """Write history for a bulk statement that bypasses ORM change tracking.

    Args:
        session: Transaction-owning SQLAlchemy session.
        source_name: Registered source table name.
        changes: Entity ID plus before/after values keyed by database column name.
        operation: Bulk operation label.
    """
    table = _HISTORY_TABLES[source_name]
    context = history_context.get() or HistoryContext()
    rows: list[dict[str, Any]] = []
    for entity_id, before, after in changes:
        values: dict[str, Any] = {
            "ENTITY_ID": entity_id,
            "MODIFIER_TYPE": context.modifier_type,
            "MODIFIER_ID": context.modifier_id,
            "CHANGED_AT": get_datetime_utc(),
            "OPERATION": operation,
            "REQUEST_ID": context.request_id,
            "TRACE_ID": context.trace_id,
            "REASON": context.reason,
            "SOURCE_IP": context.source_ip,
            "USER_AGENT": context.user_agent,
        }
        for column in table.columns:
            if not column.name.startswith(("FROM_", "TO_")):
                continue
            prefix, field_name = column.name.split("_", 1)
            value = before.get(field_name) if prefix == "FROM" else after.get(field_name)
            if any(secret in field_name.upper() for secret in SENSITIVE_FIELDS):
                value = "[REDACTED]" if value is not None else None
            values[column.name] = value
        rows.append(values)
    if rows:
        session.connection().execute(table.insert(), rows)
