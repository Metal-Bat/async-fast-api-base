"""Typed option-source metadata; keys travel through a reversible select encoding."""

from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, StrictBool, StrictInt, StrictStr

from apps.forms.domain.localization import MessageReference
from core.base_dto import BaseDTO
from utils.pagination import Page
from utils.select import SelectOption, SelectQuery

Scalar = (
    StrictStr | StrictBool | StrictInt | Annotated[float, Field(strict=True, allow_inf_nan=False)]
)
Name = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")]
Scope = Annotated[str, Field(min_length=1, max_length=1024)]


class SourceBase(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: Literal["bpms.options/1"] = "bpms.options/1"
    dependencies: dict[Name, Scope] = Field(
        default_factory=dict,
        max_length=8,
        description="Named schema-scope bindings. Missing/null parents block loading; changed parents invalidate previous results and selections. Repeated rows bind within the same item.",
    )
    enabled_when: str | None = Field(
        default=None,
        max_length=1024,
        description="Optional typed boolean expression over request data. Controls option availability, never writes or clears data.",
    )
    parent_change: Literal["invalidate"] = "invalidate"
    removed_value: Literal["reject"] = "reject"


class SchemaSource(SourceBase):
    kind: Literal["schema"] = "schema"
    membership: Literal["snapshot"] = "snapshot"


class CustomChoice(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: Scalar
    value: str = Field(min_length=1, max_length=255)
    message: MessageReference | None = None
    matches: dict[Name, Scalar] = Field(default_factory=dict, max_length=8)


class CustomSource(SourceBase):
    kind: Literal["custom"] = "custom"
    membership: Literal["snapshot"] = "snapshot"
    items: list[CustomChoice] = Field(min_length=1, max_length=256)


class DomainSource(SourceBase):
    kind: Literal["domain"] = "domain"
    membership: Literal["current"] = "current"
    selector: Literal["users", "work_groups"]


class RemoteSource(SourceBase):
    kind: Literal["remote"] = "remote"
    membership: Literal["snapshot"] = "snapshot"
    url: str = Field(
        min_length=1,
        max_length=2048,
        description="Exact HTTPS URL approved by FORM_CLIENT_OPTION_URLS. Client GET only; no server fetching, credentials, redirects, embedded query or fragment. Submitted keys must still belong to the pinned schema enum.",
    )
    method: Literal["GET"] = "GET"
    credentials: Literal["omit"] = "omit"
    redirects: Literal["error"] = "error"
    items_pointer: str = Field(default="/result/items", max_length=256)
    key_pointer: str = Field(default="/key", max_length=256)
    value_pointer: str = Field(default="/value", max_length=256)
    search_parameter: Name = "search"
    page_parameter: Name = "page"
    size_parameter: Name = "size"
    selected_parameter: Name = "selected"


OptionSource = Annotated[
    SchemaSource | CustomSource | DomainSource | RemoteSource, Field(discriminator="kind")
]


class OptionQuery(SelectQuery):
    model_config = ConfigDict(extra="forbid")
    node_pointer: str = Field(
        min_length=1,
        max_length=1024,
        description="Node JSON pointer in the selected render document, for example /root/children/1.",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Current unsaved canonical values for dependency bindings. Submission independently rechecks persisted values.",
    )
    row_indices: list[Annotated[int, Field(ge=0, le=255)]] = Field(
        default_factory=list,
        max_length=8,
        description="Outer-to-inner indices for repeated item scopes.",
    )
    selected_keys: list[Annotated[str, Field(max_length=4096)]] = Field(
        default_factory=list,
        max_length=100,
        description="Optional json-scalar/1 encoded keys for selected-value lookup through the same visibility filters.",
    )
    generation: int = Field(
        default=0,
        ge=0,
        le=2147483647,
        description="Caller generation echoed verbatim. Apply results only when generation, dependency fingerprint and source revision still match the active control.",
    )


class OptionResult(Page[SelectOption[str]]):
    dialect: Literal["bpms.options/1"] = "bpms.options/1"
    key_encoding: Literal["json-scalar/1"] = "json-scalar/1"
    state: Literal["READY", "EMPTY", "BLOCKED", "CLIENT_FETCH"]
    generation: int
    locale: str
    source_revision: str
    dependency_fingerprint: str
    dependencies: dict[str, Any]
    items: list[SelectOption[str]]
    page: int
    size: int
    total: int
    remote: RemoteSource | None = None
