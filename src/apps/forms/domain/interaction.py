"""Host-resolved field interactions; no client script or behavior executor."""

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from core.base_dto import BaseDTO


class FieldInteraction(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    input_mode: Literal["text", "email", "tel", "url", "numeric", "decimal"] | None = None
    picker: Literal["inline", "dialog", "bottom_sheet"] = "inline"
    validation_timing: list[Literal["change", "blur", "submit"]] = Field(
        default=["submit"], max_length=3
    )
    required_capabilities: list[str] = Field(default_factory=list, max_length=16)
    fallback_renderer: Literal["default", "compact"] | None = None
    min_width: int | None = Field(default=None, ge=0, le=4096)
    max_width: int | None = Field(default=None, ge=0, le=4096)

    @model_validator(mode="after")
    def consistent(self):
        if "submit" not in self.validation_timing or len(set(self.validation_timing)) != len(
            self.validation_timing
        ):
            raise ValueError("Submit validation is always required and timings must be unique")
        if len(set(self.required_capabilities)) != len(self.required_capabilities) or any(
            not item or len(item) > 128 for item in self.required_capabilities
        ):
            raise ValueError("Capabilities must be unique bounded names")
        if (
            self.min_width is not None
            and self.max_width is not None
            and self.min_width > self.max_width
        ):
            raise ValueError("Minimum width exceeds maximum")
        return self


class NavigationContract(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: Literal["bpms.navigation/1"] = "bpms.navigation/1"
    route: str = Field(
        min_length=1,
        max_length=256,
        description="Exact host-resolved route from FORM_NAVIGATION_ROUTES. No network call, arbitrary module, inline script or credential is allowed.",
    )
    argument_schema: dict[str, Any] = Field(
        description="Bounded object JSON Schema for host-route arguments, using the supported form schema subset. Required arguments must have bindings."
    )
    arguments: dict[str, str] = Field(
        default_factory=dict,
        max_length=16,
        description="Argument name to canonical form schema scope.",
    )
    result_schema: dict[str, Any] = Field(
        description="Bounded object JSON Schema for returned host values. The whole result and every mapped target value must validate before replacement."
    )
    result_mappings: dict[str, str] = Field(
        min_length=1,
        max_length=16,
        description="Writable form schema scope to result schema scope. Every mapping must validate before any data changes.",
    )
    cancel: Literal["preserve"] = "preserve"


class NavigationPlan(BaseDTO):
    dialect: Literal["bpms.navigation/1"] = "bpms.navigation/1"
    route: str
    arguments: dict[str, Any]
    data_revision: str
    result_schema: dict[str, Any]


class NavigationQuery(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    node_pointer: str = Field(min_length=1, max_length=1024)
    data: dict[str, Any]
    result: dict[str, Any] | None = None
    expected_data_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cancelled: bool = False


class NavigationPreview(BaseDTO):
    plan: NavigationPlan
    data: dict[str, Any]
