"""Durable event subscriptions and scheduled workflow actions."""

import hashlib
from datetime import timedelta
from typing import Any, Literal
from uuid import UUID

import structlog
from sqlmodel import col, or_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.application.events import ProcessEventService
from apps.processes.domain.entity import (
    EventSubscriptionEntity,
    ProcessInstanceEntity,
    ScheduledActionEntity,
    StepExecutionEntity,
)
from apps.step_types.application.registry import EventWaitConfig, TimerConfig
from apps.tasks.application.outbox import enqueue_task
from core.bpms_observability import bpms_telemetry
from core.deps import SessionFactory
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import VersionConflictException

logger = structlog.get_logger(__name__)
type DeliveryStatus = Literal["consumed", "duplicate", "late_ignored", "not_found"]


def correlation_hash(event_type: str, correlation_key: str) -> str:
    """Return a scoped digest so raw correlation material is never persisted."""
    return hashlib.sha256(f"{event_type}\0{correlation_key}".encode()).hexdigest()


class ProcessWaitService:
    """Own wait registration and resolve each waiting execution at most once."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register(
        self,
        execution: StepExecutionEntity,
        kind: str,
        config: dict[str, Any],
        inputs: dict[str, Any],
    ) -> None:
        now = get_datetime_utc()
        event_name: str
        event_payload: dict[str, Any]
        if kind == "EVENT_WAIT":
            contract = EventWaitConfig.model_validate(config)
            correlation_key = inputs.get("correlation_key")
            if not isinstance(correlation_key, str):
                raise ValueError("Event correlation key is required")
            expires_at = (
                now + timedelta(seconds=contract.expires_in_seconds)
                if contract.expires_in_seconds is not None
                else None
            )
            await self._save_subscription(
                EventSubscriptionEntity(
                    step_execution_id=execution.id,
                    event_type=contract.event_type,
                    correlation_hash=correlation_hash(contract.event_type, correlation_key),
                    expires_at=expires_at,
                )
            )
            if expires_at is not None:
                await self._save_action(
                    ScheduledActionEntity(
                        step_execution_id=execution.id,
                        kind="DEADLINE",
                        due_at=expires_at,
                        action_key=f"wait:{execution.id}:deadline",
                        outcome_key="expired",
                    )
                )
            event_name = "wait.registered"
            event_payload = {
                "wait_kind": "EVENT",
                "event_type": contract.event_type,
                "expires_at": expires_at.isoformat() if expires_at else None,
            }
        elif kind == "TIMER":
            contract = TimerConfig.model_validate(config)
            due_at = now + timedelta(seconds=contract.delay_seconds)
            await self._save_action(
                ScheduledActionEntity(
                    step_execution_id=execution.id,
                    kind="DELAY",
                    due_at=due_at,
                    action_key=f"wait:{execution.id}:delay",
                    outcome_key="elapsed",
                )
            )
            event_name = "timer.scheduled"
            event_payload = {
                "wait_kind": "TIMER",
                "due_at": due_at.isoformat(),
                "kind": "DELAY",
                "outcome": "elapsed",
            }
        else:
            raise ValueError("Unsupported wait handler")
        await self.session.flush()
        await ProcessEventService(self.session).append(
            execution.process_instance_id,
            event_name,
            step_execution_id=execution.id,
            payload=event_payload,
        )

    async def _save_subscription(self, proposed: EventSubscriptionEntity) -> None:
        existing = (
            await self.session.exec(
                select(EventSubscriptionEntity)
                .where(
                    EventSubscriptionEntity.step_execution_id == proposed.step_execution_id,
                    EventSubscriptionEntity.event_type == proposed.event_type,
                    EventSubscriptionEntity.correlation_hash == proposed.correlation_hash,
                )
                .with_for_update()
            )
        ).one_or_none()
        if existing is None:
            self.session.add(proposed)
            return
        if existing.status == "CONSUMED":
            raise VersionConflictException("A consumed event subscription cannot be reopened")
        existing.status = "ACTIVE"
        existing.expires_at = proposed.expires_at
        existing.consumed_at = None
        existing.updated_at = get_datetime_utc()

    async def _save_action(self, proposed: ScheduledActionEntity) -> None:
        existing = (
            await self.session.exec(
                select(ScheduledActionEntity)
                .where(ScheduledActionEntity.action_key == proposed.action_key)
                .with_for_update()
            )
        ).one_or_none()
        if existing is None:
            self.session.add(proposed)
            return
        if existing.status == "FIRED":
            raise VersionConflictException("A fired scheduled action cannot be reopened")
        # The process lock fences callbacks; invalidate the old lease and preserve dispatch numbers.
        existing.status = "PENDING"
        existing.due_at = proposed.due_at
        existing.max_attempts = existing.attempts + proposed.max_attempts
        existing.lease_owner = None
        existing.lease_until = None
        existing.last_error_code = None
        existing.updated_at = get_datetime_utc()

    async def deliver_event(
        self,
        event_type: str,
        correlation_key: str,
        delivery_key: str,
        outcome: str,
        payload: dict[str, Any],
        *,
        source: str,
    ) -> DeliveryStatus:
        duplicate = (
            await self.session.exec(
                select(EventSubscriptionEntity.id).where(
                    EventSubscriptionEntity.delivery_key == delivery_key
                )
            )
        ).first()
        if duplicate is not None:
            return "duplicate"
        digest = correlation_hash(event_type, correlation_key)
        candidate = (
            await self.session.exec(
                select(EventSubscriptionEntity)
                .where(
                    EventSubscriptionEntity.event_type == event_type,
                    EventSubscriptionEntity.correlation_hash == digest,
                    EventSubscriptionEntity.status == "ACTIVE",
                )
                .order_by(col(EventSubscriptionEntity.created_at), col(EventSubscriptionEntity.id))
                .limit(1)
            )
        ).one_or_none()
        if candidate is None:
            known = (
                await self.session.exec(
                    select(EventSubscriptionEntity.id)
                    .where(
                        EventSubscriptionEntity.event_type == event_type,
                        EventSubscriptionEntity.correlation_hash == digest,
                    )
                    .limit(1)
                )
            ).first()
            return "late_ignored" if known is not None else "not_found"
        execution = await self.session.get(StepExecutionEntity, candidate.step_execution_id)
        if execution is None:
            return "not_found"
        await self.session.get(
            ProcessInstanceEntity,
            execution.process_instance_id,
            with_for_update=True,
            populate_existing=True,
        )
        subscription = await self.session.get(
            EventSubscriptionEntity,
            candidate.id,
            with_for_update=True,
            populate_existing=True,
        )
        if subscription is None:
            return "not_found"
        if subscription.delivery_key == delivery_key:
            return "duplicate"
        if subscription.status != "ACTIVE":
            return "late_ignored"
        subscription.attempts += 1
        now = get_datetime_utc()
        if subscription.expires_at is not None and subscription.expires_at <= now:
            subscription.status = "EXPIRED"
            subscription.consumed_at = now
            return "late_ignored"

        from apps.processes.application.service import ProcessService

        await ProcessEventService(self.session).append(
            execution.process_instance_id,
            "event.received",
            step_execution_id=execution.id,
            payload={"event_type": event_type, "source": source, "outcome": outcome},
        )
        await ProcessService(self.session).resume_execution(
            execution.process_instance_id,
            execution.id,
            f"event:{delivery_key}",
            outcome,
            {"payload": payload},
        )
        subscription.status = "CONSUMED"
        subscription.consumed_at = now
        subscription.delivery_key = delivery_key
        subscription.delivery_source = source
        subscription.updated_at = now
        await self._cancel_actions(execution.id)
        bpms_telemetry.record_event_wait(subscription.created_at, now, outcome="CONSUMED")
        logger.info(
            "process.event_consumed",
            event_type=event_type,
            subscription_id=str(subscription.id),
            source=source,
        )
        return "consumed"

    async def cancel_execution(self, execution_id: UUID) -> None:
        from apps.ai.application.approval_service import AIToolApprovalService

        await AIToolApprovalService(self.session).cancel_execution(execution_id)
        now = get_datetime_utc()
        await self.session.exec(
            update(EventSubscriptionEntity)
            .where(
                col(EventSubscriptionEntity.step_execution_id) == execution_id,
                col(EventSubscriptionEntity.status) == "ACTIVE",
            )
            .values(status="CANCELLED", updated_at=now)
        )
        await self._cancel_actions(execution_id)

    async def _cancel_actions(self, execution_id: UUID) -> None:
        await self.session.exec(
            update(ScheduledActionEntity)
            .where(
                col(ScheduledActionEntity.step_execution_id) == execution_id,
                col(ScheduledActionEntity.status).in_(["PENDING", "LEASED"]),
            )
            .values(
                status="CANCELLED",
                lease_owner=None,
                lease_until=None,
                updated_at=get_datetime_utc(),
            )
        )


async def claim_due_actions(
    owner_id: UUID, *, batch_size: int = 100, lease_seconds: int = 60
) -> list[UUID]:
    """Lease due or abandoned actions; committed leases survive scheduler crashes."""
    now = get_datetime_utc()
    claimed: list[UUID] = []
    async with SessionFactory() as session, session.begin():
        actions = (
            await session.exec(
                select(ScheduledActionEntity)
                .where(
                    col(ScheduledActionEntity.due_at) <= now,
                    or_(
                        col(ScheduledActionEntity.status) == "PENDING",
                        (
                            (col(ScheduledActionEntity.status) == "LEASED")
                            & (col(ScheduledActionEntity.lease_until) <= now)
                        ),
                    ),
                )
                .order_by(col(ScheduledActionEntity.due_at), col(ScheduledActionEntity.id))
                .with_for_update(skip_locked=True)
                .limit(batch_size)
            )
        ).all()
        for action in actions:
            if action.attempts >= action.max_attempts:
                action.status = "FAILED"
                action.last_error_code = "scheduled_action.retry_exhausted"
                action.lease_owner = None
                action.lease_until = None
                enqueue_task(
                    session,
                    "bpms.fail_scheduled_action",
                    kwargs={"action_id": str(action.id)},
                    queue=settings.CELERY_AUTOMATION_QUEUE,
                    idempotency_key=f"{action.id}:exhausted:{action.attempts}",
                )
                execution = await session.get(StepExecutionEntity, action.step_execution_id)
                if execution is not None:
                    await ProcessEventService(session).append(
                        execution.process_instance_id,
                        "timer.failed",
                        step_execution_id=execution.id,
                        payload={
                            "kind": action.kind,
                            "attempt": action.attempts,
                            "error_code": action.last_error_code,
                        },
                    )
                continue
            action.status = "LEASED"
            action.attempts += 1
            action.lease_owner = owner_id
            action.lease_until = now + timedelta(seconds=lease_seconds)
            action.updated_at = now
            enqueue_task(
                session,
                "bpms.fire_scheduled_action",
                kwargs={"action_id": str(action.id), "owner_id": str(owner_id)},
                queue=settings.CELERY_AUTOMATION_QUEUE,
                idempotency_key=f"{action.id}:{action.attempts}",
            )
            if action.attempts > 1:
                execution = await session.get(StepExecutionEntity, action.step_execution_id)
                if execution is not None:
                    await ProcessEventService(session).append(
                        execution.process_instance_id,
                        "timer.retry",
                        step_execution_id=execution.id,
                        payload={
                            "kind": action.kind,
                            "attempt": action.attempts,
                            "error_code": action.last_error_code,
                        },
                    )
            claimed.append(action.id)
    return claimed


async def fire_claimed_action(action_id: UUID, owner_id: UUID) -> bool:
    """Resolve one leased action through the process runtime transaction."""
    async with SessionFactory() as session, session.begin():
        candidate = await session.get(ScheduledActionEntity, action_id)
        if candidate is None:
            return False
        execution = await session.get(StepExecutionEntity, candidate.step_execution_id)
        if execution is None:
            return False
        await session.get(
            ProcessInstanceEntity,
            execution.process_instance_id,
            with_for_update=True,
            populate_existing=True,
        )
        action = await session.get(
            ScheduledActionEntity, action_id, with_for_update=True, populate_existing=True
        )
        if action is None or action.status != "LEASED" or action.lease_owner != owner_id:
            return False
        now = get_datetime_utc()
        if action.lease_until is None or action.lease_until <= now:
            return False
        from apps.processes.application.service import ProcessService

        try:
            await ProcessEventService(session).append(
                execution.process_instance_id,
                "timer.fired" if action.kind == "DELAY" else "event.expired",
                step_execution_id=execution.id,
                payload={
                    "kind": action.kind,
                    "outcome": action.outcome_key,
                    "attempt": action.attempts,
                    "event_type": "deadline" if action.kind == "DEADLINE" else None,
                },
            )
            await ProcessService(session).resume_execution(
                execution.process_instance_id,
                execution.id,
                f"scheduled:{action.id}",
                action.outcome_key,
                {"payload": {}} if action.kind == "DEADLINE" else {},
            )
        except VersionConflictException:
            action.status = "CANCELLED"
            bpms_telemetry.record_timer(action.due_at, now, kind=action.kind, outcome="LATE")
            logger.info("process.scheduled_action_late", action_id=str(action.id))
        else:
            action.status = "FIRED"
            action.fired_at = now
            bpms_telemetry.record_timer(action.due_at, now, kind=action.kind, outcome="FIRED")
            action.lease_owner = None
            action.lease_until = None
            if action.kind == "DEADLINE":
                await session.exec(
                    update(EventSubscriptionEntity)
                    .where(
                        col(EventSubscriptionEntity.step_execution_id) == execution.id,
                        col(EventSubscriptionEntity.status) == "ACTIVE",
                    )
                    .values(status="EXPIRED", consumed_at=now, updated_at=now)
                )
        action.lease_owner = None
        action.lease_until = None
        action.updated_at = now
        return action.status == "FIRED"


async def fail_scheduled_action(action_id: UUID) -> bool:
    """Propagate exhausted delivery into the exact still-waiting process."""
    async with SessionFactory() as session, session.begin():
        candidate = await session.get(ScheduledActionEntity, action_id)
        if candidate is None:
            return False
        execution = await session.get(StepExecutionEntity, candidate.step_execution_id)
        if execution is None:
            return False
        await session.get(
            ProcessInstanceEntity,
            execution.process_instance_id,
            with_for_update=True,
            populate_existing=True,
        )
        action = await session.get(
            ScheduledActionEntity, action_id, with_for_update=True, populate_existing=True
        )
        if action is None or action.status != "FAILED":
            return False
        from apps.processes.application.service import ProcessService

        return await ProcessService(session).fail_wait_execution(
            execution.process_instance_id,
            execution.id,
            action.last_error_code or "scheduled_action.retry_exhausted",
        )


async def fire_due_actions(owner_id: UUID, *, batch_size: int = 100) -> int:
    claimed = await claim_due_actions(owner_id, batch_size=batch_size)
    fired = 0
    for action_id in claimed:
        fired += int(await fire_claimed_action(action_id, owner_id))
    return fired
