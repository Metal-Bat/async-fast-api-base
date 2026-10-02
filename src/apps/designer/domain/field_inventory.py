"""Read-only, bounded evidence contracts for exact workflow field snapshots."""

from typing import Literal

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO

Classification = Literal[
    "ALWAYS_REQUIRED",
    "CONDITIONALLY_REQUIRED",
    "OPTIONAL_USED",
    "SYSTEM_SUPPLIED",
    "DERIVED",
    "NO_DETECTED_CONSUMER",
    "UNKNOWN_ANALYSIS",
]


class FieldInventoryQuery(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "workflow_version_ref_id": "<exact-workflow-version-ref>",
                    "start_form_version_ref_id": "<exact-published-form-version-ref>",
                    "locale": "en",
                    "page": 1,
                    "size": 25,
                }
            ]
        },
    )
    workflow_version_ref_id: str = Field(
        description="Exact draft revision or published workflow version reference; stale revisions fail."
    )
    start_form_version_ref_id: str | None = Field(
        default=None,
        description="Exact start form version for this analysis. Omitted means no start form is analyzed; latest is never selected.",
    )
    locale: Literal["en", "fa"] = "en"
    page: int = Field(default=1, ge=1, le=1000)
    size: int = Field(default=25, ge=1, le=100)
    search: str | None = Field(default=None, max_length=128)
    classification: Classification | None = None


class FieldEvidence(BaseDTO):
    reason: str = Field(
        description="Stable technical consumer reason code; see the field inventory guide."
    )
    location: str = Field(
        description="Exact source definition pointer, prefixed by collection point for form documents."
    )
    target: str | None = None
    condition: str | None = None
    explanation: str
    via: list[str] = Field(
        default_factory=list,
        description="Intermediate calculated field identities in a transitive dependency chain.",
    )


class FieldSuggestion(BaseDTO):
    code: str = Field(
        description="Stable review-candidate code, not an automatic removal instruction."
    )
    explanation: str
    caveat: str
    impacted_locations: list[str] = Field(default_factory=list)


class FieldInventoryRow(BaseDTO):
    identity: str = Field(
        description="Form version, collection point and JSON Schema scope; duplicate labels do not merge identities."
    )
    form_version_ref_id: str
    collection_point: str
    component_instance: str | None = None
    collection_scope: str | None = None
    path: str
    label: str
    type: str
    source: str = Field(
        description="Declared origin such as USER_INPUT, DEFAULT, COMPUTATION, HOST_NAVIGATION or EARLIER_TASK_OUTPUT."
    )
    author_description: str | None = None
    business_rationale: str | None = None
    actor_targets: list[str] = Field(default_factory=list)
    first_use: str | None = None
    required: bool
    user_entry: bool = Field(
        default=False,
        description="Whether this collection point permits a user entry; read-only review does not count.",
    )
    classification: Classification = Field(
        description="Conservative requiredness/use category for the analyzed definition set."
    )
    component_scopes: list[str] = Field(default_factory=list)
    occurrences: int = 0
    dependencies: list[FieldEvidence] = Field(
        default_factory=list,
        description="Direct and transitive uses, each with reason, location and localized explanation.",
    )
    suggestions: list[FieldSuggestion] = Field(
        default_factory=list,
        description="Evidence-backed prompts for human review; never proof a field can be deleted.",
    )


class DeclaredPort(BaseDTO):
    scope: str = "workflow"
    step: str
    direction: Literal["INPUT", "OUTPUT"]
    port: str
    type_schema: dict[str, object]
    source_kind: str | None = None
    source: str | None = Field(
        default=None,
        description="User input, process context, constant, or earlier step output; no profile source is inferred from a label.",
    )
    source_path: str | None = None
    location: str
    required: bool | None = None
    nullable: bool | None = None
    cardinality: Literal["SCALAR", "LIST"] | None = None


class DefinitionPin(BaseDTO):
    kind: Literal["component", "data_type", "subprocess"]
    collection_point: str
    ref_id: str
    checksum: str | None = None


class FieldInventorySummary(BaseDTO):
    field_definitions: int = Field(
        description="Field definitions across collection points; not runtime collection row count."
    )
    unique_field_definitions: int = Field(
        description="Distinct form-version/schema-scope pairs across collection points."
    )
    user_entry_occurrences: int
    user_entered: int
    repeated_collection: int
    automatic_sources: int
    conditional_only: int
    review_candidates: int
    possible_user_inputs: int = Field(
        description="Editable collection-point definitions over all analyzed branches; not a universal minimum."
    )


class FieldInventoryResult(BaseDTO):
    workflow_version_ref_id: str | None = None
    graph_checksum: str | None = None
    form_snapshots: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    complete: bool = Field(
        description="False when opaque, inaccessible, missing, dynamic or bounded dependencies prevent an unused claim."
    )
    diagnostics: list[str] = Field(
        default_factory=list,
        description="Bounded coverage diagnostics; review these before acting on suggestions.",
    )
    summary: FieldInventorySummary
    fields: list[FieldInventoryRow]
    declared_ports: list[DeclaredPort] = Field(
        default_factory=list,
        description="Typed step and subprocess interface ports, including unbound declarations.",
    )
    resolved_pins: list[DefinitionPin] = Field(
        default_factory=list,
        description="Accessible exact component, data-type and child workflow versions analyzed.",
    )
    page: int = 1
    size: int = 25
    total: int = 0
