"""Durable, claimant-authorized approval for one fenced read-only AI tool call."""

from datetime import datetime
from uuid import UUID, uuid5

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.checkpoint_codec import AIToolCheckpointCodec
from apps.ai.application.deferred_decision import AIDeferredResult
from apps.ai.domain.entity import AIToolApprovalEntity
from apps.processes.domain.entity import (
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.requests.domain.entity import BusinessRequestEntity
from apps.tasks.application.outbox import enqueue_task
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.entity import WorkItemCandidateEntity, WorkItemEntity
from core.ref_id import open_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, NotFoundException, VersionConflictException


class AIExecutionDeferred(Exception):
    """Worker disposition: a durable wait or dispatch fence owns this attempt."""

    def __init__(self, disposition: str) -> None:
        self.disposition = disposition
        super().__init__(disposition)


def checkpoint_codec() -> AIToolCheckpointCodec:
    return AIToolCheckpointCodec(
        [key.get_secret_value().encode() for key in settings.INTEGRATION_SECRET_KEYS]
    )


class AIToolApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_attempt(
        self, attempt_id: UUID, *, lock: bool = False
    ) -> AIToolApprovalEntity | None:
        statement = select(AIToolApprovalEntity).where(
            AIToolApprovalEntity.step_execution_attempt_id == attempt_id
        )
        if lock:
            statement = statement.with_for_update()
        return (
            await self.session.exec(statement.execution_options(populate_existing=True))
        ).one_or_none()

    async def stage(
        self, attempt_id: UUID, actor_id: UUID, checkpoint: AIDeferredResult, expires_at: datetime
    ) -> AIToolApprovalEntity:
        execution = await self._active(attempt_id)
        if expires_at <= get_datetime_utc():
            raise VersionConflictException("AI task elapsed-time budget exhausted")
        if await self.for_attempt(attempt_id) is not None:
            raise VersionConflictException("AI approval was already staged")
        process = await self.session.get(ProcessInstanceEntity, execution.process_instance_id)
        request = (
            await self.session.get(BusinessRequestEntity, process.business_request_id)
            if process
            else None
        )
        if request is None:
            raise VersionConflictException("AI approval request is unavailable")
        item = WorkItemEntity(
            step_execution_id=execution.id,
            business_request_id=request.id,
            priority=request.priority,
            due_at=expires_at,
        )
        self.session.add(item)
        await self.session.flush()
        self.session.add(WorkItemCandidateEntity(work_item_id=item.id, user_id=actor_id))
        ciphertext, digest = checkpoint_codec().seal(
            checkpoint, attempt_id=attempt_id, work_item_id=item.id
        )
        row = AIToolApprovalEntity(
            step_execution_attempt_id=attempt_id,
            work_item_id=item.id,
            tool_key=checkpoint.tool_key,
            tool_version=checkpoint.tool_version,
            tool_call_id=checkpoint.tool_call_id,
            payload_ciphertext=ciphertext,
            payload_hash=digest,
            expires_at=expires_at,
        )
        self.session.add(row)
        await WorkItemService(self.session)._record(
            item, None, "CREATE", f"ai-approval:{attempt_id}"
        )
        await self.session.flush()
        from apps.notifications.application.events import stage_notice

        await stage_notice(
            self.session,
            map_id="MAP-12",
            event_id=row.id,
            recipient_id=actor_id,
            target_kind="ai_approval",
            target_id=item.id,
            request_id=request.id,
            process_id=execution.process_instance_id,
        )
        task_id = uuid5(attempt_id, "ai-approval-expiry")
        message = enqueue_task(
            self.session,
            "bpms.expire_ai_approval",
            kwargs={"attempt_id": str(attempt_id)},
            task_id=str(task_id),
            idempotency_key=task_id,
            queue=settings.CELERY_AUTOMATION_QUEUE,
        )
        message.available_at = expires_at
        return row

    async def detail(
        self, item_ref: str, actor: UserEntity
    ) -> tuple[AIToolApprovalEntity, AIDeferredResult | None]:
        item = await WorkItemService(self.session).get(item_ref, actor)
        await self._claimant(item, actor)
        row = (
            await self.session.exec(
                select(AIToolApprovalEntity).where(AIToolApprovalEntity.work_item_id == item.id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundException("AI approval not found")
        checkpoint = (
            self._open(row)
            if row.payload_ciphertext is not None and row.expires_at > get_datetime_utc()
            else None
        )
        return row, checkpoint

    async def decide(
        self, item_ref: str, actor: UserEntity, *, approved: bool, command_key: str
    ) -> AIToolApprovalEntity:
        if not command_key or len(command_key) > 128:
            raise ValueError("A bounded command key is required")
        item_id, version = open_ref_id(item_ref)
        row = (
            await self.session.exec(
                select(AIToolApprovalEntity).where(AIToolApprovalEntity.work_item_id == item_id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundException("AI approval not found")
        await self._active(row.step_execution_attempt_id)
        row = await self.for_attempt(row.step_execution_attempt_id, lock=True)
        if row is None:
            raise NotFoundException("AI approval not found")
        item = await self.session.get(
            WorkItemEntity, item_id, with_for_update=True, populate_existing=True
        )
        if item is None:
            raise NotFoundException("Work item not found")
        await self._claimant(item, actor)
        desired = "APPROVED" if approved else "DENIED"
        work = WorkItemService(self.session)
        payload_hash = f"ai-tool:{row.id}:{desired}"
        if await work._idempotent(item.id, command_key, actor.id, payload_hash):
            return row
        if (
            row.status != "PENDING"
            or item.status not in {"CLAIMED", "IN_PROGRESS"}
            or item.version != version
        ):
            raise VersionConflictException("AI approval is stale or already decided")
        if row.expires_at <= get_datetime_utc():
            raise VersionConflictException("AI approval expired")
        self._open(row)
        now = get_datetime_utc()
        row.status, row.decided_by_user_id, row.decided_at = desired, actor.id, now
        item.status, item.closed_at, item.updated_at = (
            ("COMPLETED" if approved else "REJECTED"),
            now,
            now,
        )
        if not approved:
            row.payload_ciphertext = None
        await work._record(
            item,
            actor,
            "COMPLETE" if approved else "REJECT",
            command_key,
            details={"payload_hash": payload_hash},
        )
        if approved:
            task_id = uuid5(row.step_execution_attempt_id, "ai-tool-resume")
            enqueue_task(
                self.session,
                "bpms.execute_background",
                kwargs={"attempt_id": str(row.step_execution_attempt_id)},
                task_id=str(task_id),
                idempotency_key=task_id,
                queue=settings.CELERY_AUTOMATION_QUEUE,
            )
        else:
            from apps.processes.application.service import ProcessService

            await ProcessService(self.session).fail_background(
                row.step_execution_attempt_id, "ai.tool.denied"
            )
        await self.session.flush()
        return row

    async def consume(self, attempt_id: UUID, actor: UserEntity) -> AIDeferredResult:
        await self._active(attempt_id)
        row = await self.for_attempt(attempt_id, lock=True)
        if row is None or row.status != "APPROVED" or row.expires_at <= get_datetime_utc():
            raise VersionConflictException("AI tool approval is not executable")
        item = await self.session.get(WorkItemEntity, row.work_item_id)
        if item is None or item.status != "COMPLETED" or row.decided_by_user_id != actor.id:
            raise NotAllowedException("AI approval principal changed")
        await self._claimant(item, actor)
        checkpoint = self._open(row)
        row.status, row.consumed_at, row.payload_ciphertext = "CONSUMED", get_datetime_utc(), None
        await self.session.flush()
        return checkpoint

    async def expire(self, attempt_id: UUID) -> bool:
        # Match decision and resume lock order before locking the approval row.
        try:
            await self._active(attempt_id)
        except VersionConflictException:
            return False
        row = await self.for_attempt(attempt_id, lock=True)
        if (
            row is None
            or row.status not in {"PENDING", "APPROVED"}
            or row.expires_at > get_datetime_utc()
        ):
            return False
        await self._close(row, "EXPIRED")
        from apps.processes.application.service import ProcessService

        await ProcessService(self.session).fail_background(attempt_id, "ai.tool.expired")
        return True

    async def cancel_execution(self, execution_id: UUID) -> None:
        rows = (
            await self.session.exec(
                select(AIToolApprovalEntity)
                .join(
                    StepExecutionAttemptEntity,
                    col(AIToolApprovalEntity.step_execution_attempt_id)
                    == col(StepExecutionAttemptEntity.id),
                )
                .where(
                    StepExecutionAttemptEntity.step_execution_id == execution_id,
                    col(AIToolApprovalEntity.status).in_(["PENDING", "APPROVED"]),
                )
                .with_for_update(of=AIToolApprovalEntity)
            )
        ).all()
        for row in rows:
            await self._close(row, "CANCELLED")

    async def _close(self, row: AIToolApprovalEntity, status: str) -> None:
        row.status, row.payload_ciphertext = status, None
        item = await self.session.get(WorkItemEntity, row.work_item_id, with_for_update=True)
        if item is not None and item.status in {"OPEN", "CLAIMED", "IN_PROGRESS"}:
            item.status, item.closed_at, item.updated_at = (
                status,
                get_datetime_utc(),
                get_datetime_utc(),
            )
            await WorkItemService(self.session)._record(
                item,
                None,
                "EXPIRE" if status == "EXPIRED" else "CANCEL",
                f"ai-{status.lower()}:{row.id}",
            )
        await self.session.flush()

    async def _active(self, attempt_id: UUID) -> StepExecutionEntity:
        attempt = await self.session.get(
            StepExecutionAttemptEntity, attempt_id, with_for_update=True, populate_existing=True
        )
        execution = (
            await self.session.get(
                StepExecutionEntity,
                attempt.step_execution_id,
                with_for_update=True,
                populate_existing=True,
            )
            if attempt
            else None
        )
        process = (
            await self.session.get(
                ProcessInstanceEntity,
                execution.process_instance_id,
                with_for_update=True,
                populate_existing=True,
            )
            if execution
            else None
        )
        if (
            attempt is None
            or attempt.status not in {"RUNNING", "WAITING"}
            or execution is None
            or execution.status != "WAITING"
            or process is None
            or process.status != "WAITING"
        ):
            raise VersionConflictException("AI approval execution is no longer waiting")
        return execution

    async def _claimant(self, item: WorkItemEntity, actor: UserEntity) -> None:
        current = await self.session.get(UserEntity, actor.id, populate_existing=True)
        work = WorkItemService(self.session)
        if (
            current is None
            or current.deleted_at is not None
            or item.claimed_by_user_id != actor.id
            or not await work._eligible(item.id, actor.id, require_claim=True)
        ):
            raise NotAllowedException("Only the currently eligible claimant may approve this tool")

    @staticmethod
    def _open(row: AIToolApprovalEntity) -> AIDeferredResult:
        if row.payload_ciphertext is None:
            raise VersionConflictException("AI approval payload is unavailable")
        checkpoint = checkpoint_codec().open(
            row.payload_ciphertext,
            row.payload_hash,
            attempt_id=row.step_execution_attempt_id,
            work_item_id=row.work_item_id,
        )
        if (checkpoint.tool_key, checkpoint.tool_version, checkpoint.tool_call_id) != (
            row.tool_key,
            row.tool_version,
            row.tool_call_id,
        ):
            raise VersionConflictException("AI approval metadata changed")
        return checkpoint
