"""Bounded authoring workspace, distinct from executable graph DTOs."""

import json
from typing import Annotated, Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from core.base_dto import BaseDTO


class WorkspacePoint(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(default=0, ge=-1000000, le=1000000, allow_inf_nan=False)
    y: float = Field(default=0, ge=-1000000, le=1000000, allow_inf_nan=False)


class WorkspaceViewport(WorkspacePoint):
    zoom: float = Field(default=1, ge=0.1, le=4, allow_inf_nan=False)


class WorkspaceDocument(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: str = Field(default="bpms.workspace/1", pattern=r"^bpms\.workspace/1$")
    graph: dict[str, Any] = Field(
        default_factory=dict,
        description="Incomplete authoring JSON, at most 256 KiB and depth 32. It is never executed; promotion validates GraphSnapshot and all dependencies.",
    )
    positions: dict[str, WorkspacePoint] = Field(
        default_factory=dict,
        max_length=256,
        description="Positions keyed by stable authored step key, never database row IDs.",
    )
    viewport: WorkspaceViewport = Field(default_factory=WorkspaceViewport)
    collapsed: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(
        default_factory=list, max_length=256
    )
    routing: dict[str, list[WorkspacePoint]] = Field(
        default_factory=dict,
        max_length=2048,
        description="Optional edge waypoints keyed by authored connection identity; at most 64 points each.",
    )

    @model_validator(mode="after")
    def bounded_document(self):
        if len(self.model_dump_json().encode()) > 1048576:
            raise ValueError("Workspace exceeds one MiB")
        if len(set(self.collapsed)) != len(self.collapsed):
            raise ValueError("Collapsed keys must be unique")
        return self

    @field_validator("graph")
    @classmethod
    def bounded_graph(cls, value):
        from apps.forms.application.validation import _bounded, _Invalid

        try:
            _bounded(value, "/graph")
        except _Invalid as exc:
            raise ValueError("Invalid bounded workspace graph") from exc
        if len(json.dumps(value, allow_nan=False).encode()) > 262144:
            raise ValueError("Workspace graph is too large")
        return value

    @field_validator("positions", "routing")
    @classmethod
    def bounded_keys(cls, value):
        if any(not key or len(key) > 128 for key in value):
            raise ValueError("Invalid workspace key")
        if any(isinstance(points, list) and len(points) > 64 for points in value.values()):
            raise ValueError("Too many route points")
        return value


class WorkspaceUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    workspace_ref_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description="Current workspace ref; null creates the first workspace only. Stale refs return recoverable 409.",
    )
    document: WorkspaceDocument


class WorkspacePromoteDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    workspace_ref_id: str = Field(min_length=1, max_length=512)


class WorkflowWorkspaceDTO(BaseDTO):
    workflow_version_ref_id: str
    workspace_ref_id: str | None
    document: WorkspaceDocument
    promoted_graph_checksum: str | None = Field(
        default=None,
        description="Checksum of the last explicitly promoted graph; layout-only saves do not change execution pins.",
    )
