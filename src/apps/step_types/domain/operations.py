"""Safe code-owned business operation metadata for workflow inspectors."""

from typing import Any, Literal

from pydantic import Field

from core.base_dto import BaseDTO


class BusinessOperationDTO(BaseDTO):
    operation_key: str = Field(
        description="Exact code-owned operation identifier and version; no arbitrary HTTP scripting."
    )
    handler_key: str = Field(description="Required deployed step handler key.")
    handler_version: str = Field(description="Required exact deployed handler version.")
    execution_scopes: list[Literal["NORMAL", "COMPENSATION"]] = Field(
        description="Allowed execution contexts; sandbox cancellation is compensation-only."
    )
    allowed_providers: list[str] = Field(description="Compatible registered connection providers.")
    connection_kind: Literal["SERVICE"] = Field(
        default="SERVICE",
        description="Required connection kind; AI and notification connections are incompatible.",
    )
    execution_principal: Literal["publisher"] = Field(
        default="publisher",
        description="Pinned workflow publisher; protected sandbox effects require an active ordinary publisher.",
    )
    authentication: Literal["bearer_secret"] = Field(
        default="bearer_secret",
        description="Credential mode; secret values and references remain private.",
    )
    endpoint_source: Literal["admin_owned"] = Field(
        default="admin_owned",
        description="Endpoint resolved by an administrator-owned key, never an authored URL.",
    )
    approval_policy: str | None = Field(
        description="Versioned required human approval policy for create, otherwise null; tool approval is distinct."
    )
    has_business_effect: bool = Field(
        description="Whether execution changes sandbox business state; metadata inspection has no effect."
    )
    timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Total network deadline in seconds; a timeout does not prove provider rollback.",
    )
    retry_policy: Literal["diagnostic_retry", "reconcile_before_retry"] = Field(
        description="Diagnostic retries or lookup-only recovery after uncertain business dispatch."
    )
    reconciliation: Literal["receipt_lookup"] | None = Field(
        description="Supported operation-specific receipt lookup, otherwise null."
    )
    compensation: Literal["cancel_order"] | None = Field(
        default=None,
        description="Supported explicit reversal family; null means no registered automated reversal.",
    )
    input_schema: dict[str, Any] = Field(
        description="Code-owned JSON Schema, not authored HTTP configuration."
    )
    output_schema: dict[str, Any] = Field(
        description="Code-owned JSON Schema for the bounded result port."
    )
