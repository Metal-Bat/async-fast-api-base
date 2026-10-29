"""Bounded authoring projections; none is a model result or tool approval."""

import json
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, model_validator

from apps.ai.domain.contracts import AIChoice
from apps.requests.domain.dto import BusinessRequestSubmitDTO
from core.base_dto import BaseDTO


class AIDecisionPreviewInput(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    sample_inputs: dict[str, JsonValue] | None = Field(
        default=None,
        max_length=64,
        description="Optional author-provided permitted inputs, at most 32 KiB JSON. Never reads runtime snapshots or calls a provider.",
        examples=[
            {
                "ticket": "Example invoice",
                "options": [
                    {
                        "key": "finance",
                        "labels": {"en": "Finance"},
                        "description": "Invoice handling",
                    },
                    {
                        "key": "support",
                        "labels": {"en": "Support"},
                        "description": "Service issues",
                    },
                ],
            }
        ],
    )

    @model_validator(mode="after")
    def bounded_sample(self):
        if len(json.dumps(self.sample_inputs, ensure_ascii=False).encode()) > 32768:
            raise ValueError("Authoring sample exceeds 32 KiB")
        return self


class AIDecisionPreviewDTO(BaseDTO):
    sample_state: Literal["STATIC", "MISSING", "EMPTY", "INVALID", "VALID"]
    options_input_key: str | None
    options: list[AIChoice] = Field(max_length=254)
    issue_codes: list[str] = Field(default_factory=list, max_length=64)
    provider_called: Literal[False] = False


class AIWorkflowContextInput(AIDecisionPreviewInput):
    workflow_version_ref: str = Field(
        min_length=1,
        max_length=128,
        description="Current revision-bearing reference of an active workflow version the author may view. Stale references conflict; published pins are not replaced.",
    )
    step_key: str = Field(
        min_length=1,
        max_length=64,
        description="Existing AI_DECISION step key in that exact saved executable graph.",
        examples=["classify_invoice"],
    )


class AIWorkflowContextDTO(BaseDTO):
    agent_ref: str
    workflow_version_ref: str
    workflow_checksum: str | None
    step_key: str
    input_schema: dict[str, JsonValue] | None = Field(
        description="Declared JSON Schema for the exact AI data binding, projected through its source path. Null means undeclared, not an inferred runtime schema.",
    )
    sample_origin: Literal["AUTHOR", "CONSTANT_BINDING", "NONE"]
    decision: AIDecisionPreviewDTO


class AIReportLookupDTO(BaseDTO):
    report_ref: str
    source_key: str
    definition_version: int
    created_at: datetime
    fields: list[str] = Field(max_length=256)
    classification: Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL"]
    max_rows: int = Field(ge=1, le=10)


class AIReportLookupPreviewInput(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    report_ref: str = Field(
        min_length=1,
        max_length=128,
        description="Current opaque reference of the author's unexpired saved report query, never a file URL or a definition chosen by arbitrary import path.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Reviewed maximum rows; must also fit the registered source and saved report limits.",
        examples=[5],
    )


class AIReportLookupPreviewDTO(BaseDTO):
    agent_ref: str
    source: AIReportLookupDTO
    limit: int = Field(ge=1, le=10)
    tool_key: Literal["lookup_saved_report"] = "lookup_saved_report"
    tool_version: Literal["1"] = "1"
    result_schema: dict[str, JsonValue] = Field(
        description="Bounded projected result shape. Empty property schemas do not claim unregistered scalar types. No rows, saved filters, storage paths or credentials are returned.",
    )
    requires_human_tool_approval: Literal[True] = True
    tool_called: Literal[False] = False


class AIAgentEvaluationInput(BusinessRequestSubmitDTO):
    submit_key: str = Field(
        min_length=1,
        max_length=128,
        description="Normal request submission replay key. Reuse only for the identical saved request payload; uncertain model execution is never retried through a new key.",
        examples=["reviewed-agent-evaluation-1"],
    )
    request_ref: str = Field(
        min_length=1,
        max_length=128,
        description="Exact owned eligible draft request whose pinned published workflow uses this published agent. Inputs remain in the normal saved request; this command cannot inject arbitrary model inputs.",
    )


class AIAgentEvaluationDTO(BaseDTO):
    agent_ref: str
    request_ref: str
    request_status: str
    process_ref: str | None
    evidence_kind: Literal["GOVERNED_REQUEST_SUBMISSION"] = "GOVERNED_REQUEST_SUBMISSION"
