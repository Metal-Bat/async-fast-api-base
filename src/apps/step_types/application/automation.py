"""Trusted background-operation catalog used by authoring and runtime."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AutomationOperation:
    key: str
    handler_key: str
    handler_version: str


_OPERATIONS = {
    "connection.status": AutomationOperation("connection.status", "service_task", "1"),
}


def resolve_operation(key: str, handler_key: str, handler_version: str) -> AutomationOperation:
    """Resolve only code-owned operations compatible with the pinned handler."""
    operation = _OPERATIONS.get(key)
    if operation is None or (operation.handler_key, operation.handler_version) != (
        handler_key,
        handler_version,
    ):
        raise ValueError("Background operation is not registered for this handler")
    return operation
