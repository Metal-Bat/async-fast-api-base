"""Snake-case process runtime commands and views."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from core.base_dto import BaseDTO
from utils.pagination import Page, PageRequest


class ProcessTimelineQueryDTO(PageRequest):
    """Bounded event page included in a process timeline projection."""


class TimelineEventDTO(BaseDTO):
    sequence: int
    event_type: str
    step_execution_ref_id: str | None
    work_item_ref_id: str | None
    actor_ref_id: str | None
    public_payload: dict[str, Any]
    trace_id: str | None
    request_id: str | None
    occurred_at: datetime


class TimelineAttemptDTO(BaseDTO):
    number: int
    status: str
    error_code: str | None
    started_at: datetime
    ended_at: datetime | None


class TimelineCandidateDTO(BaseDTO):
    principal_type: Literal["user", "work_group"]
    principal_ref_id: str
    can_claim: bool


class TimelineWorkItemDTO(BaseDTO):
    ref_id: str
    status: str
    claimant_ref_id: str | None
    candidates: list[TimelineCandidateDTO]
    submission_ref_id: str | None
    outcome_key: str | None
    due_at: datetime | None


class TimelineExecutionDTO(BaseDTO):
    ref_id: str
    visit_number: int
    status: str
    wait_kind: str | None
    attempts: list[TimelineAttemptDTO]
    work_item: TimelineWorkItemDTO | None
    form_submission_ref_id: str | None
    last_error_code: str | None
    started_at: datetime | None
    ended_at: datetime | None


class TimelineStepDTO(BaseDTO):
    step_key: str
    display_order: int
    path_status: Literal["active", "executed", "skipped", "not_reached"]
    executions: list[TimelineExecutionDTO]


class TimelinePositionDTO(BaseDTO):
    token_ref_id: str
    step_key: str
    execution_ref_id: str | None
    status: str
    wait_kind: str | None


class TimelineTransitionDTO(BaseDTO):
    source_step_key: str
    target_step_key: str
    outcome: str
    taken_at: datetime


class TimelineChildDTO(BaseDTO):
    """Safe child-process summary in the request's authorized timeline."""

    process_ref_id: str = Field(
        description="Opaque child process reference for detailed inspection."
    )
    parent_execution_ref_id: str = Field(
        description="Exact parent call visit that started this child."
    )
    workflow_version_ref_id: str = Field(description="Pinned published child workflow version.")
    status: str = Field(description="Current child process status.")
    current_positions: list[TimelinePositionDTO] = Field(
        description="Live child token positions, including human and timer waits."
    )
    children: list[TimelineChildDTO] = Field(
        default_factory=list,
        description="Nested child summaries without copied input or output data.",
    )


class ProcessTimelineDTO(BaseDTO):
    process_ref_id: str
    business_request_ref_id: str
    status: str
    coverage_started_at: datetime | None
    current_positions: list[TimelinePositionDTO]
    children: list[TimelineChildDTO] = Field(
        default_factory=list,
        description="Direct child call history with pinned versions and nested active positions.",
    )
    steps: list[TimelineStepDTO]
    transitions: list[TimelineTransitionDTO]
    events: Page[TimelineEventDTO]
