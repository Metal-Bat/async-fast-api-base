"""Serializable catalog metadata; schemas are generated from trusted Python types."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO
from utils.select import SelectQuery

type ExecutionMode = Literal["SYNC", "HUMAN", "BACKGROUND", "WAIT"]
type PortDirection = Literal["INPUT", "OUTPUT"]
type Cardinality = Literal["SCALAR", "LIST"]


class PortDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    port_key: str
    direction: PortDirection
    value_schema: dict[str, Any]
    required: bool
    nullable: bool
    cardinality: Cardinality


class HandlerDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    handler_key: str
    handler_version: str
    execution_mode: ExecutionMode
    config_schema: dict[str, Any]
    ports: list[PortDTO]


class StepTypeVersionDTO(HandlerDTO):
    ref_id: str
    number: int
    status: Literal["DRAFT", "PUBLISHED", "RETIRED"] = "PUBLISHED"
    is_available: bool = True
    category: str | None = None
    name_key: str | None = None
    help_key: str | None = None
    help_text: str | None = None
    outcomes: list[str] = Field(default_factory=list)
    examples: list[dict[str, Any]] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    has_inputs: bool = False
    has_outputs: bool = False


class StepTypeQuery(SelectQuery):
    status: Literal["DRAFT", "PUBLISHED", "RETIRED"] | None = None
