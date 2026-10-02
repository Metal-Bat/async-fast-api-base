"""Transactional, idempotent single-token workflow execution."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.domain.contracts import ClientContext, client_expression_schema
from apps.expressions.application.language import ExpressionCompiler, ExpressionContext
from apps.processes.application.events import ProcessEventService
from apps.processes.application.extension_services import ProcessStepServices
from apps.processes.domain.advanced import decide_join
from apps.processes.domain.entity import (
    CompensationRecordEntity,
    ExecutionTokenEntity,
    ProcessInstanceEntity,
    ProcessTransitionEntity,
    StepExecutionAttemptEntity,
    StepExecutionEntity,
)
from apps.processes.domain.state import ProcessCommand, ProcessStatus, transition
from apps.requests.domain.entity import (
    BusinessRequestEntity,
    FormSubmissionEntity,
)
from apps.step_types.application.invocation import StepInvocationContext
from apps.step_types.application.registry import (
    HandlerDefinition,
    HandlerRegistry,
    get_registry,
)
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import (
    StepTypeEntity,
    StepTypePortEntity,
    StepTypeVersionEntity,
)
from apps.workflows.domain.entity import (
    WorkflowStepEntity,
    WorkflowStepInputBindingEntity,
    WorkflowStepTargetEntity,
    WorkflowTransitionEntity,
    WorkflowVersionEntity,
)
from core.ref_id import open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException

_MAX_SYNC_STEPS = 256
_MAX_ATTEMPTS = 3


class ProcessService:
    def __init__(self, session: AsyncSession, registry: HandlerRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or get_registry()

    async def start_request(
        self,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
        command_key: str,
    ) -> ProcessInstanceEntity:
        existing = (
            await self.session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == request.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                )
            )
        ).one_or_none()
        if existing is not None:
            return existing
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
                    WorkflowStepEntity.workflow_version_id == request.workflow_version_id,
                    StepTypeEntity.code == "START",
                )
            )
        ).one_or_none()
        if start is None:
            raise VersionConflictException("Pinned workflow has no start step")
        process = ProcessInstanceEntity(
            business_request_id=request.id,
            workflow_version_id=request.workflow_version_id,
        )
        self.session.add(process)
        await self.session.flush()
        events = ProcessEventService(self.session)
        await events.append(
            process.id,
            "request.submitted",
            actor_user_id=request.requester_user_id,
            payload={"status": request.status, "priority": request.priority},
        )
        await events.append(
            process.id,
            "process.started",
            actor_user_id=request.requester_user_id,
            payload={"status": process.status},
        )
        token = ExecutionTokenEntity(
            process_instance_id=process.id,
            current_step_id=start.id,
        )
        self.session.add(token)
        request.status = "RUNNING"
        request.updated_at = get_datetime_utc()
        await self.session.flush()
        await self._run(process, token, request, submission, command_key)
        return process

    async def get(self, ref_id: str, *, update: bool = False) -> ProcessInstanceEntity:
        entity_id, expected = open_ref_id(ref_id)
        row = await self.session.get(
            ProcessInstanceEntity, entity_id, with_for_update=update, populate_existing=update
        )
        if row is None:
            raise NotFoundException("Process not found")
        if update and row.version != expected:
            raise VersionConflictException("Process is stale")
        return row

    async def current(
        self, process_id: UUID, *, update: bool = False
    ) -> tuple[ExecutionTokenEntity, StepExecutionEntity | None]:
        token_query = select(ExecutionTokenEntity).where(
            ExecutionTokenEntity.process_instance_id == process_id,
            col(ExecutionTokenEntity.status).in_(["ACTIVE", "WAITING", "FAILED"]),
        )
        if update:
            token_query = token_query.with_for_update().execution_options(populate_existing=True)
        tokens = list((await self.session.exec(token_query)).all())
        if len(tokens) > 1:
            raise VersionConflictException("Process has multiple current positions; select one")
        token = tokens[0] if tokens else None
        if token is None:
            raise VersionConflictException("Process has no current token")
        execution = None
        if token.current_step_id is not None:
            execution_query = (
                select(StepExecutionEntity)
                .where(
                    StepExecutionEntity.execution_token_id == token.id,
                    StepExecutionEntity.workflow_step_id == token.current_step_id,
                )
                .order_by(col(StepExecutionEntity.visit_number).desc())
                .limit(1)
            )
            if update:
                execution_query = execution_query.with_for_update().execution_options(
                    populate_existing=True
                )
            execution = (await self.session.exec(execution_query)).one_or_none()
        return token, execution

    async def resume(
        self,
        ref_id: str,
        command_key: str,
        outcome: str,
        outputs: dict[str, Any],
        actor_user_id: UUID | None = None,
    ) -> ProcessInstanceEntity:
        process = await self.get(ref_id, update=True)
        if process.parent_step_execution_id is not None:
            raise VersionConflictException(
                "Child waits complete through their owning work or timer"
            )
        return await self._resume_locked(
            process, None, command_key, outcome, outputs, actor_user_id=actor_user_id
        )

    async def resume_execution(
        self,
        process_id: UUID,
        execution_id: UUID,
        command_key: str,
        outcome: str,
        outputs: dict[str, Any],
        actor_user_id: UUID | None = None,
    ) -> ProcessInstanceEntity:
        """Resume an exact durable wait after locking its owning process."""
        process = await self.session.get(
            ProcessInstanceEntity, process_id, with_for_update=True, populate_existing=True
        )
        if process is None:
            raise NotFoundException("Process not found")
        return await self._resume_locked(
            process,
            execution_id,
            command_key,
            outcome,
            outputs,
            actor_user_id=actor_user_id,
        )

    async def _resume_locked(
        self,
        process: ProcessInstanceEntity,
        expected_execution_id: UUID | None,
        command_key: str,
        outcome: str,
        outputs: dict[str, Any],
        *,
        actor_user_id: UUID | None = None,
    ) -> ProcessInstanceEntity:
        prior = (
            await self.session.exec(
                select(StepExecutionAttemptEntity).where(
                    StepExecutionAttemptEntity.dispatch_key == f"resume:{process.id}:{command_key}"
                )
            )
        ).one_or_none()
        if prior is not None:
            return process
        if expected_execution_id is None:
            token, execution = await self.current(process.id, update=True)
        else:
            execution = await self.session.get(
                StepExecutionEntity,
                expected_execution_id,
                with_for_update=True,
                populate_existing=True,
            )
            token = (
                await self.session.get(
                    ExecutionTokenEntity,
                    execution.execution_token_id,
                    with_for_update=True,
                    populate_existing=True,
                )
                if execution is not None and execution.process_instance_id == process.id
                else None
            )
        if (
            execution is None
            or execution.status != "WAITING"
            or token is None
            or (expected_execution_id is not None and execution.id != expected_execution_id)
        ):
            raise VersionConflictException("Process is not waiting on a step")
        step, kind, handler = await self._definition(execution.workflow_step_id)
        if kind == "SUBPROCESS":
            raise VersionConflictException("Subprocess results are settled by the child worker")
        self._change(process, "resume")
        await ProcessEventService(self.session).append(
            process.id,
            "process.resumed",
            actor_user_id=actor_user_id,
            step_execution_id=execution.id,
            payload={"status": process.status, "outcome": outcome},
        )
        merged = dict(outputs)
        if any(port.port_key == "outcome" and port.direction == "OUTPUT" for port in handler.ports):
            merged["outcome"] = outcome
        attempt = await self._new_attempt(
            execution, f"resume:{process.id}:{command_key}", status="RUNNING"
        )
        try:
            validated = self.registry.validate_outputs(handler, merged)
        except ValueError as exc:
            await self._fail(process, token, execution, attempt, "handler.output.invalid")
            raise VersionConflictException("Handler output is invalid") from exc
        now = get_datetime_utc()
        execution.status = "COMPLETED"
        execution.output_snapshot = validated
        execution.ended_at = now
        execution.wait_kind = None
        attempt.status = "SUCCEEDED"
        attempt.ended_at = now
        token.status = "ACTIVE"
        request, submission = await self._request_context(process)
        await self._register_compensation(process, execution, step)
        await self._advance(process, token, execution, step, request, submission, outcome)
        await self._run(process, token, request, submission, f"resume:{command_key}")
        return process

    async def command(
        self,
        ref_id: str,
        command: ProcessCommand,
        command_key: str,
        actor_user_id: UUID | None = None,
    ) -> ProcessInstanceEntity:
        process = await self.get(ref_id, update=True)
        if process.parent_step_execution_id is not None:
            raise VersionConflictException("Child process control is not supported")
        active_child = (
            await self.session.exec(
                select(StepExecutionEntity.id)
                .where(
                    StepExecutionEntity.process_instance_id == process.id,
                    StepExecutionEntity.status == "WAITING",
                    StepExecutionEntity.wait_kind == "SUBPROCESS",
                )
                .limit(1)
            )
        ).first()
        if active_child is not None:
            raise VersionConflictException("Process control while a child is active is unsupported")
        if command == "compensate":
            from apps.processes.application.compensation import CompensationService

            await CompensationService(self.session).begin(
                process.id, command_key, actor_user_id=actor_user_id
            )
            return process
        if command == "cancel" and process.status == "CANCELLED":
            return process
        if command == "cancel":
            return await self._cancel_all(process, command_key, actor_user_id)
        token, execution = await self.current(process.id, update=True)
        if execution is not None:
            existing = (
                await self.session.exec(
                    select(StepExecutionAttemptEntity).where(
                        StepExecutionAttemptEntity.dispatch_key
                        == f"command:{process.id}:{command_key}"
                    )
                )
            ).one_or_none()
            if existing is not None:
                return process
        self._change(process, command)
        now = get_datetime_utc()
        if execution is not None and command == "pause":
            await self._new_attempt(
                execution,
                f"command:{process.id}:{command_key}",
                status="WAITING",
            )
        if command == "pause":
            pass
        elif command == "retry":
            if execution is None or execution.status not in {"FAILED", "TIMED_OUT"}:
                raise VersionConflictException("No failed step can be retried")
            attempts = await self._attempt_count(execution.id)
            step = await self.session.get(WorkflowStepEntity, execution.workflow_step_id)
            retry_limit = int((step.flow if step else {}).get("retry_limit", _MAX_ATTEMPTS))
            if attempts >= retry_limit:
                raise VersionConflictException("Retry limit reached")
            process.ended_at = None
            process.last_error_code = None
            token.status = "ACTIVE"
            execution.status = "RUNNING"
            execution.ended_at = None
            await ProcessEventService(self.session).append(
                process.id,
                "step.retry_started",
                actor_user_id=actor_user_id,
                step_execution_id=execution.id,
                payload={"status": process.status, "attempt": attempts + 1},
            )
            request, submission = await self._request_context(process)
            request.status = "RUNNING"
            request.closed_at = None
            await self._execute_existing(
                process,
                token,
                execution,
                request,
                submission,
                f"retry:{process.id}:{command_key}",
            )
        elif command == "resume":
            if token.status == "WAITING":
                process.status = "WAITING"
            else:
                request, submission = await self._request_context(process)
                await self._run(process, token, request, submission, f"resume:{command_key}")
        process.updated_at = now
        if command != "retry":
            event_type = {
                "pause": "process.paused",
                "resume": "process.resumed",
            }[command]
            await ProcessEventService(self.session).append(
                process.id,
                event_type,
                actor_user_id=actor_user_id,
                step_execution_id=execution.id if execution else None,
                payload={"status": process.status},
            )
        return process

    async def _cancel_all(
        self,
        process: ProcessInstanceEntity,
        command_key: str,
        actor_user_id: UUID | None,
    ) -> ProcessInstanceEntity:
        """Cancel every live branch in one aggregate transaction."""
        self._change(process, "cancel")
        now = get_datetime_utc()
        tokens = list(
            (
                await self.session.exec(
                    select(ExecutionTokenEntity)
                    .where(
                        ExecutionTokenEntity.process_instance_id == process.id,
                        col(ExecutionTokenEntity.status).in_(["ACTIVE", "WAITING", "FAILED"]),
                    )
                    .order_by(col(ExecutionTokenEntity.id))
                    .with_for_update()
                )
            ).all()
        )
        token_ids = [token.id for token in tokens]
        executions = (
            list(
                (
                    await self.session.exec(
                        select(StepExecutionEntity)
                        .where(
                            col(StepExecutionEntity.execution_token_id).in_(token_ids),
                            col(StepExecutionEntity.status).in_(["PENDING", "RUNNING", "WAITING"]),
                        )
                        .order_by(col(StepExecutionEntity.id))
                        .with_for_update()
                    )
                ).all()
            )
            if token_ids
            else []
        )
        from apps.notifications.application.service import NotificationService
        from apps.processes.application.waits import ProcessWaitService

        waits = ProcessWaitService(self.session)
        await NotificationService(self.session).cancel_process(process.id)
        for token in tokens:
            token.status = "CANCELLED"
        for execution in executions:
            await self._new_attempt(
                execution,
                f"command:{process.id}:{command_key}:{execution.id}",
                status="CANCELLED",
            )
            execution.status = "CANCELLED"
            execution.ended_at = now
            await waits.cancel_execution(execution.id)
        request, _ = await self._request_context(process)
        request.status = "CANCELLED"
        request.closed_at = now
        request.updated_at = now
        process.updated_at = now
        await ProcessEventService(self.session).append(
            process.id,
            "process.cancelled",
            actor_user_id=actor_user_id,
            payload={"status": process.status},
            command_key=command_key,
        )
        return process

    async def timeout(
        self, ref_id: str, command_key: str, actor_user_id: UUID | None = None
    ) -> ProcessInstanceEntity:
        process = await self.get(ref_id, update=True)
        if process.parent_step_execution_id is not None:
            raise VersionConflictException("Direct child process timeout is unsupported")
        token, execution = await self.current(process.id, update=True)
        if execution is not None and execution.wait_kind == "SUBPROCESS":
            raise VersionConflictException("Parent timeout while a child is active is unsupported")
        return await self._timeout_locked(process, token, execution, command_key, actor_user_id)

    async def timeout_execution(
        self,
        process_id: UUID,
        execution_id: UUID,
        command_key: str,
        actor_user_id: UUID | None = None,
    ) -> ProcessInstanceEntity:
        """Apply an authorized work-item timeout to its exact durable wait."""
        process = await self.session.get(
            ProcessInstanceEntity, process_id, with_for_update=True, populate_existing=True
        )
        if process is None:
            raise NotFoundException("Process not found")
        token, execution = await self.current(process.id, update=True)
        if execution is None or execution.id != execution_id:
            raise VersionConflictException("Process is not waiting on this work item")
        return await self._timeout_locked(process, token, execution, command_key, actor_user_id)

    async def _timeout_locked(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        execution: StepExecutionEntity | None,
        command_key: str,
        actor_user_id: UUID | None,
    ) -> ProcessInstanceEntity:
        if execution is None or execution.started_at is None:
            raise VersionConflictException("No running step can time out")
        step = await self.session.get(WorkflowStepEntity, execution.workflow_step_id)
        if step is None or step.timeout_seconds is None:
            raise VersionConflictException("Step has no timeout")
        if get_datetime_utc() < execution.started_at + timedelta(seconds=step.timeout_seconds):
            raise VersionConflictException("Step timeout has not elapsed")
        attempt = await self._new_attempt(
            execution, f"timeout:{process.id}:{command_key}", status="RUNNING"
        )
        await self._fail(
            process,
            token,
            execution,
            attempt,
            "step.timeout",
            timed_out=True,
            actor_user_id=actor_user_id,
        )
        return process

    async def complete_background(
        self, attempt_id: UUID, outputs: dict[str, Any], *, outcome: str | None = None
    ) -> str:
        """Validate and apply one background result exactly once."""
        attempt = await self.session.get(
            StepExecutionAttemptEntity, attempt_id, with_for_update=True, populate_existing=True
        )
        if attempt is None:
            raise NotFoundException("Background attempt not found")
        if attempt.status == "SUCCEEDED":
            return "duplicate"
        execution = await self.session.get(
            StepExecutionEntity,
            attempt.step_execution_id,
            with_for_update=True,
            populate_existing=True,
        )
        if execution is None:
            raise NotFoundException("Step execution not found")
        process = await self.session.get(
            ProcessInstanceEntity,
            execution.process_instance_id,
            with_for_update=True,
            populate_existing=True,
        )
        token = await self.session.get(
            ExecutionTokenEntity,
            execution.execution_token_id,
            with_for_update=True,
            populate_existing=True,
        )
        if process is None or token is None:
            raise NotFoundException("Process state not found")
        if (
            attempt.status not in {"WAITING", "RUNNING"}
            or execution.status != "WAITING"
            or process.status != "WAITING"
            or token.status != "WAITING"
        ):
            if attempt.status in {"WAITING", "RUNNING"}:
                attempt.status = "CANCELLED"
                attempt.ended_at = get_datetime_utc()
            return "late_ignored"
        step, _, handler = await self._definition(execution.workflow_step_id)
        try:
            if outcome is not None and outcome not in handler.outcomes:
                raise ValueError("Unknown background outcome")
            validated = self.registry.validate_outputs(handler, outputs)
        except ValueError:
            await self._fail(process, token, execution, attempt, "handler.output.invalid")
            return "failed"
        now = get_datetime_utc()
        execution.status = "COMPLETED"
        execution.output_snapshot = validated
        execution.wait_kind = None
        execution.ended_at = now
        attempt.status = "SUCCEEDED"
        attempt.ended_at = now
        token.status = "ACTIVE"
        process.status = "RUNNING"
        process.updated_at = now
        request, submission = await self._request_context(process)
        if process.parent_step_execution_id is None:
            request.status = "RUNNING"
            request.closed_at = None
            request.updated_at = now
        await ProcessEventService(self.session).append(
            process.id,
            "automation.completed",
            step_execution_id=execution.id,
            payload={"attempt": attempt.number},
        )
        await ProcessEventService(self.session).append(
            process.id,
            "step.completed",
            step_execution_id=execution.id,
            payload={"status": execution.status, "attempt": attempt.number},
        )
        await self._register_compensation(process, execution, step)
        await self._advance(process, token, execution, step, request, submission, outcome)
        await self._run(process, token, request, submission, f"background:{attempt.id}")
        return "completed"

    async def fail_background(self, attempt_id: UUID, code: str) -> str:
        """Fail the current attempt once; ignore stale or cancelled deliveries."""
        attempt = await self.session.get(
            StepExecutionAttemptEntity, attempt_id, with_for_update=True, populate_existing=True
        )
        if attempt is None:
            raise NotFoundException("Background attempt not found")
        if attempt.status not in {"WAITING", "RUNNING"}:
            return "duplicate"
        execution = await self.session.get(
            StepExecutionEntity,
            attempt.step_execution_id,
            with_for_update=True,
            populate_existing=True,
        )
        if execution is None:
            raise NotFoundException("Step execution not found")
        process = await self.session.get(
            ProcessInstanceEntity,
            execution.process_instance_id,
            with_for_update=True,
            populate_existing=True,
        )
        token = await self.session.get(
            ExecutionTokenEntity,
            execution.execution_token_id,
            with_for_update=True,
            populate_existing=True,
        )
        if process is None or token is None:
            raise NotFoundException("Process state not found")
        if execution.status != "WAITING" or process.status != "WAITING":
            attempt.status = "CANCELLED"
            attempt.ended_at = get_datetime_utc()
            return "late_ignored"
        await ProcessEventService(self.session).append(
            process.id,
            "automation.failed",
            step_execution_id=execution.id,
            payload={"attempt": attempt.number, "error_code": code},
        )
        await self._fail(process, token, execution, attempt, code)
        return "failed"

    async def fail_wait_execution(self, process_id: UUID, execution_id: UUID, code: str) -> bool:
        """Fail one exact unresolved wait; stale failure messages are safe no-ops."""
        process = await self.session.get(
            ProcessInstanceEntity, process_id, with_for_update=True, populate_existing=True
        )
        if process is None:
            raise NotFoundException("Process not found")
        token, execution = await self.current(process.id, update=True)
        if execution is None or execution.id != execution_id or execution.status != "WAITING":
            return False
        attempt = (
            await self.session.exec(
                select(StepExecutionAttemptEntity)
                .where(StepExecutionAttemptEntity.step_execution_id == execution.id)
                .order_by(col(StepExecutionAttemptEntity.number).desc())
                .with_for_update()
                .limit(1)
            )
        ).one_or_none()
        await self._fail(process, token, execution, attempt, code)
        return True

    def _change(self, process: ProcessInstanceEntity, command: ProcessCommand) -> ProcessStatus:
        try:
            target = transition(process.status, command)  # ty:ignore[invalid-argument-type]
        except ValueError as exc:
            raise VersionConflictException(str(exc)) from exc
        process.status = target
        if target in {"COMPLETED", "FAILED", "CANCELLED"}:
            process.ended_at = get_datetime_utc()
        else:
            process.ended_at = None
        return target

    async def _run(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
        command_key: str,
    ) -> None:
        for ordinal in range(_MAX_SYNC_STEPS):
            if token.current_step_id is None or token.status != "ACTIVE":
                return
            execution = await self._create_execution(process, token)
            stopped = await self._execute_existing(
                process,
                token,
                execution,
                request,
                submission,
                f"{process.id}:{command_key}:{ordinal}",
            )
            if stopped:
                return
        raise VersionConflictException("Synchronous workflow step limit exceeded")

    async def _create_execution(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        *,
        emit_event: bool = True,
    ) -> StepExecutionEntity:
        if token.current_step_id is None:
            raise VersionConflictException("Active token has no current step")
        pending = (
            await self.session.exec(
                select(StepExecutionEntity).where(
                    StepExecutionEntity.execution_token_id == token.id,
                    StepExecutionEntity.workflow_step_id == token.current_step_id,
                    StepExecutionEntity.status == "PENDING",
                )
            )
        ).one_or_none()
        if pending is not None:
            return pending
        visit = (
            await self.session.exec(
                select(func.count())
                .select_from(StepExecutionEntity)
                .where(
                    StepExecutionEntity.execution_token_id == token.id,
                    StepExecutionEntity.workflow_step_id == token.current_step_id,
                )
            )
        ).one()
        execution = StepExecutionEntity(
            process_instance_id=process.id,
            execution_token_id=token.id,
            workflow_step_id=token.current_step_id,
            visit_number=visit + 1,
        )
        self.session.add(execution)
        await self.session.flush()
        if emit_event:
            await self._step_started_event(process, execution)
        return execution

    async def _step_started_event(
        self, process: ProcessInstanceEntity, execution: StepExecutionEntity
    ) -> None:
        await ProcessEventService(self.session).append(
            process.id,
            "step.started",
            step_execution_id=execution.id,
            payload={"status": execution.status},
        )

    async def _execute_existing(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        execution: StepExecutionEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
        dispatch_key: str,
    ) -> bool:
        step, kind, handler = await self._definition(execution.workflow_step_id)
        inputs = execution.input_snapshot or await self._inputs(
            process, token, step, request, submission
        )
        try:
            validated_inputs = self.registry.validate_inputs(handler, inputs)
        except ValueError as exc:
            attempt = await self._new_attempt(execution, dispatch_key, status="RUNNING")
            await self._fail(process, token, execution, attempt, "handler.input.invalid")
            raise VersionConflictException("Handler input is invalid") from exc
        now = get_datetime_utc()
        execution.status = "RUNNING"
        execution.input_snapshot = validated_inputs
        execution.started_at = execution.started_at or now
        attempt = await self._new_attempt(execution, dispatch_key, status="RUNNING")
        if handler.execution_mode in {"HUMAN", "BACKGROUND", "WAIT"}:
            wait_kind = {
                "HUMAN": "HUMAN",
                "BACKGROUND": "BACKGROUND",
                "WAIT": (
                    "SUBPROCESS"
                    if kind == "SUBPROCESS"
                    else "EVENT"
                    if kind == "EVENT_WAIT"
                    else "TIMER"
                ),
            }[handler.execution_mode]
            execution.status = "WAITING"
            execution.wait_kind = wait_kind
            attempt.status = "WAITING"
            token.status = "WAITING"
            process.status = "WAITING"
            process.updated_at = now
            if handler.execution_mode == "HUMAN":
                from apps.work_items.application.service import WorkItemService

                targets = await self._human_targets(step, process, request, submission)
                initial_data = validated_inputs.get("initial_data") or {}
                try:
                    await WorkItemService(self.session).create_for_wait(
                        execution,
                        step,
                        request,
                        targets,
                        initial_data if isinstance(initial_data, dict) else {},
                    )
                except VersionConflictException:
                    await self._fail(process, token, execution, attempt, "work_item.no_candidate")
                    raise
            elif handler.execution_mode == "BACKGROUND":
                if kind not in {"SERVICE_TASK", "NOTIFICATION"} and handler.implementation is None:
                    await self._fail(
                        process, token, execution, attempt, "background.operation.unsupported"
                    )
                    raise VersionConflictException("Background operation is not available")
                try:
                    if kind == "SERVICE_TASK":
                        from apps.processes.application.automation import AutomationDispatcher

                        await AutomationDispatcher(self.session).stage(
                            attempt=attempt, step=step, handler=handler, request=request
                        )
                    elif kind == "NOTIFICATION":
                        from apps.integrations.application.service import ConnectionService
                        from apps.notifications.application.service import NotificationService
                        from apps.processes.application.automation import _provider

                        notifications = await NotificationService(self.session).stage(
                            attempt=attempt,
                            step=step,
                            handler=handler,
                            request=request,
                            process=process,
                            inputs=validated_inputs,
                            connection_service=ConnectionService(self.session, _provider()),
                        )
                        await ProcessEventService(self.session).append(
                            process.id,
                            "notification.created",
                            step_execution_id=execution.id,
                            payload={
                                "channel": str(step.config.get("channel", "EMAIL")),
                                "recipient_count": len(notifications),
                                "attempt": attempt.number,
                            },
                        )
                    else:
                        from apps.processes.application.automation import AutomationDispatcher

                        await AutomationDispatcher(self.session).stage_extension(
                            attempt=attempt, step=step, handler=handler, request=request
                        )
                except (TypeError, ValueError) as exc:
                    await self._fail(
                        process, token, execution, attempt, "background.operation.invalid"
                    )
                    raise VersionConflictException("Background operation is invalid") from exc
            elif kind == "SUBPROCESS":
                from apps.processes.application.subprocess import SubprocessService

                await SubprocessService(self.session, self)._start(
                    process, token, execution, step, request, submission
                )
            else:
                from apps.processes.application.waits import ProcessWaitService

                try:
                    await ProcessWaitService(self.session).register(
                        execution, kind, step.config, validated_inputs
                    )
                except (TypeError, ValueError) as exc:
                    await self._fail(process, token, execution, attempt, "wait.contract.invalid")
                    raise VersionConflictException("Wait configuration is invalid") from exc
            await ProcessEventService(self.session).append(
                process.id,
                "step.waiting",
                step_execution_id=execution.id,
                payload={"status": execution.status, "wait_kind": execution.wait_kind},
            )
            return True
        try:
            outputs, outcome = await self._invoke(
                kind,
                handler,
                step.config,
                validated_inputs,
                process,
                request,
                submission,
                execution,
                attempt,
                dispatch_key,
            )
            validated_outputs = self.registry.validate_outputs(handler, outputs)
        except (ValueError, TypeError) as exc:
            await self._fail(process, token, execution, attempt, "handler.output.invalid")
            raise VersionConflictException("Handler execution failed") from exc
        execution.status = "COMPLETED"
        execution.output_snapshot = validated_outputs
        execution.ended_at = now
        attempt.status = "SUCCEEDED"
        attempt.ended_at = now
        await ProcessEventService(self.session).append(
            process.id,
            "step.completed",
            step_execution_id=execution.id,
            payload={"status": execution.status, "attempt": attempt.number},
        )
        await self._register_compensation(process, execution, step)
        if kind == "FINISH":
            await self._complete(process, token, request)
            return True
        await self._advance(process, token, execution, step, request, submission, outcome)
        return token.status != "ACTIVE"

    async def _human_targets(
        self,
        step: WorkflowStepEntity,
        process: ProcessInstanceEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> list[WorkflowStepTargetEntity]:
        from apps.users.domain.entity import UserEntity
        from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity

        targets = list(
            (
                await self.session.exec(
                    select(WorkflowStepTargetEntity).where(
                        WorkflowStepTargetEntity.workflow_step_id == step.id
                    )
                )
            ).all()
        )
        if process.parent_step_execution_id is not None:
            from apps.users.domain.entity import UserEntity
            from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
            from apps.workflows.domain.entity import WorkflowVersionEntity
            from apps.workflows.domain.subprocess import SubprocessInterface

            version = await self.session.get(WorkflowVersionEntity, process.workflow_version_id)
            if version is not None and version.subprocess_interface is not None:
                interface = SubprocessInterface.model_validate(version.subprocess_interface)
                assigned = [port for port in interface.inputs if port.assignment]
                if assigned:
                    dynamic: list[WorkflowStepTargetEntity] = []
                    for port in assigned:
                        value = (process.input_context or {}).get(port.name)
                        if not isinstance(value, str):
                            raise VersionConflictException("Child assignment is missing")
                        identifier, revision = open_ref_id(value)
                        if port.assignment == "user":
                            user = await self.session.get(UserEntity, identifier)
                            if user is None or user.deleted_at or user.version != revision:
                                raise VersionConflictException(
                                    "Child assignment user is unavailable"
                                )
                            dynamic.append(
                                WorkflowStepTargetEntity(workflow_step_id=step.id, user_id=user.id)
                            )
                        else:
                            group = await self.session.get(WorkGroupEntity, identifier)
                            membership = (
                                await self.session.exec(
                                    select(WorkGroupMemberEntity)
                                    .where(
                                        WorkGroupMemberEntity.work_group_id == identifier,
                                        col(WorkGroupMemberEntity.is_active).is_(True),
                                    )
                                    .limit(1)
                                )
                            ).first()
                            if (
                                group is None
                                or group.deleted_at
                                or not group.is_active
                                or group.version != revision
                                or membership is None
                            ):
                                raise VersionConflictException(
                                    "Child assignment group is unavailable"
                                )
                            dynamic.append(
                                WorkflowStepTargetEntity(
                                    workflow_step_id=step.id, work_group_id=group.id
                                )
                            )
                    return dynamic
        eligible: list[WorkflowStepTargetEntity] = []
        for target in targets:
            if target.condition and not await self._condition(
                target.condition, process, request, submission
            ):
                continue
            if target.user_id is not None:
                user = await self.session.get(UserEntity, target.user_id)
                if user is not None and user.deleted_at is None:
                    eligible.append(target)
                continue
            if target.work_group_id is None:
                continue
            group = await self.session.get(WorkGroupEntity, target.work_group_id)
            member = (
                await self.session.exec(
                    select(WorkGroupMemberEntity).where(
                        WorkGroupMemberEntity.work_group_id == target.work_group_id,
                        col(WorkGroupMemberEntity.is_active).is_(True),
                    )
                )
            ).first()
            if group is not None and group.deleted_at is None and group.is_active and member:
                eligible.append(target)
        return eligible

    async def _invoke(
        self,
        kind: str,
        handler: HandlerDefinition,
        config: dict[str, Any],
        inputs: dict[str, Any],
        process: ProcessInstanceEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
        execution: StepExecutionEntity,
        attempt: StepExecutionAttemptEntity,
        dispatch_key: str,
    ) -> tuple[dict[str, Any], str | None]:
        if kind == "START":
            return {}, None
        if kind == "FINISH":
            return {}, None
        if kind == "TRANSFORM":
            result = self.registry.execute_transform(
                handler.handler_key, handler.handler_version, config, inputs.get("value")
            )
            return {"result": result.value}, None
        if kind == "DECISION":
            context = await self._expression_context(process, request, submission)
            schemas = {key: self._schema(value) for key, value in context.values().items()}
            schemas["client"] = client_expression_schema()
            result = (
                ExpressionCompiler()
                .compile(str(config["expression"]), schemas, expected_schema={"type": "string"})
                .evaluate(context)
            )
            return {"outcome": result.value}, str(result.value)
        if handler.implementation is not None and handler.execution_mode == "SYNC":
            workflow = await self.session.get(WorkflowVersionEntity, process.workflow_version_id)
            actor_id = workflow.published_by_user_id if workflow is not None else None
            if actor_id is None:
                raise ValueError("Published workflow has no execution principal")
            context = StepInvocationContext(
                actor_id=actor_id,
                process_id=process.id,
                request_id=request.id,
                execution_id=execution.id,
                attempt_id=attempt.id,
                idempotency_key=dispatch_key,
                inputs=inputs,
                services=ProcessStepServices(
                    self.session, actor_id=actor_id, process_id=process.id, request_id=request.id
                ),
                cancelled=lambda: process.status != "RUNNING",
            )
            result = await self.registry.invoke(
                handler.handler_key, handler.handler_version, config, context
            )
            return result.outputs, result.outcome
        raise ValueError(f"Synchronous handler {kind} has no runtime adapter")

    async def _advance(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        execution: StepExecutionEntity,
        step: WorkflowStepEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
        outcome: str | None,
    ) -> None:
        flow = step.flow or {}
        if flow.get("split") == "ALL":
            edges = await self._eligible_transitions(process, step.id, outcome, request, submission)
            if len(edges) < 2:
                await self._fail(process, token, execution, None, "split.branches.missing")
                raise VersionConflictException(
                    "Parallel split has fewer than two eligible branches"
                )
            token.status = "WAITING"
            await ProcessEventService(self.session).append(
                process.id,
                "split.created",
                step_execution_id=execution.id,
                payload={"branches": len(edges), "step": step.step_key},
            )
            children: list[ExecutionTokenEntity] = []
            for edge in edges:
                child = ExecutionTokenEntity(
                    process_instance_id=process.id,
                    current_step_id=edge.target_step_id,
                    parent_token_id=token.id,
                    branch_key=f"{execution.id}:{edge.id}",
                )
                self.session.add(child)
                await self.session.flush()
                next_execution = await self._create_execution(process, child, emit_event=False)
                await self._record_transition(process, execution, next_execution, edge, step)
                children.append(child)
            for child in children:
                await self._run(
                    process, child, request, submission, f"split:{execution.id}:{child.branch_key}"
                )
            return
        edge = await self._choose_transition(process, step.id, outcome, request, submission)
        if edge is None:
            await self._fail(process, token, execution, None, "transition.not_found")
            raise VersionConflictException("No eligible workflow transition")
        target_step = await self.session.get(WorkflowStepEntity, edge.target_step_id)
        if target_step is None:
            raise NotFoundException("Workflow step not found")
        if (target_step.flow or {}).get("join") == "ALL" and token.parent_token_id is not None:
            await self._arrive_join(
                process, token, execution, edge, step, target_step, request, submission
            )
            return
        visits = (
            await self.session.exec(
                select(func.count())
                .select_from(StepExecutionEntity)
                .where(
                    StepExecutionEntity.execution_token_id == token.id,
                    StepExecutionEntity.workflow_step_id == edge.target_step_id,
                )
            )
        ).one()
        maximum = (target_step.flow or {}).get("max_visits")
        if maximum is not None and visits >= int(maximum):
            await self._fail(process, token, execution, None, "loop.visit_limit")
            raise VersionConflictException("Workflow loop visit limit reached")
        token.current_step_id = edge.target_step_id
        next_execution = await self._create_execution(process, token, emit_event=False)
        await self._record_transition(process, execution, next_execution, edge, step)

    async def _record_transition(
        self,
        process: ProcessInstanceEntity,
        execution: StepExecutionEntity,
        next_execution: StepExecutionEntity,
        edge: WorkflowTransitionEntity,
        source_step: WorkflowStepEntity,
    ) -> None:
        self.session.add(
            ProcessTransitionEntity(
                process_instance_id=process.id,
                from_step_execution_id=execution.id,
                to_step_execution_id=next_execution.id,
                workflow_transition_id=edge.id,
                outcome_key=edge.outcome,
            )
        )
        await self.session.flush()
        target_step = await self.session.get(WorkflowStepEntity, edge.target_step_id)
        if target_step is None:
            raise NotFoundException("Workflow step not found")
        await ProcessEventService(self.session).append(
            process.id,
            "transition.taken",
            step_execution_id=execution.id,
            payload={
                "outcome": edge.outcome,
                "source_step": source_step.step_key,
                "target_step": target_step.step_key,
                "predicate_contract": "bpms.predicates/1",
            },
        )
        await self._step_started_event(process, next_execution)

    async def _eligible_transitions(
        self,
        process: ProcessInstanceEntity,
        step_id: UUID,
        outcome: str | None,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> list[WorkflowTransitionEntity]:
        candidates = list(
            (
                await self.session.exec(
                    select(WorkflowTransitionEntity)
                    .where(WorkflowTransitionEntity.source_step_id == step_id)
                    .order_by(
                        col(WorkflowTransitionEntity.priority).desc(),
                        col(WorkflowTransitionEntity.id),
                    )
                )
            ).all()
        )
        result = []
        for edge in candidates:
            if outcome is not None and edge.outcome != outcome:
                continue
            if edge.condition and not await self._condition(
                edge.condition, process, request, submission
            ):
                continue
            result.append(edge)
        return result

    async def _arrive_join(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        execution: StepExecutionEntity,
        edge: WorkflowTransitionEntity,
        source_step: WorkflowStepEntity,
        join_step: WorkflowStepEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> None:
        """Persist one arrival and release its parent scope exactly once under the process lock."""
        token.current_step_id = join_step.id
        arrival = await self._create_execution(process, token, emit_event=False)
        now = get_datetime_utc()
        arrival.status = "COMPLETED"
        arrival.input_snapshot = {}
        arrival.output_snapshot = {}
        arrival.started_at = now
        arrival.ended_at = now
        token.status = "COMPLETED"
        await self._record_transition(process, execution, arrival, edge, source_step)
        siblings = list(
            (
                await self.session.exec(
                    select(ExecutionTokenEntity)
                    .where(ExecutionTokenEntity.parent_token_id == token.parent_token_id)
                    .order_by(col(ExecutionTokenEntity.id))
                    .with_for_update()
                )
            ).all()
        )
        states = tuple(
            "ARRIVED"
            if item.status == "COMPLETED" and item.current_step_id == join_step.id
            else item.status
            for item in siblings
        )
        policy = str((join_step.flow or {}).get("cancelled_branches", "ARRIVE"))
        decision = decide_join(states, policy)  # ty:ignore[invalid-argument-type]
        events = ProcessEventService(self.session)
        await events.append(
            process.id,
            "join.arrived",
            step_execution_id=arrival.id,
            payload={
                "step": join_step.step_key,
                "arrived": states.count("ARRIVED"),
                "required": len(states),
            },
        )
        if decision == "WAIT":
            if any(item.status == "WAITING" for item in siblings):
                process.status = "WAITING"
            return
        if decision == "FAIL":
            process.status = "FAILED"
            process.last_error_code = "join.branch_failed"
            process.ended_at = now
            request.status = "FAILED"
            request.closed_at = now
            await events.append(
                process.id,
                "process.failed",
                step_execution_id=arrival.id,
                payload={"status": process.status, "error_code": process.last_error_code},
            )
            return
        parent = await self.session.get(
            ExecutionTokenEntity,
            token.parent_token_id,
            with_for_update=True,
            populate_existing=True,
        )
        if parent is None:
            raise NotFoundException("Parallel scope token not found")
        if parent.status == "ACTIVE" and parent.current_step_id == join_step.id:
            return
        parent.status = "ACTIVE"
        parent.current_step_id = join_step.id
        process.status = "RUNNING"
        process.ended_at = None
        join_execution = await self._create_execution(process, parent, emit_event=False)
        await events.append(
            process.id,
            "join.released",
            step_execution_id=join_execution.id,
            payload={"step": join_step.step_key, "branches": len(states)},
        )
        await self._step_started_event(process, join_execution)
        await self._run(process, parent, request, submission, f"join:{join_execution.id}")

    async def _register_compensation(
        self,
        process: ProcessInstanceEntity,
        execution: StepExecutionEntity,
        step: WorkflowStepEntity,
    ) -> None:
        target_key = (step.flow or {}).get("compensation_step")
        if not target_key:
            return
        existing = (
            await self.session.exec(
                select(CompensationRecordEntity).where(
                    CompensationRecordEntity.source_execution_id == execution.id
                )
            )
        ).one_or_none()
        if existing is not None:
            return
        target = (
            await self.session.exec(
                select(WorkflowStepEntity).where(
                    WorkflowStepEntity.workflow_version_id == process.workflow_version_id,
                    WorkflowStepEntity.step_key == target_key,
                )
            )
        ).one_or_none()
        if target is None:
            raise VersionConflictException("Compensation step is missing from pinned workflow")
        ordinal = (
            await self.session.exec(
                select(func.count())
                .select_from(CompensationRecordEntity)
                .where(CompensationRecordEntity.process_instance_id == process.id)
            )
        ).one()
        self.session.add(
            CompensationRecordEntity(
                process_instance_id=process.id,
                source_execution_id=execution.id,
                compensation_step_id=target.id,
                ordinal=ordinal + 1,
            )
        )
        await self.session.flush()
        await ProcessEventService(self.session).append(
            process.id,
            "compensation.registered",
            step_execution_id=execution.id,
            payload={"ordinal": ordinal + 1, "compensation_step": target.step_key},
        )

    async def _choose_transition(
        self,
        process: ProcessInstanceEntity,
        step_id: UUID,
        outcome: str | None,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> WorkflowTransitionEntity | None:
        candidates = (
            await self.session.exec(
                select(WorkflowTransitionEntity)
                .where(WorkflowTransitionEntity.source_step_id == step_id)
                .order_by(
                    col(WorkflowTransitionEntity.priority).desc(),
                    col(WorkflowTransitionEntity.id),
                )
            )
        ).all()
        fallback = None
        for edge in candidates:
            if outcome is not None and edge.outcome != outcome:
                continue
            if edge.condition and not await self._condition(
                edge.condition, process, request, submission
            ):
                continue
            if not edge.is_default:
                return edge
            fallback = fallback or edge
        return fallback

    async def _condition(
        self,
        source: str,
        process: ProcessInstanceEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> bool:
        context = await self._expression_context(process, request, submission)
        schemas = {key: self._schema(value) for key, value in context.values().items()}
        schemas["client"] = client_expression_schema()
        return bool(
            ExpressionCompiler()
            .compile(source, schemas, expected_schema={"type": "boolean"})
            .evaluate(context)
            .value
        )

    async def _expression_context(
        self,
        process: ProcessInstanceEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> ExpressionContext:
        rows = (
            await self.session.exec(
                select(WorkflowStepEntity, StepExecutionEntity)
                .join(
                    StepExecutionEntity,
                    col(StepExecutionEntity.workflow_step_id) == col(WorkflowStepEntity.id),
                )
                .where(
                    StepExecutionEntity.process_instance_id == process.id,
                    StepExecutionEntity.status == "COMPLETED",
                )
                .order_by(
                    col(StepExecutionEntity.visit_number),
                    col(StepExecutionEntity.created_at),
                )
            )
        ).all()
        steps = {
            step.step_key: {"outputs": execution.output_snapshot or {}} for step, execution in rows
        }
        return ExpressionContext(
            request=submission.data,
            process={
                "status": process.status,
                "priority": request.priority if process.parent_step_execution_id is None else 0,
            },
            current_user={},
            steps=steps,
            client=ClientContext.from_origin_snapshot(
                request.origin_client_context if process.parent_step_execution_id is None else None
            ).expression_values(),
        )

    async def _inputs(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        step: WorkflowStepEntity,
        request: BusinessRequestEntity,
        submission: FormSubmissionEntity,
    ) -> dict[str, Any]:
        rows = (
            await self.session.exec(
                select(WorkflowStepInputBindingEntity, StepTypePortEntity)
                .join(
                    StepTypePortEntity,
                    col(StepTypePortEntity.id)
                    == col(WorkflowStepInputBindingEntity.target_port_id),
                )
                .where(WorkflowStepInputBindingEntity.workflow_step_id == step.id)
                .order_by(
                    col(StepTypePortEntity.port_key),
                    col(WorkflowStepInputBindingEntity.ordinal),
                )
            )
        ).all()
        result: dict[str, Any] = {}
        lists: dict[str, list[Any]] = {}
        for binding, port in rows:
            if binding.source_kind == "CONSTANT":
                value = binding.constant_value
            elif binding.source_kind == "REQUEST":
                value = self._pointer(submission.data, binding.source_path or "")
            elif binding.source_kind == "CONTEXT":
                value = self._pointer(
                    {
                        "process": {"status": process.status},
                        "request": {
                            "priority": request.priority
                            if process.parent_step_execution_id is None
                            else 0
                        },
                    },
                    binding.source_path or "",
                )
            else:
                value = await self._step_output(token.id, binding)
            if port.cardinality == "LIST":
                bucket = lists.setdefault(port.port_key, [])
                if isinstance(value, list):
                    bucket.extend(value)
                else:
                    bucket.append(value)
            else:
                result[port.port_key] = value
        result.update(lists)
        return result

    async def _step_output(self, token_id: UUID, binding: WorkflowStepInputBindingEntity) -> Any:
        if binding.source_step_id is None or binding.source_port_id is None:
            raise ValueError("Step output binding is incomplete")
        port = await self.session.get(StepTypePortEntity, binding.source_port_id)
        execution = (
            await self.session.exec(
                select(StepExecutionEntity)
                .where(
                    StepExecutionEntity.execution_token_id == token_id,
                    StepExecutionEntity.workflow_step_id == binding.source_step_id,
                    StepExecutionEntity.status == "COMPLETED",
                )
                .order_by(col(StepExecutionEntity.visit_number).desc())
                .limit(1)
            )
        ).one_or_none()
        if port is None or execution is None or execution.output_snapshot is None:
            raise ValueError("Prior step output is unavailable")
        return execution.output_snapshot[port.port_key]

    async def _definition(self, step_id: UUID) -> tuple[WorkflowStepEntity, str, HandlerDefinition]:
        row = (
            await self.session.exec(
                select(WorkflowStepEntity, StepTypeEntity, StepTypeVersionEntity)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.id) == col(WorkflowStepEntity.step_type_version_id),
                )
                .join(
                    StepTypeEntity,
                    col(StepTypeEntity.id) == col(StepTypeVersionEntity.step_type_id),
                )
                .where(WorkflowStepEntity.id == step_id)
            )
        ).one_or_none()
        if row is None:
            raise NotFoundException("Workflow step not found")
        step, kind, version = row
        handler = await StepTypeService(self.session, self.registry).registered_handler(version)
        return step, kind.code, handler

    async def _new_attempt(
        self, execution: StepExecutionEntity, dispatch_key: str, *, status: str
    ) -> StepExecutionAttemptEntity:
        number = await self._attempt_count(execution.id) + 1
        attempt = StepExecutionAttemptEntity(
            step_execution_id=execution.id,
            number=number,
            status=status,
            dispatch_key=dispatch_key,
            ended_at=get_datetime_utc() if status in {"CANCELLED", "TIMED_OUT"} else None,
        )
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def _attempt_count(self, execution_id: UUID) -> int:
        return (
            await self.session.exec(
                select(func.count())
                .select_from(StepExecutionAttemptEntity)
                .where(StepExecutionAttemptEntity.step_execution_id == execution_id)
            )
        ).one()

    async def _fail(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        execution: StepExecutionEntity,
        attempt: StepExecutionAttemptEntity | None,
        code: str,
        *,
        timed_out: bool = False,
        actor_user_id: UUID | None = None,
    ) -> None:
        from apps.ai.application.approval_service import AIToolApprovalService

        await AIToolApprovalService(self.session).cancel_execution(execution.id)
        now = get_datetime_utc()
        execution.status = "TIMED_OUT" if timed_out else "FAILED"
        execution.last_error_code = code
        execution.ended_at = now
        if attempt is not None:
            attempt.status = "TIMED_OUT" if timed_out else "FAILED"
            attempt.error_code = code
            attempt.error_details = {"code": code}
            attempt.ended_at = now
        token.status = "FAILED"
        process.status = "FAILED"
        process.last_error_code = code
        process.ended_at = now
        process.updated_at = now
        request, _ = await self._request_context(process)
        if process.parent_step_execution_id is None:
            request.status = "FAILED"
            request.closed_at = now
            request.updated_at = now
        await self.session.flush()
        events = ProcessEventService(self.session)
        await events.append(
            process.id,
            "step.timed_out" if timed_out else "step.failed",
            actor_user_id=actor_user_id,
            step_execution_id=execution.id,
            payload={
                "status": execution.status,
                "error_code": code,
                "attempt": attempt.number if attempt else None,
            },
        )
        await events.append(
            process.id,
            "process.failed",
            actor_user_id=actor_user_id,
            step_execution_id=execution.id,
            payload={"status": process.status, "error_code": code},
        )
        await self._stage_subprocess_result(process)

    async def _stage_subprocess_result(self, process: ProcessInstanceEntity) -> None:
        if process.parent_step_execution_id is None:
            return
        from apps.tasks.application.outbox import enqueue_task
        from core.settings import settings

        enqueue_task(
            self.session,
            "bpms.settle_subprocess",
            kwargs={"child_id": str(process.id)},
            task_id=str(process.id),
            idempotency_key=f"subprocess-result:{process.id}",
            queue=settings.CELERY_AUTOMATION_QUEUE,
        )

    async def _complete(
        self,
        process: ProcessInstanceEntity,
        token: ExecutionTokenEntity,
        request: BusinessRequestEntity,
    ) -> None:
        now = get_datetime_utc()
        token.status = "COMPLETED"
        token.current_step_id = None
        process.status = "COMPLETED"
        process.ended_at = now
        process.updated_at = now
        if process.parent_step_execution_id is None:
            request.status = "COMPLETED"
            request.closed_at = now
            request.updated_at = now
        await ProcessEventService(self.session).append(
            process.id, "process.completed", payload={"status": process.status}
        )
        await self._stage_subprocess_result(process)

    async def _request_context(
        self, process: ProcessInstanceEntity
    ) -> tuple[BusinessRequestEntity, FormSubmissionEntity]:
        request_id = process.business_request_id
        request = await self.session.get(BusinessRequestEntity, request_id)
        submission = (
            await self.session.exec(
                select(FormSubmissionEntity).where(
                    FormSubmissionEntity.business_request_id == request_id,
                    col(FormSubmissionEntity.step_execution_id).is_(None),
                )
            )
        ).one_or_none()
        if request is None or submission is None:
            raise NotFoundException("Request context not found")
        if process.parent_step_execution_id is not None:
            submission = submission.model_copy(update={"data": process.input_context or {}})
        return request, submission

    @staticmethod
    def _pointer(value: Any, pointer: str) -> Any:
        if not pointer.startswith("/"):
            raise ValueError("JSON Pointer must be absolute")
        current = value
        for raw in pointer[1:].split("/"):
            key = raw.replace("~1", "/").replace("~0", "~")
            current = current[int(key)] if isinstance(current, list) else current[key]
        return current

    @classmethod
    def _schema(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {"type": "null"}
        if isinstance(value, bool):
            return {"type": "boolean"}
        if isinstance(value, int):
            return {"type": "integer"}
        if isinstance(value, float):
            return {"type": "number"}
        if isinstance(value, str):
            return {"type": "string"}
        if isinstance(value, list):
            return {"type": "array", "items": cls._schema(value[0]) if value else {}}
        if isinstance(value, dict):
            return {
                "type": "object",
                "properties": {key: cls._schema(item) for key, item in value.items()},
            }
        return {}
