"""Append-only process event writing and public payload policy."""

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.domain.entity import (
    ProcessEventEntity,
    ProcessInstanceEntity,
    StepExecutionEntity,
)
from core.bpms_observability import bpms_telemetry
from core.history import history_context
from utils.exceptions import NotFoundException

_MAX_TEXT_LENGTH = 512
_MAX_PAYLOAD_BYTES = 4096

_COMMON_FIELDS = frozenset({"status", "error_code", "wait_kind", "attempt", "outcome"})
_EVENT_FIELDS: dict[str, frozenset[str]] = {
    "operation.recovered": frozenset({"action", "reason", "intent_hash"}),
    "request.submitted": frozenset({"status", "priority"}),
    "process.started": frozenset({"status"}),
    "subprocess.started": frozenset({"child_process_ref", "workflow_version_ref"}),
    "subprocess.completed": frozenset({"child_process_ref", "outcome"}),
    "subprocess.failed": frozenset({"child_process_ref", "outcome", "error_code"}),
    "process.paused": frozenset({"status"}),
    "process.resumed": frozenset({"status"}),
    "process.cancelled": frozenset({"status"}),
    "process.completed": frozenset({"status"}),
    "process.failed": _COMMON_FIELDS,
    "process.compensated": frozenset({"status"}),
    "step.started": _COMMON_FIELDS,
    "step.waiting": _COMMON_FIELDS,
    "step.completed": _COMMON_FIELDS,
    "step.failed": _COMMON_FIELDS,
    "step.timed_out": _COMMON_FIELDS,
    "step.retry_started": _COMMON_FIELDS,
    "transition.taken": frozenset({"outcome", "source_step", "target_step", "predicate_contract"}),
    "work_item.created": frozenset({"status", "candidate_count", "priority"}),
    "work_item.claimed": frozenset({"action", "status"}),
    "work_item.released": frozenset({"action", "status"}),
    "work_item.started": frozenset({"action", "status"}),
    "work_item.saved": frozenset({"action", "status", "submission_status"}),
    "work_item.completed": frozenset({"action", "outcome", "status"}),
    "work_item.rejected": frozenset({"action", "outcome", "status"}),
    "work_item.returned": frozenset({"action", "outcome", "status"}),
    "work_item.forwarded": frozenset({"action", "status", "candidate_count"}),
    "work_item.cancelled": frozenset({"action", "status"}),
    "work_item.expired": frozenset({"action", "status"}),
    "work_item.commented": frozenset({"action", "status"}),
    "attachment.added": frozenset({"action", "field_path", "position"}),
    "attachment.replaced": frozenset({"action", "field_path", "position"}),
    "attachment.reordered": frozenset({"action", "field_path", "attachment_count"}),
    "attachment.removed": frozenset({"action", "field_path", "position"}),
    "wait.registered": frozenset({"wait_kind", "event_type", "expires_at", "due_at"}),
    "event.received": frozenset({"event_type", "source", "outcome"}),
    "event.expired": frozenset({"event_type", "outcome"}),
    "timer.scheduled": frozenset({"kind", "due_at", "outcome"}),
    "timer.fired": frozenset({"kind", "outcome", "attempt"}),
    "timer.retry": frozenset({"kind", "attempt", "error_code"}),
    "timer.failed": frozenset({"kind", "attempt", "error_code"}),
    "automation.dispatched": frozenset({"operation", "attempt"}),
    "automation.completed": frozenset({"operation", "attempt"}),
    "automation.failed": frozenset({"operation", "attempt", "error_code"}),
    "notification.created": frozenset({"channel", "recipient_count", "attempt"}),
    "split.created": frozenset({"branches", "step"}),
    "join.arrived": frozenset({"step", "arrived", "required"}),
    "join.released": frozenset({"step", "branches"}),
    "compensation.registered": frozenset({"ordinal", "compensation_step"}),
    "compensation.started": frozenset({"ordinal"}),
    "compensation.completed": frozenset({"ordinal"}),
    "compensation.failed": frozenset({"ordinal", "error_code", "manual_intervention"}),
}


def _safe_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str) and len(value) <= _MAX_TEXT_LENGTH:
        return value
    return None


def public_event_payload(event_type: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return the small, event-specific public subset; raw business data is never copied."""
    allowed = _EVENT_FIELDS.get(event_type)
    if allowed is None:
        raise ValueError(f"Unsupported process event type: {event_type}")
    result = {
        key: safe
        for key, value in (payload or {}).items()
        if key in allowed and (safe := _safe_value(value)) is not None
    }
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    return result if len(encoded) <= _MAX_PAYLOAD_BYTES else {"payload_omitted": True}


class ProcessEventService:
    """Allocate ordered process sequences and append immutable audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(
        self,
        process_id: UUID,
        event_type: str,
        *,
        actor_user_id: UUID | None = None,
        step_execution_id: UUID | None = None,
        work_item_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
        command_key: str | None = None,
    ) -> ProcessEventEntity:
        process = await self.session.get(
            ProcessInstanceEntity,
            process_id,
            with_for_update=True,
            populate_existing=True,
        )
        if process is None:
            raise NotFoundException("Process not found")
        safe_payload = public_event_payload(event_type, payload)
        process.event_sequence += 1
        context = history_context.get()
        payload_hash = None
        if command_key is not None:
            payload_hash = hashlib.sha256(
                json.dumps(safe_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        event = ProcessEventEntity(
            process_instance_id=process.id,
            business_request_id=process.business_request_id,
            sequence=process.event_sequence,
            event_type=event_type,
            step_execution_id=step_execution_id,
            work_item_id=work_item_id,
            actor_user_id=actor_user_id,
            public_payload=safe_payload,
            trace_id=context.trace_id if context else None,
            request_id=context.request_id if context else None,
            command_key=command_key,
            command_payload_hash=payload_hash,
        )
        self.session.add(event)
        await self.session.flush()
        execution = None
        if step_execution_id is not None and event_type in {
            "step.completed",
            "step.failed",
            "step.timed_out",
        }:
            execution = await self.session.get(StepExecutionEntity, step_execution_id)
        bpms_telemetry.record_process_event(
            event_type,
            occurred_at=event.occurred_at,
            process_started_at=process.started_at,
            step_started_at=execution.started_at if execution else None,
            wait_kind=execution.wait_kind if execution else None,
        )
        return event
