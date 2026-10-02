"""Public snake-case AI agent authoring and catalog contracts."""

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, StrictBool

from apps.ai.domain.agent import AIAgentDraftSpec, AIAgentPublishedSpec
from core.base_dto import BaseDTO
from utils.pagination import SearchRequest


class AIAgentCreateDTO(BaseDTO):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=255)
    spec: AIAgentDraftSpec


class AIAgentUpdateDTO(BaseDTO):
    name: str = Field(min_length=1, max_length=255)
    spec: AIAgentDraftSpec


class AIAgentDTO(BaseDTO):
    ref_id: str
    code: str
    number: int
    name: str
    status: Literal["DRAFT", "PUBLISHED", "RETIRED"]
    spec: AIAgentDraftSpec | AIAgentPublishedSpec
    checksum: str | None
    published_at: datetime | None
    created_at: datetime


class AIAgentQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {
        "code": str,
        "name": str,
        "number": int,
        "status": str,
        "created_at": datetime,
    }


class AIProviderMetadataDTO(BaseDTO):
    key: str
    extra: str
    available: bool
    unavailable_reason: str | None
    credential_mode: str
    needs_endpoint: bool
    supports_custom_endpoint: bool
    supports_tools: bool
    supports_structured_output: bool
    strict_spend_supported: bool
    governed_execution: bool


class AIModelMetadataDTO(BaseDTO):
    connection_ref: str
    provider: str
    model_id: str
    source: Literal["configured"]
    can_execute: bool
    supports_structured_output: bool
    supports_tools: bool
    region: str | None
    provider_retention: str


class AIModelSuggestionDTO(BaseDTO):
    connection_ref: str | None
    model_id: str
    source: Literal["library", "configured"]
    can_execute: bool


class AIToolApprovalCommandDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    approved: StrictBool = Field(
        description="True authorizes the exact displayed read-only call once; false denies it and fails this AI attempt.",
        examples=[True],
    )
    command_key: str = Field(
        min_length=1,
        max_length=128,
        description="Client-generated idempotency key for this decision. Reuse only with the identical decision on the same work item.",
        examples=["approve-lookup-42"],
    )


class AIToolApprovalDTO(BaseDTO):
    work_item_ref: str = Field(
        description="Current version-bearing work-item reference; claim it through the normal work-item API before inspecting or deciding the tool call."
    )
    status: Literal["PENDING", "APPROVED", "DENIED", "EXPIRED", "CANCELLED", "CONSUMED"] = Field(
        description="Durable approval state. CONSUMED fences dispatch; it does not itself prove the model completed. DENIED, EXPIRED and CANCELLED cannot resume."
    )
    tool_key: str = Field(
        description="Allowlisted trusted tool selected by the model; never a Python import or arbitrary SQL."
    )
    tool_version: str = Field(
        description="Immutable deployed tool version pinned when the agent was published."
    )
    arguments: dict[str, Any] | None = Field(
        description="Exact validated named tool arguments, available only to the eligible claimant before expiry/consumption. For lookup_saved_report: report_ref is an owned saved report reference and limit is an integer from 1 to 10. Null after payload deletion; contains no message history.",
        examples=[{"report_ref": "opaque-report-reference", "limit": 5}],
    )
    expires_at: datetime = Field(
        description="UTC deadline derived from the logical task elapsed-time budget, including human approval time."
    )
    decided_at: datetime | None = Field(
        description="UTC decision time, or null before a claimant decision."
    )
