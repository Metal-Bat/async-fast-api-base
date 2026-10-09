"""Reviewed definition restoration is distinct from publication and environment reset."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from apps.workflows.domain.dto import GraphIssue
from core.base_dto import BaseDTO

BindingKey = Annotated[
    str,
    Field(
        pattern=r"^(form|step_type|user|work_group|connection|agent|subprocess):[A-Za-z][A-Za-z0-9_.-]*(?::[0-9]+)?$"
    ),
]


class RestorePreviewInput(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    source_ref_id: str | None = Field(
        default=None,
        max_length=512,
        description="Exact immutable published/retired template version; omit only when the target has recorded provenance.",
    )
    mode: Literal["replace_draft", "successor"] = Field(
        description="replace_draft replaces only the target DRAFT; successor creates a new editable version without publishing."
    )
    workspace_ref_id: str | None = Field(
        default=None,
        max_length=512,
        description="Current independent workspace reference; null is valid only when no saved workspace exists.",
    )
    bindings: dict[BindingKey, Annotated[str, Field(min_length=1, max_length=512)]] = Field(
        default_factory=dict,
        max_length=128,
        description="At most 128 exact dependency replacements. Keys are kind:step_key, or user/work_group:step_key:target_index. Supported kinds: form, step_type, user, work_group, connection, agent, subprocess. Omitted bindings retain the associated installation mapping when source_ref_id is omitted.",
    )


class RestorePlan(BaseDTO):
    template_ref_id: str
    template_checksum: str
    mode: Literal["replace_draft", "successor"]
    dependencies: dict[str, str]
    changed_step_keys: list[str]
    changed_paths: list[str] = Field(
        default_factory=list,
        description="Safe changed top-level definition paths; no embedded config or private values.",
    )
    blockers: list[GraphIssue]
    expires_in_seconds: int = 600
    plan_token: str | None


class RestoreApplyInput(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    command_key: str = Field(
        min_length=1,
        max_length=128,
        description="Client-generated restore intent identity. Reuse with the identical reviewed token to replay; a different token conflicts.",
    )
    plan_token: str = Field(
        min_length=1,
        max_length=131072,
        description="Opaque signed preview token. New application expires after 600 seconds; a committed command can replay after expiry subject to current authorization.",
    )


class RestoreResult(BaseDTO):
    workflow_version_ref_id: str
    workspace_ref_id: str
    replayed: bool = False


class LayoutResetInput(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    workspace_ref_id: str = Field(min_length=1, max_length=512)
