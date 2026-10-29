"""Bounded candidate-only samples; no runtime value or provider output API."""

import json
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, model_validator

from apps.workflows.domain.dtos.graph import GraphIssue, GraphSnapshot
from core.base_dto import BaseDTO


class BindingSourceSample(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    ordinal: int = Field(
        ge=0,
        le=1023,
        description="Existing source binding ordinal within the selected input port. Constants cannot be overridden here.",
    )
    value: JsonValue = Field(
        description="Explicit author sample for the already-projected source value. Null, false, zero and empty collections are present values, distinct from an omitted sample."
    )


class BindingPreviewInput(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    graph: GraphSnapshot
    target_step: str = Field(min_length=1, max_length=64)
    target_port: str = Field(min_length=1, max_length=64)
    samples: list[BindingSourceSample] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def bounded_candidate(self) -> BindingPreviewInput:
        if len({item.ordinal for item in self.samples}) != len(self.samples):
            raise ValueError("binding.preview.sample.duplicate")
        try:
            samples = json.dumps(
                [item.model_dump(mode="json") for item in self.samples],
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
            graph = json.dumps(
                self.graph.model_dump(mode="json"), ensure_ascii=False, allow_nan=False
            ).encode()
        except TypeError, ValueError, RecursionError:
            raise ValueError("binding.preview.document.invalid") from None
        if len(samples) > 32768 or len(graph) > 1048576:
            raise ValueError("binding.preview.document.limit")
        return self


class BindingPreviewField(BaseDTO):
    path: str
    source_kind: Literal["REQUEST", "CONTEXT", "CONSTANT", "STEP_OUTPUT"]
    sample_origin: Literal["AUTHOR", "VISIBLE_CONSTANT"]
    value_type: Literal["null", "boolean", "integer", "number", "string", "array", "object"]


class BindingPreviewDTO(BaseDTO):
    workflow_version_ref: str
    candidate_checksum: str | None
    target_step: str
    target_port: str
    sample_state: Literal["VALID", "MISSING", "INVALID"]
    fields: list[BindingPreviewField] = Field(default_factory=list, max_length=64)
    issues: list[GraphIssue] = Field(default_factory=list, max_length=64)
    values_redacted: Literal[True] = True
    provider_called: Literal[False] = False
    tool_called: Literal[False] = False
    handler_called: Literal[False] = False
