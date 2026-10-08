"""Versioned form authoring and validation contracts."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from apps.forms.domain.dtos.authoring import FormDocuments, ValidationResult
from apps.forms.domain.interaction import NavigationQuery
from apps.forms.domain.library import ComponentUse
from apps.forms.domain.options import OptionQuery
from core.base_dto import BaseDTO


class OptionPreviewRequest(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "documents": {
                        "data_schema": {
                            "type": "object",
                            "properties": {"priority": {"type": "integer", "enum": [1, 2]}},
                        },
                        "render_schema": {
                            "root": {
                                "component": "choice",
                                "scope": "/properties/priority",
                                "source": {"kind": "schema"},
                            }
                        },
                    },
                    "query": {"node_pointer": "/root", "data": {}, "generation": 1},
                }
            ]
        },
    )
    documents: FormDocuments = Field(
        description="Bounded canonical draft documents; validated before source resolution. The authenticated client selects the variant."
    )
    query: OptionQuery
    locale: Literal["en", "fa"] | None = Field(
        default=None,
        description="Author-only simulated option locale. Null uses Accept-Language; no canonical values or client identity change.",
    )


class NavigationPreviewRequest(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    documents: FormDocuments
    query: NavigationQuery


class ComponentCopyRequest(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    documents: FormDocuments
    instance: ComponentUse


class BehaviorPreviewRequest(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    documents: FormDocuments
    data: dict[str, Any]
    initial: dict[str, Any] = Field(default_factory=dict)
    initialize: bool = False


class BehaviorPreview(BaseDTO):
    data: dict[str, Any]
    cleared: list[str]
    required: list[str]
    validation_timing: dict[str, list[str]] = Field(default_factory=dict)
    pending: list[str] = Field(default_factory=list)
    validation: ValidationResult
