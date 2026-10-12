"""Trusted background-operation catalog used by authoring and runtime."""

from dataclasses import dataclass
from typing import Literal

from apps.integrations.domain.contracts import AdapterResult
from apps.integrations.domain.orders import (
    APPROVAL_POLICY,
    ORDER_CANCELLATION_OPERATION,
    PROTECTED_ORDER_OPERATION,
    SandboxCancellationReceipt,
    SandboxOrderPayload,
    SandboxOrderReceipt,
)
from apps.step_types.domain.operations import BusinessOperationDTO


@dataclass(frozen=True, slots=True)
class AutomationOperation:
    key: str
    handler_key: str
    handler_version: str
    allowed_providers: tuple[str, ...] = ("https_status", "https_sandbox_orders")
    approval_policy: str | None = None
    execution_scopes: tuple[Literal["NORMAL", "COMPENSATION"], ...] = ("NORMAL",)


_OPERATIONS = {
    "connection.status": AutomationOperation(
        "connection.status", "service_task", "1", execution_scopes=("NORMAL", "COMPENSATION")
    ),
    PROTECTED_ORDER_OPERATION: AutomationOperation(
        PROTECTED_ORDER_OPERATION,
        "service_task",
        "1",
        ("https_sandbox_orders",),
        APPROVAL_POLICY,
    ),
    ORDER_CANCELLATION_OPERATION: AutomationOperation(
        ORDER_CANCELLATION_OPERATION,
        "service_task",
        "1",
        ("https_sandbox_orders",),
        None,
        ("COMPENSATION",),
    ),
}


def resolve_operation(
    key: str, handler_key: str, handler_version: str, *, execution_scope: str = "NORMAL"
) -> AutomationOperation:
    """Resolve only code-owned operations compatible with the pinned handler."""
    operation = _OPERATIONS.get(key)
    if (
        operation is None
        or execution_scope not in operation.execution_scopes
        or (operation.handler_key, operation.handler_version)
        != (
            handler_key,
            handler_version,
        )
    ):
        raise ValueError("Background operation is not registered for this handler")
    return operation


def operation_catalog() -> list[BusinessOperationDTO]:
    """Bounded deployed catalog; endpoints and credentials are never returned."""
    return [
        BusinessOperationDTO(
            operation_key=operation.key,
            handler_key=operation.handler_key,
            handler_version=operation.handler_version,
            allowed_providers=list(operation.allowed_providers),
            approval_policy=operation.approval_policy,
            execution_scopes=list(operation.execution_scopes),
            has_business_effect=operation.key
            in {PROTECTED_ORDER_OPERATION, ORDER_CANCELLATION_OPERATION},
            retry_policy="reconcile_before_retry"
            if operation.key != "connection.status"
            else "diagnostic_retry",
            reconciliation="receipt_lookup" if operation.key != "connection.status" else None,
            compensation="cancel_order" if operation.key == PROTECTED_ORDER_OPERATION else None,
            input_schema=SandboxOrderPayload.model_json_schema()
            if operation.key == PROTECTED_ORDER_OPERATION
            else SandboxOrderReceipt.model_json_schema()
            if operation.key == ORDER_CANCELLATION_OPERATION
            else {"type": "object"},
            output_schema=SandboxOrderReceipt.model_json_schema()
            if operation.key == PROTECTED_ORDER_OPERATION
            else SandboxCancellationReceipt.model_json_schema()
            if operation.key == ORDER_CANCELLATION_OPERATION
            else AdapterResult.model_json_schema(),
        )
        for operation in _OPERATIONS.values()
    ]
