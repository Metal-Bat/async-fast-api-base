"""Workflow graph authoring contracts."""

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from apps.work_items.domain.task_contract import HumanTaskContract
from apps.workflows.domain.subprocess import SubprocessCall, SubprocessInterface
from core.base_dto import BaseDTO


class GraphFlow(BaseDTO):
    """Optional advanced control-flow policy; absent means legacy single-path behavior."""

    model_config = ConfigDict(extra="forbid")
    split: Literal["ALL"] | None = None
    join: Literal["ALL"] | None = None
    cancelled_branches: Literal["ARRIVE", "FAIL"] = "ARRIVE"
    max_visits: int | None = Field(default=None, ge=1, le=10_000)
    retry_limit: int = Field(default=3, ge=0, le=20)
    compensation_step: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$"
    )
    compensation_only: bool = False


class GraphStep(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    type_code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")
    type_version_ref: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    flow: GraphFlow = Field(default_factory=GraphFlow)
    form_ref: str | None = None
    field_policy: dict[str, list[str]] | None = None
    task_contract: HumanTaskContract | None = None
    subprocess: SubprocessCall | None = Field(
        default=None,
        description="Pinned child call on a SUBPROCESS step. Execution uses the exact published version and isolated mapped inputs.",
    )
    default_priority: int | None = Field(default=None, ge=0, le=9)
    timeout_seconds: int | None = Field(default=None, gt=0, le=2_592_000)
    display_order: int = Field(default=0, ge=0)


class GraphBinding(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    step: str
    target_port: str
    target_schema: dict[str, Any]
    ordinal: int = Field(default=0, ge=0)
    source_kind: Literal["REQUEST", "CONTEXT", "CONSTANT", "STEP_OUTPUT"]
    source_path: str | None = None
    source_step: str | None = None
    source_port: str | None = None
    source_schema: dict[str, Any] | None = None
    constant_value: Any = None


class GraphTarget(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    step: str
    user_ref: str | None = None
    work_group_ref: str | None = None
    condition: str | None = Field(default=None, max_length=1024)
    priority: int = Field(default=0, ge=0, le=9)

    @model_validator(mode="after")
    def validate_target(self) -> GraphTarget:
        if bool(self.user_ref) == bool(self.work_group_ref):
            raise ValueError("Exactly one target is required")
        return self


class GraphTransition(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    outcome: str = Field(min_length=1, max_length=64)
    condition: str | None = Field(
        default=None,
        max_length=1024,
        description="Boolean expression over declared request/process/reachable outputs and saved origin client. Use version_in_range(client.release, literal_minimum, literal_maximum_exclusive) for releases. Null is unconditional; errors stop progression.",
        examples=['client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)'],
    )
    is_default: bool = Field(
        default=False,
        description="Final else for this source/outcome, used only when no non-default matches. At most one; client-aware groups require an unconditional default below all branch priorities.",
    )
    priority: int = Field(
        default=0,
        ge=0,
        description="Descending if/elif order within a source/outcome. Duplicate priorities are invalid. First matching non-default wins outside explicit parallel split policy.",
    )


class GraphSnapshot(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    interface: SubprocessInterface | None = Field(
        default=None,
        description="Reusable published workflow interface; null preserves ordinary workflow behavior.",
    )
    steps: list[GraphStep] = Field(default_factory=list, max_length=256)
    bindings: list[GraphBinding] = Field(default_factory=list, max_length=1024)
    targets: list[GraphTarget] = Field(default_factory=list, max_length=1024)
    transitions: list[GraphTransition] = Field(default_factory=list, max_length=2048)


class GraphIssue(BaseDTO):
    pointer: str
    code: str
    line: int | None = None
    column: int | None = None
    expected_schema: dict[str, Any] | None = None
    actual_schema: dict[str, Any] | None = None


class GraphValidationResult(BaseDTO):
    valid: bool
    issues: list[GraphIssue] = Field(default_factory=list)
    checksum: str | None = None
