"""Pinned subprocess creation and one-time parent continuation."""

from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.processes.application.events import ProcessEventService
from apps.processes.domain.entity import (
    ExecutionTokenEntity,
    ProcessInstanceEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.requests.domain.entity import BusinessRequestEntity, FormSubmissionEntity
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.workflows.domain.entity import WorkflowStepEntity, WorkflowVersionEntity
from apps.workflows.domain.subprocess import SubprocessCall, SubprocessInterface
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException


class SubprocessService:
    def __init__(self, session: AsyncSession, engine) -> None:
        self.session = session
        self.engine = engine

    async def _start(
        self,
        parent: ProcessInstanceEntity,
        parent_token: ExecutionTokenEntity,
        execution: StepExecutionEntity,
        step: WorkflowStepEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> ProcessInstanceEntity:
        existing = (
            await self.session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.parent_step_execution_id == execution.id
                )
            )
        ).one_or_none()
        if existing is not None:
            return existing
        if step.subprocess_call is None:
            raise VersionConflictException("Published subprocess call is missing")
        call = SubprocessCall.model_validate(step.subprocess_call)
        child_id, pinned_revision = open_ref_id(call.workflow_version_ref)
        version = await self.session.get(WorkflowVersionEntity, child_id)
        if (
            version is None
            or version.version != pinned_revision
            or version.status not in {"PUBLISHED", "RETIRED"}
            or version.subprocess_interface is None
        ):
            raise VersionConflictException("Pinned subprocess version is unavailable")
        interface = SubprocessInterface.model_validate(version.subprocess_interface)
        context = await self._inputs(call, interface, parent, parent_token, request, submission)
        start = (
            await self.session.exec(
                select(WorkflowStepEntity)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.id) == col(WorkflowStepEntity.step_type_version_id),
                )
                .join(
                    StepTypeEntity,
                    col(StepTypeEntity.id) == col(StepTypeVersionEntity.step_type_id),
                )
                .where(
                    WorkflowStepEntity.workflow_version_id == version.id,
                    StepTypeEntity.code == "START",
                )
            )
        ).one_or_none()
        if start is None:
            raise VersionConflictException("Pinned subprocess has no start step")
        child = ProcessInstanceEntity(
            business_request_id=request.id,
            workflow_version_id=version.id,
            parent_step_execution_id=execution.id,
            input_context=context,
        )
        self.session.add(child)
        await self.session.flush()
        token = ExecutionTokenEntity(process_instance_id=child.id, current_step_id=start.id)
        self.session.add(token)
        await self.session.flush()
        events = ProcessEventService(self.session)
        await events.append(
            parent.id,
            "subprocess.started",
            step_execution_id=execution.id,
            payload={
                "child_process_ref": create_ref_id(child.id, child.version),
                "workflow_version_ref": call.workflow_version_ref,
            },
        )
        await events.append(child.id, "process.started", payload={"status": child.status})
        isolated = submission.model_copy(update={"data": context})
        await self.engine._run(child, token, request, isolated, f"subprocess:{execution.id}")
        return child

    async def _inputs(
        self,
        call: SubprocessCall,
        interface: SubprocessInterface,
        parent: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> dict[str, Any]:
        mappings = {row.name: row for row in call.inputs}
        context: dict[str, Any] = {}
        for port in interface.inputs:
            mapping = mappings.get(port.name)
            if mapping is None:
                if port.required:
                    raise VersionConflictException("Required subprocess input is unmapped")
                continue
            if mapping.source_kind == "CONSTANT":
                value = mapping.constant_value
            elif mapping.source_kind == "REQUEST":
                value = self.engine._pointer(submission.data, mapping.source_path or "")
            elif mapping.source_kind == "CONTEXT":
                value = self.engine._pointer(
                    {
                        "process": {"status": parent.status},
                        "request": {"priority": request.priority},
                    },
                    mapping.source_path or "",
                )
            else:
                source = (
                    await self.session.exec(
                        select(WorkflowStepEntity).where(
                            WorkflowStepEntity.workflow_version_id == parent.workflow_version_id,
                            WorkflowStepEntity.step_key == mapping.source_step,
                        )
                    )
                ).one_or_none()
                prior = (
                    (
                        await self.session.exec(
                            select(StepExecutionEntity)
                            .where(
                                StepExecutionEntity.execution_token_id == token.id,
                                StepExecutionEntity.workflow_step_id == source.id,
                                StepExecutionEntity.status == "COMPLETED",
                            )
                            .order_by(col(StepExecutionEntity.visit_number).desc())
                            .limit(1)
                        )
                    ).one_or_none()
                    if source is not None
                    else None
                )
                if prior is None or prior.output_snapshot is None:
                    raise VersionConflictException("Subprocess source output is unavailable")
                value = prior.output_snapshot[mapping.source_port or ""]
            if not Draft202012Validator(port.value_schema).is_valid(value):
                raise VersionConflictException("Subprocess input does not match its pinned schema")
            context[port.name] = value
        return context

    async def settle(self, child_id: UUID) -> str:
        child = await self.session.get(ProcessInstanceEntity, child_id)
        if child is None or child.parent_step_execution_id is None:
            raise NotFoundException("Subprocess not found")
        parent_id = (
            await self.session.exec(
                select(StepExecutionEntity.process_instance_id).where(
                    StepExecutionEntity.id == child.parent_step_execution_id
                )
            )
        ).one_or_none()
        if parent_id is None:
            raise NotFoundException("Parent call not found")
        parent = await self.session.get(
            ProcessInstanceEntity,
            parent_id,
            with_for_update=True,
            populate_existing=True,
        )
        if parent is None:
            raise NotFoundException("Parent process not found")
        execution = await self.session.get(
            StepExecutionEntity,
            child.parent_step_execution_id,
            with_for_update=True,
            populate_existing=True,
        )
        if (
            execution is None
            or execution.status != "WAITING"
            or execution.wait_kind != "SUBPROCESS"
        ):
            return "duplicate"
        if parent.status in {
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "COMPENSATED",
            "COMPENSATION_FAILED",
        }:
            return "late_ignored"
        child = await self.session.get(
            ProcessInstanceEntity, child_id, with_for_update=True, populate_existing=True
        )
        if child is None or child.status not in {"COMPLETED", "FAILED"}:
            return "pending"
        step = await self.session.get(WorkflowStepEntity, execution.workflow_step_id)
        version = await self.session.get(WorkflowVersionEntity, child.workflow_version_id)
        token = await self.session.get(
            ExecutionTokenEntity,
            execution.execution_token_id,
            with_for_update=True,
            populate_existing=True,
        )
        if step is None or version is None or token is None or version.subprocess_interface is None:
            raise NotFoundException("Pinned subprocess context not found")
        interface = SubprocessInterface.model_validate(version.subprocess_interface)
        outcome = "failure"
        outputs: dict[str, Any] = {}
        error_code = child.last_error_code
        if child.status == "COMPLETED":
            finish = (
                await self.session.exec(
                    select(WorkflowStepEntity, StepExecutionEntity)
                    .join(
                        StepExecutionEntity,
                        col(StepExecutionEntity.workflow_step_id) == col(WorkflowStepEntity.id),
                    )
                    .where(
                        StepExecutionEntity.process_instance_id == child.id,
                        StepExecutionEntity.status == "COMPLETED",
                        col(WorkflowStepEntity.step_key).in_(list(interface.outcomes.values())),
                    )
                    .order_by(col(StepExecutionEntity.ended_at).desc())
                    .limit(1)
                )
            ).first()
            if finish is None:
                error_code = "subprocess.outcome.missing"
            else:
                outcome = next(
                    key for key, value in interface.outcomes.items() if value == finish[0].step_key
                )
                for port in interface.outputs:
                    source = (
                        await self.session.exec(
                            select(StepExecutionEntity)
                            .join(
                                WorkflowStepEntity,
                                col(WorkflowStepEntity.id)
                                == col(StepExecutionEntity.workflow_step_id),
                            )
                            .where(
                                StepExecutionEntity.process_instance_id == child.id,
                                StepExecutionEntity.status == "COMPLETED",
                                WorkflowStepEntity.step_key == port.source_step,
                            )
                            .order_by(col(StepExecutionEntity.ended_at).desc())
                            .limit(1)
                        )
                    ).first()
                    snapshot = source.output_snapshot if source else None
                    if (
                        snapshot is None
                        or port.source_port not in snapshot
                        or not Draft202012Validator(port.value_schema).is_valid(
                            snapshot[port.source_port]
                        )
                    ):
                        outcome = "failure"
                        outputs = {}
                        error_code = "subprocess.output.invalid"
                        break
                    outputs[port.name] = snapshot[port.source_port]
        now = get_datetime_utc()
        attempt = StepExecutionAttemptEntity(
            step_execution_id=execution.id,
            number=await self.engine._attempt_count(execution.id) + 1,
            status="SUCCEEDED",
            dispatch_key=f"subprocess-result:{child.id}",
            ended_at=now,
        )
        self.session.add(attempt)
        execution.status = "COMPLETED"
        execution.wait_kind = None
        execution.output_snapshot = outputs
        execution.last_error_code = error_code
        execution.ended_at = now
        token.status = "ACTIVE"
        parent.status = "RUNNING"
        parent.updated_at = now
        request, submission = await self.engine._request_context(parent)
        await ProcessEventService(self.session).append(
            parent.id,
            "subprocess.completed" if outcome != "failure" else "subprocess.failed",
            step_execution_id=execution.id,
            payload={
                "child_process_ref": create_ref_id(child.id, child.version),
                "outcome": outcome,
                "error_code": error_code,
            },
        )
        await self.engine._advance(parent, token, execution, step, request, submission, outcome)
        await self.engine._run(parent, token, request, submission, f"subprocess-result:{child.id}")
        return "completed"
