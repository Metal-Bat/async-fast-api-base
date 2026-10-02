"""Versioned, bounded AI agent definition and price contract."""

from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from apps.ai.domain.budget import BudgetAmounts
from apps.ai.domain.contracts import AIChoice, AIDecisionContract, AIPermittedData, AITaskLimits
from core.base_dto import BaseDTO


class AIInputDecision(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1024)
    options_input_key: str = Field(min_length=1, max_length=64)
    review_below: float = Field(default=0.8, ge=0, le=1)


class AIAgentDraftSpec(BaseDTO):
    """Author-controlled values. All references are resolved at publication."""

    model_config = ConfigDict(extra="forbid")
    connection_ref: str = Field(min_length=1, max_length=128)
    provider_key: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=255)
    prompt_version: str = Field(min_length=1, max_length=128)
    instructions: str = Field(min_length=1, max_length=8192)
    decision: AIDecisionContract | AIInputDecision
    data_policy: AIPermittedData
    field_classifications: dict[str, Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL"]]
    user_limits: AITaskLimits

    @model_validator(mode="after")
    def validate_data_policy(self) -> AIAgentDraftSpec:
        if set(self.field_classifications) != self.data_policy.allowed_fields:
            raise ValueError("Classifications must cover exactly the permitted input fields")
        if self.data_policy.redacted_fields - self.data_policy.allowed_fields:
            raise ValueError("Redactions must name permitted input fields")
        if (
            isinstance(self.decision, AIInputDecision)
            and self.decision.options_input_key not in self.data_policy.allowed_fields
        ):
            raise ValueError("Runtime choices must be a permitted input")
        return self

    def decision_snapshot(self, inputs: dict[str, object]) -> AIDecisionContract:
        if isinstance(self.decision, AIDecisionContract):
            return self.decision
        raw = inputs.get(self.decision.options_input_key)
        if not isinstance(raw, list):
            raise TypeError("Bound decision options must be an array")
        return AIDecisionContract(
            question=self.decision.question,
            options=[AIChoice.model_validate(value) for value in raw],
            review_below=self.decision.review_below,
        )


class AIPrice(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=1, max_length=128)
    input_per_million_usd: Decimal = Field(ge=0)
    output_per_million_usd: Decimal = Field(ge=0)
    fixed_per_request_usd: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def priced(self) -> AIPrice:
        if not any(
            (
                self.fixed_per_request_usd,
                self.input_per_million_usd,
                self.output_per_million_usd,
            )
        ):
            raise ValueError("A zero or unknown AI price cannot be reserved")
        return self

    def upper(self, limits: AITaskLimits, *, attempts: int = 1) -> BudgetAmounts:
        if limits.input_tokens + limits.output_tokens > limits.total_tokens:
            raise ValueError("AI reservation needs a total-token cap covering both token caps")
        if attempts < 1:
            raise ValueError("At least one charged attempt is required")
        spend = (
            self.fixed_per_request_usd
            + self.input_per_million_usd * Decimal(limits.input_tokens) / Decimal(1_000_000)
            + self.output_per_million_usd * Decimal(limits.output_tokens) / Decimal(1_000_000)
        ) * attempts
        limits.require_strict_spend_bound(spend)
        return BudgetAmounts(
            requests=attempts,
            input_tokens=limits.input_tokens * attempts,
            output_tokens=limits.output_tokens * attempts,
            total_tokens=(limits.input_tokens + limits.output_tokens) * attempts,
            spend_usd=spend,
        )

    def actual(self, input_tokens: int, output_tokens: int) -> BudgetAmounts:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Usage counters cannot be negative")
        return BudgetAmounts(
            requests=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            spend_usd=(
                self.fixed_per_request_usd
                + self.input_per_million_usd * Decimal(input_tokens) / Decimal(1_000_000)
                + self.output_per_million_usd * Decimal(output_tokens) / Decimal(1_000_000)
            ),
        )


class AIAgentPublishedSpec(AIAgentDraftSpec):
    tool_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Trusted tool key to immutable deployed version, resolved at publication; empty for tool-free agents.",
    )
    effective_limits: AITaskLimits
    price: AIPrice
    transport_attempts: int = Field(default=1, ge=1, le=3)
