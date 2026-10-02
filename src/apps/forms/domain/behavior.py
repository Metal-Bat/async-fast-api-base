"""Explicit manual calculation override commands."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO


class ManualOverrideRequest(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    scope: str = Field(min_length=2, max_length=1024)
    operation: Literal["set", "reset"]
    value: Any = None
    reason: str | None = Field(default=None, max_length=1024)


class ManualOverrideState(BaseDTO):
    data: dict[str, Any]
    override_provenance: dict[str, dict[str, Any]]
