"""Bounded public receipt projection and explicit operator lookup intent."""

from uuid import UUID

from pydantic import ConfigDict, Field

from apps.integrations.domain.orders import SandboxOrderReceipt
from apps.processes.domain.automation import OrderDispatchState
from apps.processes.domain.dtos.commands import ProcessCommandDTO
from core.base_dto import BaseDTO


class OrderReconciliationDTO(ProcessCommandDTO):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "command_key": "incident-lookup-1",
                    "step_execution_ref_id": "opaque-current-step-reference",
                    "reason": "INC-001",
                }
            ]
        }
    )
    step_execution_ref_id: str = Field(
        min_length=1,
        max_length=4096,
        description="Current opaque step execution reference belonging to the path process.",
    )
    reason: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        description="Safe incident/ticket code, not private free text.",
    )


class SandboxOperationDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    step_execution_ref_id: str = Field(
        description="Current opaque execution reference for a subsequent operator command."
    )
    operation_id: UUID = Field(
        description="Stable external operation identity; never a permission or backend ref."
    )
    state: OrderDispatchState = Field(
        description="Persisted attempt evidence: PREPARED, DISPATCHING, UNKNOWN or CONFIRMED; queued is not completed."
    )
    receipt: SandboxOrderReceipt | None = Field(
        default=None,
        description="Validated provider receipt only when confirmed; never inferred from a timeout.",
    )


class SandboxCancellationRecoveryDTO(BaseDTO):
    step_execution_ref_id: str = Field(
        description="Current opaque reference of the original order execution."
    )
    status: str = Field(
        description="Existing compensation record state; RUNNING is queued, not confirmed cancellation."
    )
