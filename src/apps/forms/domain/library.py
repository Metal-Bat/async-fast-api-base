"""Versioned authored form-library contracts separate from primitive field metadata."""

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from utils.pagination import SearchRequest

LibraryKind = Literal["component", "data_type"]


class LibraryCreate(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class LibraryDTO(LibraryCreate):
    ref_id: str
    created_at: datetime


class TypeUse(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    schema_pointer: str = Field(min_length=1, max_length=1024)
    version_ref: str = Field(min_length=1, max_length=128)


class ComponentUse(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    instance_key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    component_ref: str = Field(min_length=1, max_length=128)
    schema_pointer: str = Field(min_length=1, max_length=1024)
    node_pointer: str = Field(min_length=1, max_length=1024)
    parameters: dict[str, Any] = Field(default_factory=dict, max_length=16)
    message_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict, max_length=32)


class TypeDocument(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: Literal["bpms.data-type/1"] = "bpms.data-type/1"
    data_schema: dict[str, Any]
    uses: list[TypeUse] = Field(default_factory=list, max_length=64)
    help_messages: dict[str, dict[str, str]] = Field(default_factory=dict, max_length=32)
    category: str = Field(default="general", min_length=1, max_length=64)
    sample_input: Any = None


class ComponentDocument(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: Literal["bpms.component/1"] = "bpms.component/1"
    data_schema: dict[str, Any]
    render_schema: dict[str, Any]
    components: list[ComponentUse] = Field(default_factory=list, max_length=64)
    types: list[TypeUse] = Field(default_factory=list, max_length=64)
    parameters_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "additionalProperties": False}
    )
    parameter_targets: dict[str, str] = Field(default_factory=dict, max_length=16)
    messages: dict[str, dict[str, str]] = Field(default_factory=dict, max_length=64)
    overridable_messages: list[str] = Field(default_factory=list, max_length=32)
    supported_actions: list[str] = Field(default_factory=list, max_length=32)
    required_capabilities: list[str] = Field(default_factory=list, max_length=32)
    category: str = Field(default="general", min_length=1, max_length=64)
    help_messages: dict[str, dict[str, str]] = Field(default_factory=dict, max_length=32)
    sample_input: Any = None

    @model_validator(mode="after")
    def distinct_interface_names(self):
        for names in (
            self.overridable_messages,
            self.supported_actions,
            self.required_capabilities,
        ):
            if len(set(names)) != len(names) or any(not name or len(name) > 128 for name in names):
                raise ValueError("Component interface names must be unique bounded strings")
        return self


class LibraryVersionCreate(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    root_ref_id: str
    number: int = Field(ge=1)
    document: dict[str, Any]


class LibraryVersionUpdate(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    document: dict[str, Any]


class LibraryVersionDTO(BaseDTO):
    ref_id: str
    root_ref_id: str
    number: int
    status: Literal["DRAFT", "PUBLISHED", "RETIRED"]
    document: dict[str, Any]
    resolved: dict[str, Any] | None
    dependencies: list[dict[str, Any]]
    checksum: str | None
    published_at: datetime | None
    published_by_ref_id: str | None


class LibraryQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {"code": str, "name": str, "is_active": bool}


class LibraryVersionQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {"number": int, "status": str}
    root_ref_id: str


class LibraryGrantCreate(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    user_ref_id: str | None = None
    work_group_ref_id: str | None = None

    @model_validator(mode="after")
    def exactly_one_target(self):
        if (self.user_ref_id is None) == (self.work_group_ref_id is None):
            raise ValueError("Choose one user or work group")
        return self


class LibraryGrantDTO(BaseDTO):
    ref_id: str
    user_ref_id: str | None
    work_group_ref_id: str | None
    can_use: bool


class ComponentUpgradePreviewRequest(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    replacements: dict[str, str] = Field(min_length=1, max_length=64)


class ComponentUpgradeIssue(BaseDTO):
    pointer: str
    code: str


class ComponentUpgradePreview(BaseDTO):
    compatible: bool
    issues: list[ComponentUpgradeIssue]
    manifest: list[dict[str, Any]]
    documents: dict[str, Any]
