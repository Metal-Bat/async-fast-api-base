"""Committed human-action evidence for the protected sandbox operation."""

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.integrations.domain.orders import (
    ProtectedApprovalEvidence,
    SandboxOrderPayload,
    payload_hash,
)
from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
from apps.requests.domain.entity import FormSubmissionEntity
from apps.step_types.domain.entity import StepTypePortEntity, StepTypeVersionEntity
from apps.work_items.domain.entity import WorkItemActionEntity, WorkItemEntity
from apps.work_items.domain.task_contract import HumanTaskContract
from apps.workflows.application.protected_effects import has_approval_action
from apps.workflows.domain.entity import (
    WorkflowStepEntity,
    WorkflowStepInputBindingEntity,
    WorkflowVersionEntity,
)
from utils.exceptions import VersionConflictException


class ProtectedEffectApproval:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def capture(
        self, execution: StepExecutionEntity, step: WorkflowStepEntity
    ) -> ProtectedApprovalEvidence:
        """Fence staging/dispatch against exact process, latest visit and human action."""

        def unavailable():
            return VersionConflictException("Protected operation requires matching human approval")

        process = await self.session.get(ProcessInstanceEntity, execution.process_instance_id)
        if (
            process is None
            or process.status not in {"RUNNING", "WAITING"}
            or process.parent_step_execution_id is not None
        ):
            raise unavailable()
        version = await self.session.get(WorkflowVersionEntity, process.workflow_version_id)
        if (
            version is None
            or version.subprocess_interface is not None
            or step.workflow_version_id != version.id
            or not bool(version.graph_checksum)
        ):
            raise unavailable()
        bindings = (
            await self.session.exec(
                select(WorkflowStepInputBindingEntity).where(
                    WorkflowStepInputBindingEntity.workflow_step_id == step.id
                )
            )
        ).all()
        if len(bindings) != 1:
            raise unavailable()
        binding = bindings[0]
        target = await self.session.get(StepTypePortEntity, binding.target_port_id)
        source = (
            await self.session.get(StepTypePortEntity, binding.source_port_id)
            if binding.source_port_id
            else None
        )
        approval_step = (
            await self.session.get(WorkflowStepEntity, binding.source_step_id)
            if binding.source_step_id
            else None
        )
        handler = (
            await self.session.get(StepTypeVersionEntity, approval_step.step_type_version_id)
            if approval_step
            else None
        )
        if (
            target is None
            or target.port_key != "payload"
            or target.step_type_version_id != step.step_type_version_id
            or target.direction != "INPUT"
            or target.cardinality != "SCALAR"
            or binding.source_kind != "STEP_OUTPUT"
            or binding.ordinal != 0
            or binding.source_path is not None
            or source is None
            or source.port_key != "submission"
            or source.direction != "OUTPUT"
            or approval_step is None
            or approval_step.workflow_version_id != version.id
            or source.step_type_version_id != approval_step.step_type_version_id
            or handler is None
            or handler.handler_key != "human_task"
            or not has_approval_action(
                HumanTaskContract.model_validate(approval_step.task_contract)
                if bool(approval_step.task_contract)
                else None
            )
        ):
            raise unavailable()
        approval = (
            await self.session.exec(
                select(StepExecutionEntity)
                .where(
                    StepExecutionEntity.execution_token_id == execution.execution_token_id,
                    StepExecutionEntity.workflow_step_id == approval_step.id,
                )
                .order_by(col(StepExecutionEntity.visit_number).desc())
                .limit(1)
            )
        ).one_or_none()
        if (
            approval is None
            or approval.status != "COMPLETED"
            or approval.process_instance_id != process.id
            or not bool(approval.output_snapshot)
            or approval.output_snapshot.get("outcome") != "approve"
        ):
            raise unavailable()
        rows = (
            await self.session.exec(
                select(WorkItemEntity, WorkItemActionEntity)
                .join(
                    WorkItemActionEntity,
                    col(WorkItemActionEntity.work_item_id) == col(WorkItemEntity.id),
                )
                .where(
                    WorkItemEntity.step_execution_id == approval.id,
                    WorkItemActionEntity.action == "COMPLETE",
                    WorkItemActionEntity.outcome_key == "approve",
                )
                .limit(2)
            )
        ).all()
        if len(rows) != 1:
            raise unavailable()
        item, action = rows[0]
        submission = (
            await self.session.get(FormSubmissionEntity, action.form_submission_id)
            if action.form_submission_id
            else None
        )
        payload = (execution.input_snapshot or {}).get("payload")
        SandboxOrderPayload.model_validate(payload)
        digest = payload_hash(payload)
        if (
            item.status != "COMPLETED"
            or action.actor_user_id is None
            or action.actor_user_id != item.claimed_by_user_id
            or submission is None
            or submission.status != "SUBMITTED"
            or submission.submitted_by_user_id != action.actor_user_id
            or digest != payload_hash(submission.data)
            or digest != payload_hash(approval.output_snapshot.get("submission"))
        ):
            raise unavailable()
        recorded = action.details.get("protected_approval")
        expected = {
            "workflow_version_id": str(version.id),
            "graph_checksum": version.graph_checksum,
            "approval_step_id": str(approval_step.id),
            "payload_hash": digest,
        }
        if recorded != expected:
            raise unavailable()
        return ProtectedApprovalEvidence(
            workflow_version_id=version.id,
            graph_checksum=version.graph_checksum,
            approval_step_id=approval_step.id,
            approval_execution_id=approval.id,
            work_item_id=item.id,
            action_id=action.id,
            actor_id=action.actor_user_id,
            payload_hash=digest,
        )
