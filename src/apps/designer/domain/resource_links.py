"""Bounded link and selected-summary contracts; browsers never receive table identities."""

from typing import Literal

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO
from core.i18n import _

type ResourceKind = Literal[
    "users",
    "work_groups",
    "clients",
    "client_releases",
    "forms",
    "form_versions",
    "workflows",
    "workflow_versions",
    "step_versions",
    "request_types",
    "connections",
    "agent_versions",
    "components",
    "component_versions",
    "data_types",
    "data_type_versions",
]


class ResourceReference(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    kind: ResourceKind = Field(description=_("Code-owned resource kind; never a table or URL."))
    ref_id: str = Field(min_length=1, max_length=512, description=_("Opaque resource reference."))


class LocatorQuery(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    locator: str = Field(
        min_length=55,
        max_length=107,
        description=_("Opaque stable locator previously returned by the server."),
    )


class SelectedQuery(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    resources: list[ResourceReference] = Field(
        min_length=1,
        max_length=50,
        description=_("Selected values outside any search page; all must remain eligible."),
    )


class ResourceSummary(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    kind: ResourceKind
    ref_id: str = Field(
        description=_("Fresh version-bearing reference; replace cached mutation refs.")
    )
    label: str = Field(description=_("Safe current display name from the owning resource service."))
    number: int | None = Field(
        default=None, description=_("Exact version number, when applicable.")
    )
    available: bool = Field(
        description=_("Current selection eligibility; does not grant execution authority.")
    )


class ResourceLink(ResourceSummary):
    locator: str = Field(
        description=_("Stable encrypted identity; invalid after signing-key replacement.")
    )
    route_key: ResourceKind = Field(
        description=_("Allowlisted frontend route key; no arbitrary navigation URL.")
    )
