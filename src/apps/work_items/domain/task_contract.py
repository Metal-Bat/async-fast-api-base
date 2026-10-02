"""Pinned human-task view and action authoring contract."""

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from core.base_dto import BaseDTO


class LocalizedTaskText(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    en: str = Field(min_length=1, max_length=255)
    fa: str | None = Field(default=None, min_length=1, max_length=255)


class TaskView(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    purpose: Literal["edit", "summary", "print"]
    title: LocalizedTaskText
    scopes: list[str] = Field(max_length=128)


class TaskAction(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    kind: Literal["complete", "reject", "return"]
    outcome_key: str = Field(min_length=1, max_length=64)
    title: LocalizedTaskText
    confirmation: LocalizedTaskText | None = None
    required_scopes: list[str] = Field(default_factory=list, max_length=128)
    require_comment: bool = False
    validation: Literal["complete", "partial"] = "complete"


class HumanTaskContract(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    default_view: str
    correction_entry: bool = False
    inherit_previous: bool = False
    views: list[TaskView] = Field(min_length=1, max_length=12)
    actions: list[TaskAction] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def valid_keys(self) -> HumanTaskContract:
        view_keys = [view.key for view in self.views]
        action_keys = [action.key for action in self.actions]
        if self.default_view not in view_keys or len(set(view_keys)) != len(view_keys):
            raise ValueError("Task views need unique keys and a declared default")
        if len(set(action_keys)) != len(action_keys):
            raise ValueError("Task actions need unique keys")
        if not any(view.purpose == "edit" for view in self.views):
            raise ValueError("A human task needs an edit view")
        return self
