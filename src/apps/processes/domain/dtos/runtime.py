"""Snake-case process runtime commands and views."""

from datetime import datetime
from typing import Literal

from core.base_dto import BaseDTO


class ProcessPositionDTO(BaseDTO):
    step_key: str
    token_status: str
    execution_status: str | None
    wait_kind: Literal["HUMAN", "EVENT", "TIMER", "BACKGROUND", "SUBPROCESS"] | None


class ProcessDTO(BaseDTO):
    ref_id: str
    business_request_ref_id: str
    workflow_version_ref_id: str
    status: str
    current_positions: list[ProcessPositionDTO]
    last_error_code: str | None
    started_at: datetime
    ended_at: datetime | None


class ScheduledActionDTO(BaseDTO):
    ref_id: str
    status: str
    kind: str
    due_at: datetime
    attempts: int
    max_attempts: int
    last_error_code: str | None
