"""Versioned form authoring and validation contracts."""

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from apps.clients.domain.contracts import ClientKind, ReleaseRange
from apps.forms.domain.library import ComponentUse
from apps.forms.domain.localization import (
    FormatSample,
    FormattedValue,
    FormLocalization,
    ResolvedLocalization,
)
from core.base_dto import BaseDTO
from utils.pagination import SearchRequest, auto_query_model

DATA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
RENDER_DIALECT = "bpms.render/1"


class FormDesignVariantDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    priority: int = Field(
        ge=0,
        le=100,
        description="Descending branch order; the first matching variant wins. Shared design is the final fallback.",
    )
    condition: str | None = Field(
        default=None,
        min_length=1,
        max_length=1024,
        description="Optional boolean expression over the declared client namespace, combined with client/range targets. Uses version_in_range(client.release, minimum, maximum_exclusive) for numeric releases; bounds are literal versions or null. Missing releases do not match. Errors fail selection. No request data, scripts or authorization grants. Null preserves legacy targeting.",
        examples=['client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)'],
    )
    client_ref_id: str | None = None
    kind: ClientKind | None = None
    minimum_release: str | None = Field(default=None, max_length=64)
    maximum_release_exclusive: str | None = Field(default=None, max_length=64)
    required_capabilities: list[str] = Field(default_factory=list, max_length=32)
    render_schema: dict[str, Any]
    page_settings: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_target(self) -> FormDesignVariantDTO:
        if self.client_ref_id is None and self.kind is None and self.condition is None:
            raise ValueError("A variant needs a client/kind target or condition")
        ReleaseRange(self.minimum_release, self.maximum_release_exclusive)
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("Renderer capabilities must be unique")
        return self


class FormDocuments(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    data_dialect: str = DATA_DIALECT
    render_dialect: str = RENDER_DIALECT
    data_schema: dict[str, Any]
    behavior_dialect: Literal["bpms.behavior/1"] | None = None
    render_schema: dict[str, Any] = Field(
        description="Bounded bpms.render/1 document; POST /forms/render-schema returns its complete typed JSON Schema including messages, option_messages and bpms.format/1 field formatting. Message roles resolve to localized_text, localized_options and compatibility label/placeholder/accessibility fields in runtime views."
    )
    page_settings: dict[str, Any] = Field(default_factory=dict)
    variants: list[FormDesignVariantDTO] = Field(default_factory=list, max_length=32)
    reuse_instances: list[ComponentUse] | None = Field(
        default=None,
        max_length=100,
        description="Exact authored component version references placed in empty render placeholders. Published versions pin fully resolved data/render snapshots and their transitive manifest.",
    )
    localization: FormLocalization | None = Field(
        default=None,
        description="Optional bpms.messages/1 catalog pinned with this exact version. Null preserves legacy reads and checksums. Draft gaps are warnings; required translations and matching parameters are mandatory at publication.",
    )


class ValidationIssue(BaseDTO):
    pointer: str
    code: str
    line: int | None = Field(
        default=None,
        description="One-based source line for an expression issue; null for document-only issues.",
    )
    column: int | None = Field(
        default=None,
        description="Zero-based source column for an expression issue; null when unavailable.",
    )


class ValidationResult(BaseDTO):
    valid: bool
    evaluated_data: dict[str, Any] | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    checksum: str | None = None
    warnings: list[ValidationIssue] = Field(
        default_factory=list,
        description="Draft translation gaps. Publication promotes required gaps to errors.",
    )
    source_revisions: dict[str, str] = Field(
        default_factory=dict, description="Default message hashes for translation acknowledgement."
    )


class PreviewRequest(FormDocuments):
    data: Any = None
    locale: str | None = Field(
        default=None,
        max_length=64,
        description="Preview locale override; regional tags use the base en/fa language. Omitted uses Accept-Language.",
    )
    format_values: list[FormatSample] = Field(default_factory=list, max_length=32)


class PreviewDTO(ValidationResult):
    render_schema: dict[str, Any] | None = None
    variant_key: str | None = None
    page_settings: dict[str, Any] | None = None
    design_revision: str | None = None
    localization: ResolvedLocalization | None = None
    formatted_values: list[FormattedValue] = Field(default_factory=list)


class FormCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class FormDTO(FormCreateDTO):
    ref_id: str
    created_at: datetime


class FormVersionCreateDTO(FormDocuments):
    form_ref_id: str
    number: int = Field(ge=1)


class FormVersionDTO(FormDocuments):
    template_source: dict[str, Any] | None = None
    ref_id: str
    form_ref_id: str
    number: int
    status: str
    checksum: str | None
    published_at: datetime | None
    published_by_ref_id: str | None


class FormQuery(SearchRequest):
    __query_fields__ = auto_query_model(FormDTO, exclude={"ref_id"}).__query_fields__


class FormVersionQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {"number": int, "status": str}
    form_ref_id: str
