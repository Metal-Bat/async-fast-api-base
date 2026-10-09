"""Snake-case request-type and business-request API contracts."""

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from apps.clients.domain.contracts import ReleaseRange
from core.base_dto import BaseDTO
from utils.pagination import SearchRequest, auto_query_model


class RequestTypeClientTargetDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    client_ref_id: str
    minimum_release: str | None = Field(default=None, max_length=64)
    maximum_release_exclusive: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def valid_range(self) -> RequestTypeClientTargetDTO:
        ReleaseRange(self.minimum_release, self.maximum_release_exclusive)
        return self


class RequestTypeCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=255)
    workflow_ref_id: str
    form_ref_id: str
    is_active: bool = True
    default_priority: int | None = Field(default=None, ge=0, le=9)
    client_targets: list[RequestTypeClientTargetDTO] = Field(
        default_factory=list,
        max_length=32,
        description="Authoritative confidential-client/release restrictions. On PUT, omission preserves existing restrictions; an explicit empty list deliberately removes them.",
    )
    allow_cross_client_resume: bool = False
    extension_contract: str | None = Field(
        default=None, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"
    )


class RequestTypeDTO(RequestTypeCreateDTO):
    ref_id: str
    created_at: datetime


class RequestTypeQuery(SearchRequest):
    __query_fields__ = auto_query_model(
        RequestTypeDTO,
        exclude={"ref_id", "workflow_ref_id", "form_ref_id"},
    ).__query_fields__


class BusinessRequestCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    request_type_ref_id: str
    priority: int | None = Field(default=None, ge=0, le=9)
    data: dict[str, Any] = Field(default_factory=dict)


class BusinessRequestUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    priority: int | None = Field(default=None, ge=0, le=9)
    data: dict[str, Any]


class BusinessRequestSubmitDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    submit_key: str = Field(min_length=1, max_length=128)


class EligibleRequestTypeQuery(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    supported_render_dialects: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Declared renderer capabilities, such as bpms.render/1. Empty means no renderer support and returns an empty page. This hint grants no authorization; draft creation rechecks server eligibility.",
    )


class EligibleRequestTypeDTO(BaseDTO):
    ref_id: str
    code: str
    name: str
    workflow_version_ref_id: str
    form_version_ref_id: str
    render_dialect: str


class BusinessRequestDTO(BaseDTO):
    process_ref_id: str | None = Field(
        default=None,
        description="Real authorized root-process ref for tracking, or null for a draft/no process. Never derive a process ref from another entity reference.",
    )
    ref_id: str
    request_type_ref_id: str
    requester_ref_id: str
    workflow_version_ref_id: str
    form_version_ref_id: str
    status: str
    priority: int
    data: dict[str, Any]
    item_identity: dict[str, list[str]] | None = None
    submitted_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    origin_client: dict[str, Any] | None = None
    design_snapshot: dict[str, Any] | None = Field(
        default=None,
        description="Pinned client variant and interaction revision with locale-resolved presentation text. Reads resolve the exact pinned form catalog using Accept-Language without rewriting audit snapshots or canonical data. localization reports resolved_locale, direction, catalog_revision and per-message locale/source_revision. Option values and outcomes remain canonical. Authorized responses are private, no-store; locale changes never select a different variant.",
    )


class BusinessRequestQuery(SearchRequest):
    scope: Literal["visible", "mine"] = Field(
        default="visible",
        description="Visible uses current read policy; mine additionally requires requester ownership.",
    )
    __query_fields__: ClassVar[dict[str, Any]] = {
        "status": str,
        "priority": int,
        "created_at": datetime,
        "submitted_at": datetime,
        "closed_at": datetime,
    }
