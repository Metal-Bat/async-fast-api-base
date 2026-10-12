"""Allowed process AI evidence, separate from private prompts and checkpoints."""

from pydantic import Field

from apps.ai.domain.budget import AIBudgetStatus
from apps.ai.domain.contracts import AIDecision
from core.base_dto import BaseDTO


class AIProcessEvidenceDTO(BaseDTO):
    step_execution_ref_id: str = Field(
        description="Current opaque AI execution reference; this endpoint is read-only."
    )
    attempt_number: int = Field(
        ge=1, description="Latest persisted attempt number within the logical AI execution."
    )
    status: str = Field(
        description="Existing automation attempt state; queued or failed does not imply a recommendation."
    )
    agent_ref_id: str | None = Field(
        description="Exact historical agent pin; never a substituted latest agent."
    )
    agent_available: bool = Field(
        description="Whether the exact pinned published/retired agent metadata remains available."
    )
    model_id: str | None = Field(
        description="Model identity from the exact agent pin, not a substituted latest model."
    )
    allowed_input_fields: list[str] = Field(
        description="Approved field names only; no copied input values."
    )
    recommendation: AIDecision | None = Field(
        description="Typed model recommendation; confidence never grants business approval."
    )
    budget: AIBudgetStatus | None = Field(
        description="Existing task-wide budget, reservation and unknown-usage evidence; no new provider call."
    )
