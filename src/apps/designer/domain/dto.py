"""Bounded snake-case contracts for workflow-designer support."""

from typing import Any, Literal

from pydantic import ConfigDict, Field, JsonValue

from apps.forms.domain.fields import FieldContract
from apps.step_types.domain.dto import ExecutionMode, PortDTO
from apps.workflows.domain.subprocess import SubprocessInterface
from core.base_dto import BaseDTO
from utils.select import SelectQuery

type SelectorKind = Literal[
    "users",
    "work_groups",
    "forms",
    "form_versions",
    "workflows",
    "workflow_versions",
    "request_types",
    "definition_status",
    "request_status",
    "process_status",
    "outcome",
]


class DesignerQuery(SelectQuery):
    model_config = ConfigDict(extra="forbid")


class EmptyCatalogMetadata(BaseDTO):
    model_config = ConfigDict(extra="forbid")


class StepCatalogMetadata(EmptyCatalogMetadata):
    code: str
    ref_id: str
    number: int
    handler_key: str
    handler_version: str
    execution_mode: ExecutionMode
    ports: list[PortDTO]
    runtime_available: bool


class SubprocessCatalogMetadata(EmptyCatalogMetadata):
    workflow_version_ref: str
    interface: SubprocessInterface
    runtime_available: bool
    call_step_type: Literal["SUBPROCESS"]


class ProcessStatusMetadata(EmptyCatalogMetadata):
    compatible_next_values: list[
        Literal["RUNNING", "WAITING", "PAUSED", "COMPLETED", "FAILED", "CANCELLED"]
    ]


class CatalogItemDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    category: str
    type_schema: dict[str, JsonValue] = Field(default_factory=dict)
    metadata: (
        StepCatalogMetadata
        | SubprocessCatalogMetadata
        | FieldContract
        | ProcessStatusMetadata
        | EmptyCatalogMetadata
    ) = Field(default_factory=EmptyCatalogMetadata)


class CompletionQuery(DesignerQuery):
    workflow_version_ref_id: str
    request_type_ref_id: str
    current_step_key: str = Field(min_length=1, max_length=64)


class CompletionItemDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    path: str
    source: Literal["request", "process", "current_user", "step_output", "client"]
    type_schema: dict[str, Any]
    nullable: bool
    cardinality: Literal["SCALAR", "LIST"]
    source_step: str | None = None
