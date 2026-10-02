"""Snake-case work-item and cartable wire contracts."""

from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from apps.forms.domain.attachment_dto import SubmissionAttachmentDTO
from core.base_dto import BaseDTO

type CartableKind = Literal["available", "claimed", "completed", "watching", "submitted", "unread"]


class CartableQueryDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    cartable: CartableKind
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class WorkItemDTO(BaseDTO):
    ref_id: str
    request_ref_id: str
    step_execution_ref_id: str
    form_version_ref_id: str | None
    submission_ref_id: str | None
    item_identity: dict[str, list[str]] | None = None
    design_snapshot: dict[str, Any] | None = Field(
        default=None,
        description="Pinned client variant and interaction revision with locale-resolved presentation text. Reads resolve the exact pinned form catalog using Accept-Language without rewriting audit snapshots or canonical data. localization reports resolved_locale, direction, catalog_revision and per-message locale/source_revision. Option values and outcomes remain canonical. Authorized responses are private, no-store; locale changes never select a different variant.",
    )
    status: str
    priority: int
    claimant_ref_id: str | None
    outcome_key: str | None
    due_at: datetime | None
    claimed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    read_at: datetime | None = None
    pinned_at: datetime | None = None
    archived_at: datetime | None = None
    watching_at: datetime | None = None


class WorkItemCommandDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    command_key: str = Field(min_length=1, max_length=128)


class WorkItemSaveDTO(WorkItemCommandDTO):
    data: dict[str, Any]


class CorrectionFeedbackInput(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    scope: str = Field(min_length=1, max_length=512)
    item_key: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


class CorrectionFeedbackDTO(CorrectionFeedbackInput):
    key: str
    actor_ref_id: str
    status: Literal["OPEN", "RESOLVED"]
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by_ref_id: str | None = None


class WorkItemCompleteDTO(WorkItemSaveDTO):
    outcome_key: str = Field(min_length=1, max_length=64)
    comment: str | None = Field(default=None, max_length=4000)
    feedback: list[CorrectionFeedbackInput] = Field(default_factory=list, max_length=64)


class TaskActionViewDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: str
    kind: Literal["complete", "reject", "return"]
    outcome_key: str
    title: str
    confirmation: str | None
    required_scopes: list[str]
    require_comment: bool
    validation: Literal["complete", "partial"]


class WorkItemViewDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    work_item_ref_id: str = Field(
        description="Current revision-bearing ref for autosave and actions."
    )
    submission_ref_id: str = Field(description="Pinned draft/submitted form revision ref.")
    view_key: str = Field(description="Named task view selected from the pinned workflow step.")
    purpose: Literal["edit", "summary", "print"]
    title: str = Field(description="Localized plain-text task-view title.")
    data: dict[str, Any] = Field(
        description="Current canonical data filtered by the task read policy and named view."
    )
    item_identity: dict[str, list[str]] | None = Field(
        description="Stable row keys only for readable collection paths."
    )
    before_data: dict[str, Any] | None = Field(
        description="Prior submitted canonical data through the same read filter, or null."
    )
    render_schema: dict[str, Any] = Field(
        description="Pinned client variant's bpms.render/1 document with unreadable nodes removed and messages localized."
    )
    actions: list[TaskActionViewDTO] = Field(
        description="Available declared actions for the current claimant; empty for observers or closed work."
    )
    feedback: list[CorrectionFeedbackDTO] = Field(
        description="Visible feedback keyed by stable field scope and optional collection item key."
    )
    autosave_conflict: Literal["VERSION_CONFLICT"] = "VERSION_CONFLICT"
    unsaved_navigation: Literal["warn_before_leave"] = "warn_before_leave"


class WorkItemCommentDTO(WorkItemCommandDTO):
    comment: str = Field(min_length=1, max_length=4000)


class WorkItemStateDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    value: bool = True


class WorkItemForwardDTO(WorkItemCommandDTO):
    user_ref_ids: list[str] = Field(default_factory=list, max_length=100)
    work_group_ref_ids: list[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def require_candidates(self) -> WorkItemForwardDTO:
        if not self.user_ref_ids and not self.work_group_ref_ids:
            raise ValueError("At least one forwarding candidate is required")
        if len(set(self.user_ref_ids)) != len(self.user_ref_ids) or len(
            set(self.work_group_ref_ids)
        ) != len(self.work_group_ref_ids):
            raise ValueError("Forwarding candidates must be unique")
        return self


class WorkItemAttachmentMutationDTO(BaseDTO):
    work_item_ref_id: str
    attachment: SubmissionAttachmentDTO
