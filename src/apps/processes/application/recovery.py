"""Authorized, transactional recovery through existing runtime state machines."""

import hashlib
import json

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.application.events import ProcessEventService
from apps.processes.application.service import ProcessService
from apps.processes.domain.dto import RecoveryCommandDTO, ScheduledActionDTO
from apps.processes.domain.entity import (
    ProcessEventEntity,
    ProcessInstanceEntity,
    ScheduledActionEntity,
    StepExecutionEntity,
)
from apps.users.domain.entity import UserEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, NotFoundException, VersionConflictException
from utils.pagination import Page, PageRequest


class ProcessRecoveryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def scheduled_actions(
        self, ref_id: str, query: PageRequest, actor: UserEntity
    ) -> Page[ScheduledActionDTO]:
        self._authorize(actor)
        process = await ProcessService(self.session).get(ref_id)
        criteria = col(ScheduledActionEntity.step_execution_id).in_(
            select(StepExecutionEntity.id).where(
                StepExecutionEntity.process_instance_id == process.id
            )
        )
        rows = (
            await self.session.exec(
                select(ScheduledActionEntity)
                .where(criteria)
                .order_by(col(ScheduledActionEntity.due_at), col(ScheduledActionEntity.id))
                .offset((query.page - 1) * query.size)
                .limit(query.size)
            )
        ).all()
        total = (
            await self.session.exec(
                select(func.count()).select_from(ScheduledActionEntity).where(criteria)
            )
        ).one()
        return Page[ScheduledActionDTO](
            page=query.page,
            size=query.size,
            total=total,
            items=[
                ScheduledActionDTO(
                    ref_id=create_ref_id(row.id, row.version),
                    status=row.status,
                    kind=row.kind,
                    due_at=row.due_at,
                    attempts=row.attempts,
                    max_attempts=row.max_attempts,
                    last_error_code=row.last_error_code,
                )
                for row in rows
            ],
        )

    @staticmethod
    def _authorize(actor: UserEntity) -> None:
        if not actor.is_superuser or actor.deleted_at is not None:
            raise NotAllowedException("Only superusers may recover processes")

    async def recover(
        self, ref_id: str, data: RecoveryCommandDTO, actor: UserEntity
    ) -> ProcessInstanceEntity:
        self._authorize(actor)
        service = ProcessService(self.session)
        identifier, expected = open_ref_id(ref_id)
        process = await self.session.get(
            ProcessInstanceEntity, identifier, with_for_update=True, populate_existing=True
        )
        if process is None:
            raise NotFoundException("Process not found")
        key = "recovery:" + hashlib.sha256(data.command_key.encode()).hexdigest()
        intent = hashlib.sha256(
            json.dumps(
                {**data.model_dump(exclude={"command_key"}), "actor": str(actor.id)},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        existing = (
            await self.session.exec(
                select(ProcessEventEntity).where(
                    ProcessEventEntity.process_instance_id == process.id,
                    ProcessEventEntity.event_type == "operation.recovered",
                    ProcessEventEntity.command_key == key,
                )
            )
        ).one_or_none()
        if existing is not None:
            if existing.public_payload.get("intent_hash") != intent:
                raise VersionConflictException(
                    "Recovery command key was reused with different intent"
                )
            return process
        if process.version != expected:
            raise VersionConflictException("Process is stale")
        if data.action == "retry_timer":
            await self._retry_timer(process, data)
        else:
            if data.scheduled_action_ref_id is not None:
                raise VersionConflictException("This recovery action does not accept a timer")
            if data.action == "resume" and process.status != "PAUSED":
                raise VersionConflictException("Recovery resume requires a paused process")
            await service.command(ref_id, data.action, key, actor_user_id=actor.id)
        await ProcessEventService(self.session).append(
            process.id,
            "operation.recovered",
            actor_user_id=actor.id,
            command_key=key,
            payload={"action": data.action, "reason": data.reason, "intent_hash": intent},
        )
        return process

    async def _retry_timer(self, process: ProcessInstanceEntity, data: RecoveryCommandDTO) -> None:
        if data.scheduled_action_ref_id is None:
            raise VersionConflictException("Timer recovery requires a scheduled action")
        identifier, expected = open_ref_id(data.scheduled_action_ref_id)
        timer = await self.session.get(
            ScheduledActionEntity, identifier, with_for_update=True, populate_existing=True
        )
        execution = (
            await self.session.get(StepExecutionEntity, timer.step_execution_id)
            if timer is not None
            else None
        )
        if timer is None or execution is None or execution.process_instance_id != process.id:
            raise NotFoundException("Scheduled action not found")
        if timer.version != expected:
            raise VersionConflictException("Scheduled action is stale")
        if timer.status != "FAILED" or execution.status != "WAITING" or process.status != "WAITING":
            raise VersionConflictException(
                "Scheduled action cannot be recovered from its current state"
            )
        timer.status = "PENDING"
        # Keep dispatch identities monotonic so old broker deliveries cannot become current.
        timer.max_attempts = max(timer.max_attempts, timer.attempts) + 1
        timer.lease_owner = None
        timer.lease_until = None
        timer.last_error_code = None
        timer.due_at = get_datetime_utc()
