"""Workflow graph authoring contracts."""

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from utils.pagination import SearchRequest, auto_query_model


class WorkflowCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=255)
    access_mode: Literal["OPEN", "RESTRICTED"] = "RESTRICTED"
    is_active: bool = True


class WorkflowDTO(WorkflowCreateDTO):
    ref_id: str
    created_at: datetime


class WorkflowVersionCreateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    workflow_ref_id: str
    number: int = Field(ge=1)
    default_priority: int = Field(default=0, ge=0, le=9)


class WorkflowVersionUpdateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    default_priority: int = Field(ge=0, le=9)


class WorkflowVersionDTO(BaseDTO):
    template_source: dict[str, Any] | None = None
    ref_id: str
    workflow_ref_id: str
    number: int
    status: str
    default_priority: int
    graph_checksum: str | None
    published_at: datetime | None
    published_by_ref_id: str | None


class WorkflowQuery(SearchRequest):
    __query_fields__ = auto_query_model(WorkflowDTO, exclude={"ref_id"}).__query_fields__


class WorkflowVersionQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {
        "number": int,
        "status": str,
        "default_priority": int,
    }
    workflow_ref_id: str


class WorkflowGrantDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    user_ref_id: str | None = None
    work_group_ref_id: str | None = None
    can_view: bool = True
    can_start: bool = False

    @model_validator(mode="after")
    def validate_target(self) -> WorkflowGrantDTO:
        if bool(self.user_ref_id) == bool(self.work_group_ref_id):
            raise ValueError("Exactly one grant target is required")
        if not (self.can_view or self.can_start):
            raise ValueError("At least one capability is required")
        self.can_view = self.can_view or self.can_start
        return self


class WorkflowGrantViewDTO(WorkflowGrantDTO):
    ref_id: str
    workflow_ref_id: str


class WorkflowGrantQuery(SearchRequest):
    __query_fields__: ClassVar[dict[str, Any]] = {"can_view": bool, "can_start": bool}
