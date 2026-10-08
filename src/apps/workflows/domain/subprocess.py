"""Version-pinned, typed interfaces for reusable workflow calls."""

import json
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from core.base_dto import BaseDTO


class SubprocessPort(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    value_schema: dict[str, Any] = Field(
        description="JSON Schema Draft 2020-12 type expected in the isolated child context."
    )
    required: bool = Field(default=True, description="A call must map this input when true.")
    assignment: Literal["user", "work_group"] | None = Field(
        default=None,
        description="Actor or group assignment reference carried as a string.",
    )


class SubprocessOutput(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    value_schema: dict[str, Any] = Field(
        description="Declared output schema matching the named child step output port."
    )
    source_step: str = Field(description="Child graph step producing this output.")
    source_port: str = Field(description="Output port on source_step.")


class SubprocessInterface(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    inputs: list[SubprocessPort] = Field(
        default_factory=list,
        max_length=64,
        description="Named values copied into the child; parent context is not implicit.",
    )
    outputs: list[SubprocessOutput] = Field(
        default_factory=list,
        max_length=64,
        description="Named values returned from child step output ports.",
    )
    category: str = Field(default="general", min_length=1, max_length=64)
    help_messages: dict[str, str] = Field(default_factory=dict, max_length=2)
    sample_inputs: dict[str, Any] = Field(default_factory=dict, max_length=64)
    required_capabilities: list[str] = Field(default_factory=list, max_length=32)
    outcomes: dict[str, str] = Field(
        min_length=1,
        max_length=16,
        description="Business outcome name to child FINISH step key. The parent also handles failure.",
    )

    @model_validator(mode="after")
    def unique_names(self) -> SubprocessInterface:
        for ports in (self.inputs, self.outputs):
            if len({port.name for port in ports}) != len(ports):
                raise ValueError("Subprocess port names must be unique; duplicate name")
        if any(not key or len(key) > 64 for key in self.outcomes):
            raise ValueError("Subprocess outcomes must have bounded names")
        if any(len(value) > 2048 for value in self.help_messages.values()):
            raise ValueError("Subprocess help text exceeds 2048 characters")
        if len(set(self.required_capabilities)) != len(self.required_capabilities) or any(
            not value or len(value) > 128 for value in self.required_capabilities
        ):
            raise ValueError("Subprocess capabilities must be unique bounded names")
        if len(json.dumps(self.sample_inputs, allow_nan=False).encode()) > 16384:
            raise ValueError("Subprocess sample inputs exceed 16 KiB")
        if "failure" in self.outcomes:
            raise ValueError("Technical failure is a reserved subprocess outcome")
        return self


class SubprocessInputMapping(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    name: str
    source_kind: Literal["REQUEST", "CONTEXT", "CONSTANT", "STEP_OUTPUT"]
    source_schema: dict[str, Any] = Field(
        description="Source JSON Schema; publication checks compatibility with the child input."
    )
    source_path: str | None = Field(default=None, max_length=512)
    source_step: str | None = None
    source_port: str | None = None
    constant_value: Any = None

    @model_validator(mode="after")
    def valid_source(self) -> SubprocessInputMapping:
        if self.source_kind == "STEP_OUTPUT":
            if bool(self.source_path):
                raise ValueError("Step output mapping cannot use a path")
            if not bool(self.source_step) or not bool(self.source_port):
                raise ValueError("Step output source requires step and port")
        elif bool(self.source_step) or bool(self.source_port):
            raise ValueError("Step source is only valid for STEP_OUTPUT")
        if self.source_kind == "CONSTANT" and bool(self.source_path):
            raise ValueError("Constant source cannot have a path")
        if (
            self.source_kind != "CONSTANT"
            and not bool(self.source_path)
            and self.source_kind != "STEP_OUTPUT"
        ):
            raise ValueError("Context source requires a path")
        return self


class SubprocessCall(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    workflow_version_ref: str = Field(
        description="Exact published child workflow version ref_id. Existing pins survive retirement."
    )
    inputs: list[SubprocessInputMapping] = Field(
        default_factory=list,
        max_length=64,
        description="Explicit source mapping for required child inputs and assignment references.",
    )

    @model_validator(mode="after")
    def unique_mappings(self) -> SubprocessCall:
        if len({item.name for item in self.inputs}) != len(self.inputs):
            raise ValueError("Duplicate subprocess input mapping")
        return self
