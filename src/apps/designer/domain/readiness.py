"""Exact-snapshot authoring repair plans with allowlisted destinations."""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from apps.designer.domain.resource_links import ResourceLink
from core.base_dto import BaseDTO


class DependencyReadinessQuery(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    workflow_version_ref_id: str = Field(
        min_length=1,
        max_length=512,
        description="Exact current workflow version reference; stale plans fail 409.",
    )

    client_release_ref_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Optional exact registered release for renderer compatibility; omitted/null does not check a client.",
    )


class RepairIssue(BaseDTO):
    pointer: str
    code: str
    node_key: str | None
    repair_key: Literal[
        "workflow_versions",
        "form_versions",
        "step_types",
        "connections",
        "agent_versions",
        "work_groups",
        "clients",
    ]


class DependencyPin(BaseDTO):
    pointer: str
    requested_ref_id: str
    resource: ResourceLink
    checksum: str | None = None


class DependencyReadiness(BaseDTO):
    schema_version: Literal[1] = 1
    scope: Literal["author_publication"] = "author_publication"
    workflow_version_ref_id: str
    checked_at: datetime
    ready: bool
    graph_checksum: str | None
    issues: list[RepairIssue]
    pins: list[DependencyPin]
    requester_eligibility: Literal["not_checked"] = "not_checked"
    client_readiness: Literal["not_checked", "ready", "blocked"] = "not_checked"
