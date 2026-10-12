"""Safe, bounded projection of existing persisted AI attempts and budgets."""

from uuid import UUID

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.budget_service import AIBudgetService
from apps.ai.domain.agent import AIAgentPublishedSpec
from apps.ai.domain.contracts import AIDecision
from apps.ai.domain.entity import AIAgentEntity, AITaskBudgetEntity
from apps.ai.domain.evidence import AIProcessEvidenceDTO
from apps.processes.domain.automation import AutomationSnapshot
from apps.processes.domain.entity import StepExecutionAttemptEntity, StepExecutionEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.pagination import Page, PageRequest


class AIProcessEvidenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, process_id: UUID, query: PageRequest) -> Page[AIProcessEvidenceDTO]:
        """Caller must already authorize participant view access to the process."""
        latest = (
            select(func.max(StepExecutionAttemptEntity.number))
            .where(StepExecutionAttemptEntity.step_execution_id == col(StepExecutionEntity.id))
            .correlate(StepExecutionEntity)
            .scalar_subquery()
        )
        statement = (
            select(StepExecutionAttemptEntity, StepExecutionEntity)
            .join(
                StepExecutionEntity,
                col(StepExecutionEntity.id) == col(StepExecutionAttemptEntity.step_execution_id),
            )
            .where(
                StepExecutionEntity.process_instance_id == process_id,
                col(StepExecutionAttemptEntity.automation_snapshot).op("->>")("handler_key")
                == "ai_decision",
                StepExecutionAttemptEntity.number == latest,
            )
        )
        total = (
            await self.session.exec(select(func.count()).select_from(statement.subquery()))
        ).one()
        rows = (
            await self.session.exec(
                statement.order_by(col(StepExecutionEntity.created_at), col(StepExecutionEntity.id))
                .offset((query.page - 1) * query.size)
                .limit(query.size)
            )
        ).all()
        items = []
        for attempt, execution in rows:
            snapshot = AutomationSnapshot.model_validate(attempt.automation_snapshot)
            agent = (
                await self.session.get(AIAgentEntity, open_ref_id(snapshot.ai_agent_ref)[0])
                if snapshot.ai_agent_ref is not None
                else None
            )
            spec = (
                AIAgentPublishedSpec.model_validate(agent.spec)
                if agent is not None
                and agent.checksum == snapshot.ai_agent_checksum
                and agent.status in {"PUBLISHED", "RETIRED"}
                else None
            )
            budget = (
                await self.session.exec(
                    select(AITaskBudgetEntity.id).where(
                        AITaskBudgetEntity.step_execution_id == execution.id
                    )
                )
            ).one_or_none()
            items.append(
                AIProcessEvidenceDTO(
                    step_execution_ref_id=create_ref_id(execution.id, execution.version),
                    attempt_number=attempt.number,
                    status=attempt.status,
                    agent_ref_id=snapshot.ai_agent_ref,
                    agent_available=spec is not None,
                    model_id=spec.model_id if spec is not None else None,
                    allowed_input_fields=sorted(spec.data_policy.allowed_fields)
                    if spec is not None
                    else [],
                    recommendation=AIDecision.model_validate(execution.output_snapshot)
                    if execution.status == "COMPLETED" and bool(execution.output_snapshot)
                    else None,
                    budget=await AIBudgetService(self.session).status_for_execution(execution.id)
                    if budget is not None
                    else None,
                )
            )
        return Page[AIProcessEvidenceDTO](
            page=query.page, size=query.size, total=total, items=items
        )
