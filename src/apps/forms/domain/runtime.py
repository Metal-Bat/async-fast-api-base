"""Versioned ordinary-actor runtime form projections; never authoring DTOs."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO


class RuntimeActionDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: str
    kind: Literal["complete", "reject", "return"]
    outcome_key: str
    title: str
    confirmation: str | None
    required_scopes: list[str]
    require_comment: bool
    validation: Literal["complete", "partial"]


class RuntimeFieldMetadataDTO(BaseDTO):
    scope: str = Field(description="Visible JSON Schema property/items scope.")
    validation_schema: dict[str, Any] = Field(
        description="Bounded compiled schema of this visible field only. No defaults, examples, hidden properties or shared definitions; backend validates the full canonical document."
    )
    writable: bool
    required: bool


class RuntimeFormStateDTO(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "runtime_dialect": "bpms.runtime/1",
                    "resource_kind": "WORK_ITEM",
                    "resource_ref_id": "r2-current-work-item",
                    "form_version_ref_id": "r2-pinned-form-version",
                    "form_version_number": 1,
                    "submission_ref_id": "r2-current-submission",
                    "design_key": "shared",
                    "view_key": "review",
                    "purpose": "edit",
                    "resolved_locale": "en",
                    "direction": "ltr",
                    "data": {"amount": "125.00"},
                    "item_identity": {},
                    "render_schema": {
                        "dialect": "bpms.render/1",
                        "root": {
                            "component": "text",
                            "scope": "/properties/amount",
                            "label": "Amount",
                        },
                    },
                    "readable_scopes": ["/properties/amount"],
                    "writable_scopes": ["/properties/amount"],
                    "required_scopes": ["/properties/amount"],
                    "field_metadata": [
                        {
                            "scope": "/properties/amount",
                            "validation_schema": {"type": "string"},
                            "writable": True,
                            "required": True,
                        }
                    ],
                    "actions": [],
                    "override_provenance": {},
                    "issues": [],
                }
            ]
        },
    )
    runtime_dialect: Literal["bpms.runtime/1"] = "bpms.runtime/1"
    resource_kind: Literal["REQUEST", "WORK_ITEM"]
    resource_ref_id: str = Field(
        description="Current opaque revision-bearing reference for the owning request/work item; replace after every mutation."
    )
    form_version_ref_id: str
    form_version_number: int = Field(ge=1)
    submission_ref_id: str
    design_key: str = Field(
        description="Exact pinned client variant; locale changes cannot change this key."
    )
    render_dialect: Literal["bpms.render/1"] = "bpms.render/1"
    data_dialect: Literal["https://json-schema.org/draft/2020-12/schema"] = (
        "https://json-schema.org/draft/2020-12/schema"
    )
    view_key: str
    purpose: Literal["edit", "summary", "print", "observer", "correction"]
    resolved_locale: str = Field(
        description="Locale selected by the pinned catalog, or negotiated en/fa fallback."
    )
    direction: Literal["ltr", "rtl"]
    data: dict[str, Any] = Field(
        description="Canonical actor-visible values. Hidden values are preserved only on the server."
    )
    item_identity: dict[str, list[str]] = Field(
        description="Stable row keys for visible collection paths only."
    )
    page_settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Pinned display-only settings; optional pages contains at most 32 unique key/title/scopes entries with actor-readable scopes only. No scripts, bindings or runtime values.",
    )
    before_data: dict[str, Any] | None = Field(
        default=None,
        description="Prior submitted data filtered through the same task view, or null when unavailable.",
    )
    before_item_identity: dict[str, list[str]] | None = Field(
        default=None,
        description="Actor-filtered prior row identities; null when unavailable. / هویت مجاز ردیف‌های پیشین؛ در صورت نبودن null.",
    )
    render_schema: dict[str, Any] = Field(
        description="Actor-filtered bounded bpms.render/1 display document. Server-evaluated calculation metadata and client expressions are omitted; writable_scopes is authoritative for editability."
    )
    readable_scopes: list[str] = Field(max_length=256)
    writable_scopes: list[str] = Field(max_length=256)
    required_scopes: list[str] = Field(max_length=256)
    field_metadata: list[RuntimeFieldMetadataDTO] = Field(max_length=256)
    actions: list[RuntimeActionDTO] = Field(default_factory=list, max_length=64)
    override_provenance: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Visible override actor/reason/value/time only; input checksums remain server-only.",
    )
    issues: list[dict[str, str]] = Field(
        default_factory=list,
        max_length=32,
        description="Safe visible pointer/code pairs. Hidden canonical validation failures produce a generic task.validation issue.",
    )
