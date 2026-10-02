"""Bounded snake-case contracts for workflow-designer support."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

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


class CatalogItemDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    category: str
    type_schema: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


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
