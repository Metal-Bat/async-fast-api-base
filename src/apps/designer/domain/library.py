"""Bounded contracts for reusable definition discovery and draft decisions."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO
from utils.select import SelectQuery

LibraryKind = Literal["component", "data_type", "subprocess"]
TemplateKind = Literal["form", "workflow"]


class LibrarySearch(SelectQuery):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=100)
    kind: LibraryKind | None = None
    category: str | None = Field(default=None, min_length=1, max_length=64)
    locale: Literal["en", "fa"] = "en"
    capabilities: list[str] = Field(default_factory=list, max_length=32)


class LibrarySelectQuery(LibrarySearch):
    """Filter one authored resource kind for a bounded key/value picker."""

    kind: LibraryKind


class LibraryCard(BaseDTO):
    kind: LibraryKind
    ref_id: str
    root_ref_id: str
    code: str
    title: str
    number: int
    category: str
    help_text: str | None = None
    sample_input: Any = None
    available_locales: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    status: str


class LibraryDependency(BaseDTO):
    kind: LibraryKind
    ref_id: str
    checksum: str | None = None
    depth: int = Field(ge=1)


class LibraryUsage(BaseDTO):
    kind: Literal["component", "data_type", "form", "workflow"]
    ref_id: str
    root_ref_id: str
    path: str
    direct: bool


class CompareRequest(BaseDTO):
    other_ref_id: str


class VersionComparison(BaseDTO):
    source_ref_id: str
    target_ref_id: str
    changed_paths: list[str]
    removed_capabilities: list[str]
    added_capabilities: list[str]
    removed_locales: list[str]
    added_locales: list[str]
    schema_compatible: bool


class ReplacementGuidance(BaseDTO):
    ref_id: str
    status: str
    deprecated: bool
    replacement_ref_id: str | None = None
    reason: str | None = None


class TemplateCreate(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    kind: TemplateKind
    source_ref_id: str
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=255)
    mode: Literal["COPY", "REFERENCE"]


class TemplateDraft(BaseDTO):
    kind: TemplateKind
    root_ref_id: str
    version_ref_id: str
    provenance: dict[str, Any]


class UpgradeTarget(BaseDTO):
    kind: TemplateKind
    version_ref_id: str
    replacements: dict[str, str] = Field(min_length=1, max_length=64)


class BulkUpgradeRequest(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    targets: list[UpgradeTarget] = Field(min_length=1, max_length=32)


class UpgradeImpact(BaseDTO):
    kind: TemplateKind
    version_ref_id: str
    compatible: bool
    affected_bindings: list[str]
    issues: list[dict[str, str]]
    translation_changes: list[str]
    capability_changes: list[str]


class BulkUpgradeReport(BaseDTO):
    compatible: bool
    impacts: list[UpgradeImpact]


class RuleExplanation(BaseDTO):
    node_pointer: str
    effect: str
    source_scope: str
    operator: str
    description: str


class FormExplanation(BaseDTO):
    version_ref_id: str
    localization_issues: list[dict[str, str]]
    rules: list[RuleExplanation]
