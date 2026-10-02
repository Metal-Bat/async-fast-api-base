"""Pinned AI data, budget and typed decision contracts."""

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, WithJsonSchema, create_model, model_validator

from core.base_dto import BaseDTO
from utils.select import SelectOption


class AIPermittedData(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    allowed_fields: set[str] = Field(min_length=1, max_length=64)
    allowed_classifications: set[Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL"]] = Field(
        min_length=1, max_length=3
    )
    redacted_fields: set[str] = Field(default_factory=set, max_length=64)
    allowed_tools: set[str] = Field(default_factory=set, max_length=32)
    allowed_retrieval_sources: set[str] = Field(default_factory=set, max_length=32)

    def prepare(self, values: dict[str, Any], classifications: Mapping[str, str]) -> dict[str, Any]:
        if self.allowed_fields - values.keys():
            raise ValueError("Required permitted input field is missing")
        result = {}
        for key in sorted(self.allowed_fields):
            classification = classifications.get(key)
            if classification not in self.allowed_classifications:
                raise ValueError("Input classification is not permitted")
            result[key] = "[REDACTED]" if key in self.redacted_fields else values[key]
        return result

    def permits_tool(self, key: str) -> bool:
        return key in self.allowed_tools

    def permits_retrieval(self, key: str) -> bool:
        return key in self.allowed_retrieval_sources


class AITaskLimits(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    requests: int = Field(ge=1, le=1000)
    tool_calls: int = Field(ge=0, le=1000)
    input_tokens: int = Field(ge=1, le=10_000_000)
    output_tokens: int = Field(ge=1, le=10_000_000)
    total_tokens: int = Field(ge=1, le=20_000_000)
    elapsed_seconds: int = Field(ge=1, le=86400)
    spend_usd: Decimal = Field(ge=Decimal(0), max_digits=12, decimal_places=6)
    strict_spend: bool = True

    def require_strict_spend_bound(self, per_call_upper_usd: Decimal | None) -> None:
        if self.strict_spend and (
            per_call_upper_usd is None
            or per_call_upper_usd <= 0
            or per_call_upper_usd > self.spend_usd
        ):
            raise ValueError("Strict spend requires a defensible per-call upper bound")


def effective_limits(user: AITaskLimits, admin: AITaskLimits) -> AITaskLimits:
    """Pin the tighter limit for one logical task across all attempts."""
    return AITaskLimits(
        requests=min(user.requests, admin.requests),
        tool_calls=min(user.tool_calls, admin.tool_calls),
        input_tokens=min(user.input_tokens, admin.input_tokens),
        output_tokens=min(user.output_tokens, admin.output_tokens),
        total_tokens=min(user.total_tokens, admin.total_tokens),
        elapsed_seconds=min(user.elapsed_seconds, admin.elapsed_seconds),
        spend_usd=min(user.spend_usd, admin.spend_usd),
        strict_spend=user.strict_spend or admin.strict_spend,
    )


class AIChoice(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    labels: dict[Literal["en", "fa"], str] = Field(min_length=1, max_length=2)
    description: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def valid_labels(self) -> AIChoice:
        if any(not label.strip() for label in self.labels.values()):
            raise ValueError("Choice labels cannot be empty")
        return self


class AIDecision(BaseDTO):
    choice: str
    confidence: float = Field(ge=0, le=1)
    needs_review: bool


class AIDecisionContract(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1024)
    options: list[AIChoice] = Field(min_length=2, max_length=254)
    review_below: float = Field(default=0.8, ge=0, le=1)

    @model_validator(mode="after")
    def unique_options(self) -> AIDecisionContract:
        if len({item.key for item in self.options}) != len(self.options):
            raise ValueError("Duplicate decision option key")
        return self

    @property
    def schema_hash(self) -> str:
        payload = self.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def output_model(self) -> type[BaseDTO]:
        """Compile a trusted Literal type from validated keys, never user Python."""
        keys = tuple(item.key for item in self.options)
        described = Annotated[
            Literal.__getitem__(keys),  # ty:ignore[invalid-type-form] -- validated dynamic keys
            WithJsonSchema(
                {
                    "anyOf": [
                        {"const": item.key, "type": "string", "description": item.description}
                        for item in self.options
                    ]
                }
            ),
        ]
        return create_model(
            "AIDecisionOutput",
            __base__=BaseDTO,
            choice=(described, Field(description=self.question)),
        )

    def select(self, locale: str) -> list[SelectOption[str]]:
        language = "fa" if locale.lower().startswith("fa") else "en"
        return [
            SelectOption(
                key=item.key, value=item.labels.get(language, item.labels.get("en", item.key))
            )
            for item in self.options
        ]

    def decide(self, choice: str, confidence: float) -> AIDecision:
        if choice not in {item.key for item in self.options}:
            raise ValueError("Unknown decision option key")
        return AIDecision(
            choice=choice, confidence=confidence, needs_review=confidence < self.review_below
        )
