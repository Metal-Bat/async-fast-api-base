from datetime import datetime
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from core.ref_id import create_ref_id
from utils.pagination import SearchRequest, auto_query_model


class ManualTaskDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    task_name: str
    args: list[object] = Field(default_factory=list)
    kwargs: dict[str, object] = Field(default_factory=dict)
    queue: str | None = None


class TaskControlDTO(BaseDTO):
    task_id: str
    status: str


class TaskExecutionDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned execution reference."),
    )
    task_id: str
    task_name: str
    queue: str | None
    status: str
    args: list[object] | None
    kwargs: dict[str, object] | None
    result: object | None
    traceback: str | None
    worker: str | None
    retries: int
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    created_at: datetime
    updated_at: datetime | None

    @model_validator(mode="before")
    @classmethod
    def create_public_reference(cls, value: Any) -> Any:
        if isinstance(value, dict):
            data = value.copy()
            if "refId" not in data and "ref_id" not in data:
                data["ref_id"] = create_ref_id(data.pop("id"), data.pop("version"))
            return data
        return {field: getattr(value, field) for field in cls.model_fields if field != "ref_id"} | {
            "ref_id": create_ref_id(value.id, value.version)
        }


class TaskExecutionQuery(SearchRequest):
    __query_fields__ = auto_query_model(
        TaskExecutionDTO, exclude={"ref_id", "args", "kwargs", "result", "traceback"}
    ).__query_fields__
