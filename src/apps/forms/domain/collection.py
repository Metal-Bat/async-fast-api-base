"""Collection edit request and stable identity responses."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO


class CollectionEditRequest(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=2, max_length=1024)
    operation: Literal["add", "remove", "reorder", "duplicate"]
    item_key: str | None = None
    target_index: int | None = Field(default=None, ge=0, le=256)
    value: Any = None


class CollectionIssue(BaseDTO):
    pointer: str
    code: str
    item_keys: list[str] = Field(default_factory=list)


class CollectionState(BaseDTO):
    data: dict[str, Any]
    item_identity: dict[str, list[str]]
    issues: list[CollectionIssue] = Field(default_factory=list)
