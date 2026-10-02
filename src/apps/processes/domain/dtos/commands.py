"""Snake-case process runtime commands and views."""

from typing import Any, Literal

from pydantic import ConfigDict, Field, JsonValue

from core.base_dto import BaseDTO


class ResumeProcessDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    command_key: str = Field(min_length=1, max_length=128)
    outcome: str = Field(min_length=1, max_length=64)
    outputs: dict[str, Any] = Field(default_factory=dict)


class ProcessCommandDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    command_key: str = Field(min_length=1, max_length=128)


class RecoveryCommandDTO(ProcessCommandDTO):
    """Operator intent; use a ticket/reason code rather than sensitive free text."""

    action: Literal["retry", "resume", "retry_timer"]
    reason: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    scheduled_action_ref_id: str | None = None


class EventDeliveryDTO(BaseDTO):
    """Validated input shared by authenticated webhook and message adapters."""

    model_config = ConfigDict(extra="forbid", strict=True)
    correlation_key: str = Field(min_length=1, max_length=512)
    delivery_key: str = Field(min_length=1, max_length=128)
    outcome: str = Field(min_length=1, max_length=64)
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class EventDeliveryResultDTO(BaseDTO):
    status: Literal["consumed", "duplicate", "late_ignored", "not_found"]
