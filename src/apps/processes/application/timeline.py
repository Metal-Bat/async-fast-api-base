"""Authorized process timeline read projection over immutable graph and runtime facts."""

from collections import defaultdict
from typing import Literal
from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.domain.dto import (
    ProcessTimelineDTO,
    ProcessTimelineQueryDTO,
    TimelineAttemptDTO,
    TimelineCandidateDTO,
    TimelineChildDTO,
    TimelineEventDTO,
    TimelineExecutionDTO,
    TimelinePositionDTO,
    TimelineStepDTO,
    TimelineTransitionDTO,
    TimelineWorkItemDTO,
)
from apps.processes.domain.entity import (
    ExecutionTokenEntity,
    ProcessEventEntity,
    ProcessInstanceEntity,
    ProcessTransitionEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.requests.domain.entity import BusinessRequestEntity, FormSubmissionEntity
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity
from apps.work_items.domain.entity import (
    WorkItemCandidateEntity,
    WorkItemEntity,
)
from apps.workflows.domain.entity import (
    WorkflowStepEntity,
    WorkflowTransitionEntity,
    WorkflowVersionEntity,
)
from core.ref_id import create_ref_id
from utils.exceptions import NotFoundException, VersionConflictException
from utils.pagination import Page


class ProcessTimelineService:
    """Build a stable, bounded timeline without exposing form data or object keys."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self, process: ProcessInstanceEntity, query: ProcessTimelineQueryDTO
    ) -> ProcessTimelineDTO:
        steps = list(
            (
                await self.session.exec(
                    select(WorkflowStepEntity)
                    .where(WorkflowStepEntity.workflow_version_id == process.workflow_version_id)
                    .order_by(
                        col(WorkflowStepEntity.display_order), col(WorkflowStepEntity.step_key)
                    )
                )
            ).all()
        )
        executions = list(
            (
                await self.session.exec(
                    select(StepExecutionEntity)
                    .where(StepExecutionEntity.process_instance_id == process.id)
                    .order_by(col(StepExecutionEntity.created_at), col(StepExecutionEntity.id))
                )
            ).all()
        )
        tokens = list(
            (
                await self.session.exec(
                    select(ExecutionTokenEntity)
                    .where(
                        ExecutionTokenEntity.process_instance_id == process.id,
                        col(ExecutionTokenEntity.status).in_(["ACTIVE", "WAITING", "FAILED"]),
                    )
                    .order_by(col(ExecutionTokenEntity.created_at), col(ExecutionTokenEntity.id))
                )
            ).all()
        )
        attempts = await self._attempts(executions)
        work_items, candidates, claimants = await self._work_items(executions)
        submissions = await self._submissions(executions)
        request = await self.session.get(BusinessRequestEntity, process.business_request_id)
        if request is None:
            raise NotFoundException("Process request not found")
        step_by_id = {step.id: step for step in steps}
        executions_by_step: dict[UUID, list[StepExecutionEntity]] = defaultdict(list)
        for execution in executions:
            executions_by_step[execution.workflow_step_id].append(execution)

        timeline_steps = [
            TimelineStepDTO(
                step_key=step.step_key,
                display_order=step.display_order,
                path_status=self._path_status(
                    process, step.id, executions_by_step[step.id], tokens
                ),
                executions=[
                    self._execution_dto(
                        execution,
                        attempts.get(execution.id, []),
                        work_items.get(execution.id),
                        candidates,
                        claimants,
                        submissions.get(execution.id),
                    )
                    for execution in executions_by_step[step.id]
                ],
            )
            for step in steps
        ]
        current_positions = [self._position(token, step_by_id, executions) for token in tokens]
        return ProcessTimelineDTO(
            process_ref_id=create_ref_id(process.id, process.version),
            business_request_ref_id=create_ref_id(request.id, request.version),
            status=process.status,
            coverage_started_at=(
                await self.session.exec(
                    select(func.min(ProcessEventEntity.occurred_at)).where(
                        ProcessEventEntity.process_instance_id == process.id
                    )
                )
            ).one(),
            current_positions=current_positions,
            children=await self._children(process, {process.id}, 0),
            steps=timeline_steps,
            transitions=await self._transitions(process.id),
            events=await self._events(process.id, query),
        )

    async def _children(
        self, parent: ProcessInstanceEntity, seen: set[UUID], depth: int
    ) -> list[TimelineChildDTO]:
        if depth >= 4:
            return []
        rows = list(
            (
                await self.session.exec(
                    select(ProcessInstanceEntity, StepExecutionEntity)
                    .join(
                        StepExecutionEntity,
                        col(StepExecutionEntity.id)
                        == col(ProcessInstanceEntity.parent_step_execution_id),
                    )
                    .where(StepExecutionEntity.process_instance_id == parent.id)
                    .order_by(col(ProcessInstanceEntity.started_at), col(ProcessInstanceEntity.id))
                    .limit(1025)
                )
            ).all()
        )
        if len(rows) > 1024:
            raise VersionConflictException("Subprocess timeline exceeds its bounded page")
        result: list[TimelineChildDTO] = []
        for child, call in rows:
            if child.id in seen:
                continue
            version = await self.session.get(WorkflowVersionEntity, child.workflow_version_id)
            if version is None:
                raise NotFoundException("Child workflow version not found")
            tokens = list(
                (
                    await self.session.exec(
                        select(ExecutionTokenEntity)
                        .where(
                            ExecutionTokenEntity.process_instance_id == child.id,
                            col(ExecutionTokenEntity.status).in_(["ACTIVE", "WAITING", "FAILED"]),
                        )
                        .order_by(
                            col(ExecutionTokenEntity.created_at), col(ExecutionTokenEntity.id)
                        )
                    )
                ).all()
            )
            executions = list(
                (
                    await self.session.exec(
                        select(StepExecutionEntity)
                        .where(StepExecutionEntity.process_instance_id == child.id)
                        .order_by(col(StepExecutionEntity.created_at), col(StepExecutionEntity.id))
                    )
                ).all()
            )
            step_ids = {token.current_step_id for token in tokens if token.current_step_id}
            steps = (
                {
                    step.id: step
                    for step in (
                        await self.session.exec(
                            select(WorkflowStepEntity).where(
                                col(WorkflowStepEntity.id).in_(step_ids)
                            )
                        )
                    ).all()
                }
                if step_ids
                else {}
            )
            result.append(
                TimelineChildDTO(
                    process_ref_id=create_ref_id(child.id, child.version),
                    parent_execution_ref_id=create_ref_id(call.id, call.version),
                    workflow_version_ref_id=create_ref_id(version.id, version.version),
                    status=child.status,
                    current_positions=[
                        self._position(token, steps, executions) for token in tokens
                    ],
                    children=await self._children(child, seen | {child.id}, depth + 1),
                )
            )
        return result

    async def _attempts(
        self, executions: list[StepExecutionEntity]
    ) -> dict[UUID, list[StepExecutionAttemptEntity]]:
        if not executions:
            return {}
        rows = list(
            (
                await self.session.exec(
                    select(StepExecutionAttemptEntity)
                    .where(
                        col(StepExecutionAttemptEntity.step_execution_id).in_(
                            [row.id for row in executions]
                        )
                    )
                    .order_by(
                        col(StepExecutionAttemptEntity.step_execution_id),
                        col(StepExecutionAttemptEntity.number),
                    )
                )
            ).all()
        )
        result: dict[UUID, list[StepExecutionAttemptEntity]] = defaultdict(list)
        for row in rows:
            result[row.step_execution_id].append(row)
        return result

    async def _work_items(
        self, executions: list[StepExecutionEntity]
    ) -> tuple[dict[UUID, WorkItemEntity], dict[UUID, list[TimelineCandidateDTO]], dict[UUID, str]]:
        if not executions:
            return {}, {}, {}
        items = list(
            (
                await self.session.exec(
                    select(WorkItemEntity)
                    .where(
                        col(WorkItemEntity.step_execution_id).in_([row.id for row in executions])
                    )
                    .order_by(col(WorkItemEntity.created_at), col(WorkItemEntity.id))
                )
            ).all()
        )
        if not items:
            return {}, {}, {}
        candidate_rows = list(
            (
                await self.session.exec(
                    select(WorkItemCandidateEntity)
                    .where(col(WorkItemCandidateEntity.work_item_id).in_([row.id for row in items]))
                    .order_by(
                        col(WorkItemCandidateEntity.work_item_id),
                        col(WorkItemCandidateEntity.id),
                    )
                )
            ).all()
        )
        user_ids = {row.user_id for row in candidate_rows if row.user_id} | {
            row.claimed_by_user_id for row in items if row.claimed_by_user_id
        }
        group_ids = {row.work_group_id for row in candidate_rows if row.work_group_id}
        users = (
            {
                row.id: row
                for row in (
                    await self.session.exec(
                        select(UserEntity).where(col(UserEntity.id).in_(user_ids))
                    )
                ).all()
            }
            if user_ids
            else {}
        )
        groups = (
            {
                row.id: row
                for row in (
                    await self.session.exec(
                        select(WorkGroupEntity).where(col(WorkGroupEntity.id).in_(group_ids))
                    )
                ).all()
            }
            if group_ids
            else {}
        )
        candidates: dict[UUID, list[TimelineCandidateDTO]] = defaultdict(list)
        for row in candidate_rows:
            principal = users.get(row.user_id) if row.user_id else groups.get(row.work_group_id)
            if principal is not None:
                candidates[row.work_item_id].append(
                    TimelineCandidateDTO(
                        principal_type="user" if row.user_id else "work_group",
                        principal_ref_id=create_ref_id(principal.id, principal.version),
                        can_claim=row.can_claim,
                    )
                )
        claimants: dict[UUID, str] = {}
        for row in items:
            claimant = users.get(row.claimed_by_user_id) if row.claimed_by_user_id else None
            if claimant is not None:
                claimants[row.id] = create_ref_id(claimant.id, claimant.version)
        return {row.step_execution_id: row for row in items}, candidates, claimants

    async def _submissions(
        self, executions: list[StepExecutionEntity]
    ) -> dict[UUID, FormSubmissionEntity]:
        if not executions:
            return {}
        rows = (
            await self.session.exec(
                select(FormSubmissionEntity).where(
                    col(FormSubmissionEntity.step_execution_id).in_([row.id for row in executions])
                )
            )
        ).all()
        return {row.step_execution_id: row for row in rows if row.step_execution_id is not None}

    def _execution_dto(
        self,
        execution: StepExecutionEntity,
        attempts: list[StepExecutionAttemptEntity],
        item: WorkItemEntity | None,
        candidates: dict[UUID, list[TimelineCandidateDTO]],
        claimants: dict[UUID, str],
        submission: FormSubmissionEntity | None,
    ) -> TimelineExecutionDTO:
        work_item = None
        if item is not None:
            work_item = TimelineWorkItemDTO(
                ref_id=create_ref_id(item.id, item.version),
                status=item.status,
                claimant_ref_id=claimants.get(item.id),
                candidates=candidates.get(item.id, []),
                submission_ref_id=(
                    create_ref_id(submission.id, submission.version) if submission else None
                ),
                outcome_key=item.outcome_key,
                due_at=item.due_at,
            )
        return TimelineExecutionDTO(
            ref_id=create_ref_id(execution.id, execution.version),
            visit_number=execution.visit_number,
            status=execution.status,
            wait_kind=execution.wait_kind,
            attempts=[
                TimelineAttemptDTO(
                    number=row.number,
                    status=row.status,
                    error_code=row.error_code,
                    started_at=row.started_at,
                    ended_at=row.ended_at,
                )
                for row in attempts
            ],
            work_item=work_item,
            form_submission_ref_id=(
                create_ref_id(submission.id, submission.version) if submission else None
            ),
            last_error_code=execution.last_error_code,
            started_at=execution.started_at,
            ended_at=execution.ended_at,
        )

    @staticmethod
    def _path_status(
        process: ProcessInstanceEntity,
        step_id: UUID,
        executions: list[StepExecutionEntity],
        tokens: list[ExecutionTokenEntity],
    ) -> Literal["active", "executed", "skipped", "not_reached"]:
        if any(row.current_step_id == step_id for row in tokens):
            return "active"
        if executions:
            return "executed"
        return (
            "skipped" if process.status in {"COMPLETED", "FAILED", "CANCELLED"} else "not_reached"
        )

    @staticmethod
    def _position(
        token: ExecutionTokenEntity,
        steps: dict[UUID, WorkflowStepEntity],
        executions: list[StepExecutionEntity],
    ) -> TimelinePositionDTO:
        step = steps.get(token.current_step_id) if token.current_step_id else None
        current = next(
            (
                row
                for row in reversed(executions)
                if row.execution_token_id == token.id
                and row.workflow_step_id == token.current_step_id
            ),
            None,
        )
        return TimelinePositionDTO(
            token_ref_id=create_ref_id(token.id, token.version),
            step_key=step.step_key if step else "",
            execution_ref_id=create_ref_id(current.id, current.version) if current else None,
            status=token.status,
            wait_kind=current.wait_kind if current else None,
        )

    async def _transitions(self, process_id: UUID) -> list[TimelineTransitionDTO]:
        rows = (
            await self.session.exec(
                select(ProcessTransitionEntity, WorkflowTransitionEntity)
                .join(
                    WorkflowTransitionEntity,
                    col(WorkflowTransitionEntity.id)
                    == col(ProcessTransitionEntity.workflow_transition_id),
                )
                .where(ProcessTransitionEntity.process_instance_id == process_id)
                .order_by(col(ProcessTransitionEntity.taken_at), col(ProcessTransitionEntity.id))
            )
        ).all()
        step_ids = {
            step_id for _, edge in rows for step_id in (edge.source_step_id, edge.target_step_id)
        }
        step_rows = (
            (
                await self.session.exec(
                    select(WorkflowStepEntity).where(col(WorkflowStepEntity.id).in_(step_ids))
                )
            ).all()
            if step_ids
            else []
        )
        keys = {row.id: row.step_key for row in step_rows}
        return [
            TimelineTransitionDTO(
                source_step_key=keys[edge.source_step_id],
                target_step_key=keys[edge.target_step_id],
                outcome=row.outcome_key,
                taken_at=row.taken_at,
            )
            for row, edge in rows
        ]

    async def _events(
        self, process_id: UUID, query: ProcessTimelineQueryDTO
    ) -> Page[TimelineEventDTO]:
        criteria = ProcessEventEntity.process_instance_id == process_id
        total = (
            await self.session.exec(
                select(func.count()).select_from(ProcessEventEntity).where(criteria)
            )
        ).one()
        rows = list(
            (
                await self.session.exec(
                    select(ProcessEventEntity)
                    .where(criteria)
                    .order_by(col(ProcessEventEntity.sequence))
                    .offset((query.page - 1) * query.size)
                    .limit(query.size)
                )
            ).all()
        )
        execution_ids = {row.step_execution_id for row in rows if row.step_execution_id}
        item_ids = {row.work_item_id for row in rows if row.work_item_id}
        actor_ids = {row.actor_user_id for row in rows if row.actor_user_id}
        execution_versions = await self._versions(StepExecutionEntity, execution_ids)
        item_versions = await self._versions(WorkItemEntity, item_ids)
        actor_versions = await self._versions(UserEntity, actor_ids)
        return Page[TimelineEventDTO](
            items=[
                TimelineEventDTO(
                    sequence=row.sequence,
                    event_type=row.event_type,
                    step_execution_ref_id=self._ref(row.step_execution_id, execution_versions),
                    work_item_ref_id=self._ref(row.work_item_id, item_versions),
                    actor_ref_id=self._ref(row.actor_user_id, actor_versions),
                    public_payload=row.public_payload,
                    trace_id=row.trace_id,
                    request_id=row.request_id,
                    occurred_at=row.occurred_at,
                )
                for row in rows
            ],
            page=query.page,
            size=query.size,
            total=total,
        )

    async def _versions(self, model, ids: set[UUID]) -> dict[UUID, int]:
        if not ids:
            return {}
        rows = (
            await self.session.exec(select(model.id, model.version).where(col(model.id).in_(ids)))
        ).all()
        return dict(rows)

    @staticmethod
    def _ref(entity_id: UUID | None, versions: dict[UUID, int]) -> str | None:
        if entity_id is None or entity_id not in versions:
            return None
        return create_ref_id(entity_id, versions[entity_id])
