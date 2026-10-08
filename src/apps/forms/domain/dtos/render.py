"""Versioned form authoring and validation contracts."""

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from apps.forms.domain.fields import ComponentKind
from apps.forms.domain.interaction import FieldInteraction, NavigationContract
from apps.forms.domain.localization import (
    FieldFormatting,
    MessageReference,
    OptionMessage,
    TextRole,
)
from apps.forms.domain.options import OptionSource
from core.base_dto import BaseDTO


class RenderOptions(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    placeholder: str | None = Field(default=None, max_length=255)
    rows: int | None = Field(default=None, ge=1, le=30)
    columns: int | None = Field(default=None, ge=1, le=12)
    min_items: int | None = Field(default=None, ge=0, le=256)
    max_items: int | None = Field(default=None, ge=0, le=256)
    multiple: bool | None = None
    read_only: bool | None = None
    allowed_kinds: list[Literal["file", "image"]] | None = None
    allowed_mime_types: list[str] | None = Field(default=None, max_length=32)
    max_item_bytes: int | None = Field(default=None, ge=1, le=1_073_741_824)
    max_total_bytes: int | None = Field(default=None, ge=1, le=4_294_967_296)
    caption_required: bool | None = None
    allow_duplicates: bool | None = None
    preview: bool | None = None
    camera: bool | None = None
    allow_reorder: bool | None = None
    allow_replace: bool | None = None
    allow_remove: bool | None = None

    @model_validator(mode="after")
    def validate_attachment_options(self) -> RenderOptions:
        if self.allowed_mime_types is not None:
            normalized = [value.strip().lower() for value in self.allowed_mime_types]
            if len(set(normalized)) != len(normalized) or any(
                not value
                or "/" not in value
                or value.startswith("/")
                or value.endswith("/")
                or any(char.isspace() for char in value)
                for value in normalized
            ):
                raise ValueError("MIME types must be unique normalized type/subtype values")
            self.allowed_mime_types = normalized
        if (
            self.max_item_bytes is not None
            and self.max_total_bytes is not None
            and self.max_item_bytes > self.max_total_bytes
        ):
            raise ValueError("Per-item bytes cannot exceed total bytes")
        return self


class GridPlacement(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    column: int = Field(default=1, ge=1, le=12)
    span: int = Field(default=12, ge=1, le=12)
    row: int = Field(default=1, ge=1, le=256)


class Accessibility(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)


class RenderRule(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    scope: str
    operator: Literal["eq", "ne", "present"]
    value: Any = None
    effect: Literal["show", "hide", "enable", "disable", "require"]


class Calculation(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    function: Literal["sum", "concat", "count"] | None = None
    scopes: list[str] = Field(default_factory=list, max_length=16)
    expression: str | None = Field(default=None, min_length=1, max_length=1024)
    override_permission: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_source(self) -> Calculation:
        if bool(self.function) == bool(self.expression):
            raise ValueError("Exactly one calculation source is required")
        if self.function and not self.scopes or bool(self.expression) and self.scopes:
            raise ValueError("Registered functions require scopes; expressions do not")
        return self


class RenderNode(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    node_key: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
    )
    component: ComponentKind
    renderer: Literal["default", "compact"] = "default"
    scope: str | None = None
    label: str | None = Field(default=None, max_length=255)
    localization_key: str | None = Field(default=None, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    messages: dict[TextRole, MessageReference] = Field(default_factory=dict, max_length=12)
    option_messages: list[OptionMessage] = Field(default_factory=list, max_length=256)
    formatting: FieldFormatting | None = None
    interaction: FieldInteraction | None = Field(
        default=None,
        description="Typed presentation hints, mandatory submit validation and declared capability fallback. No behavior scripts execute.",
    )
    navigation: NavigationContract | None = Field(
        default=None,
        description="Host-approved bpms.navigation/1 route with typed arguments and atomic writable result mappings. Cancel preserves canonical data.",
    )
    source: OptionSource | None = Field(
        default=None,
        description="bpms.options/1 source; static/remote keys use pinned membership and domain keys use current visibility. Repeated dependencies bind within row_indices. Cannot coexist with selector.",
    )
    selector: Literal["users", "work_groups"] | None = None
    options: RenderOptions = Field(default_factory=RenderOptions)
    grid: GridPlacement | None = None
    accessibility: Accessibility | None = None
    rules: list[RenderRule] = Field(default_factory=list, max_length=16)
    calculation: Calculation | None = None
    outcome: str | None = Field(default=None, min_length=1, max_length=64)
    children: list[RenderNode] = Field(default_factory=list, max_length=100)


class RenderDocument(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: Literal["bpms.render/1"] = "bpms.render/1"
    root: RenderNode
    outcomes: list[str] = Field(default_factory=list, max_length=32)
