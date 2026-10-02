"""Conservative task-wide AI usage and reservation arithmetic."""

from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import ConfigDict, Field, model_validator

from apps.ai.domain.contracts import AITaskLimits
from core.base_dto import BaseDTO


class BudgetAmounts(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    requests: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    spend_usd: Decimal = Field(default=Decimal(0), ge=Decimal(0))

    @model_validator(mode="after")
    def valid_total(self) -> BudgetAmounts:
        if self.total_tokens < self.input_tokens + self.output_tokens:
            raise ValueError("Total tokens cannot be less than input plus output")
        return self

    def __add__(self, other: BudgetAmounts) -> BudgetAmounts:
        return BudgetAmounts(
            **{key: getattr(self, key) + getattr(other, key) for key in BudgetAmounts.model_fields}
        )

    def __sub__(self, other: BudgetAmounts) -> BudgetAmounts:
        return BudgetAmounts(
            **{key: getattr(self, key) - getattr(other, key) for key in BudgetAmounts.model_fields}
        )


class BudgetCapacity(BaseDTO):
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    spend_usd: Decimal


@dataclass
class BudgetLedger:
    limits: AITaskLimits
    used: BudgetAmounts = field(default_factory=BudgetAmounts)
    reserved: BudgetAmounts = field(default_factory=BudgetAmounts)
    unknown: bool = False

    def remaining(self) -> BudgetCapacity:
        values = {}
        for key in BudgetAmounts.model_fields:
            values[key] = max(
                0, getattr(self.limits, key) - getattr(self.used, key) - getattr(self.reserved, key)
            )
        # Remaining independent caps need not obey an actual usage record's token sum.
        return BudgetCapacity.model_validate(values)

    def reserve(self, upper: BudgetAmounts) -> None:
        if upper.requests < 1 or upper.spend_usd <= 0 and self.limits.strict_spend:
            raise ValueError("A model dispatch requires a priced request bound")
        for key in BudgetAmounts.model_fields:
            if getattr(upper, key) > getattr(self.remaining(), key):
                raise ValueError("AI task budget exhausted")
        self.reserved += upper

    def settle(self, upper: BudgetAmounts, actual: BudgetAmounts) -> None:
        self.reserved -= upper
        self.used += actual

    def mark_unknown(self, upper: BudgetAmounts) -> None:
        """Keep the hold until a reconciliation proves the call was not billed."""
        if any(
            getattr(upper, key) > getattr(self.reserved, key) for key in BudgetAmounts.model_fields
        ):
            raise ValueError("Unknown usage needs an existing reservation")
        self.unknown = True


class AIBudgetStatus(BaseDTO):
    effective_limits: AITaskLimits
    used: BudgetAmounts
    reserved: BudgetAmounts
    remaining: BudgetCapacity
    currency: str
    price_version: str
    unknown_usage: bool
