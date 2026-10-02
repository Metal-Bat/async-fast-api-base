"""Reserve and fence both model calls around a durable human tool approval."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from anyio import fail_after
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models import Model
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.approval_service import (
    AIExecutionDeferred,
    AIToolApprovalService,
    checkpoint_codec,
)
from apps.ai.application.budget_service import AIBudgetService
from apps.ai.application.deferred_decision import (
    AIDeferredResult,
    begin_tool_decision,
    resume_tool_decision,
)
from apps.ai.application.errors import AIBudgetExhausted
from apps.ai.application.providers import close_model
from apps.ai.application.query_lookup import AIQueryContext
from apps.ai.domain.agent import AIAgentPublishedSpec
from apps.ai.domain.contracts import AIDecisionContract, AITaskLimits
from apps.ai.domain.entity import AIReservationEntity, AITaskBudgetEntity
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory
from utils.date_utils import get_datetime_utc
from utils.exceptions import VersionConflictException


async def execute_tool_decision(
    session: AsyncSession,
    *,
    actor: UserEntity,
    attempt_id: UUID,
    budget: AITaskBudgetEntity,
    spec: AIAgentPublishedSpec,
    contract: AIDecisionContract,
    permitted: dict[str, Any],
    model: Model,
) -> dict[str, Any]:
    try:
        return await _execute(
            session,
            actor=actor,
            attempt_id=attempt_id,
            budget=budget,
            spec=spec,
            contract=contract,
            permitted=permitted,
            model=model,
        )
    finally:
        await close_model(model)


async def _execute(
    session: AsyncSession,
    *,
    actor: UserEntity,
    attempt_id: UUID,
    budget: AITaskBudgetEntity,
    spec: AIAgentPublishedSpec,
    contract: AIDecisionContract,
    permitted: dict[str, Any],
    model: Model,
) -> dict[str, Any]:
    checkpoint_codec()
    deadline = budget.created_at + timedelta(seconds=spec.effective_limits.elapsed_seconds)
    checkpoint = None
    async with SessionFactory() as dispatch, dispatch.begin():
        # Serialize initial and resumed dispatch before reading either fence. The
        # lock is released before network I/O; duplicate deliveries then observe
        # the committed reservation instead of failing the live attempt.
        await dispatch.get(AITaskBudgetEntity, budget.id, with_for_update=True)
        approvals = AIToolApprovalService(dispatch)
        approval = await approvals.for_attempt(attempt_id)
        if approval is not None and approval.status == "PENDING":
            raise AIExecutionDeferred("waiting_approval")
        if approval is not None and approval.status == "CONSUMED":
            raise AIExecutionDeferred("already_dispatched")
        if approval is not None and approval.status != "APPROVED":
            raise VersionConflictException("AI approval is not executable")
        key = f"{attempt_id}:tool" if approval else str(attempt_id)
        prior = (
            await dispatch.exec(
                select(AIReservationEntity).where(
                    AIReservationEntity.task_budget_id == budget.id,
                    AIReservationEntity.reservation_key == key,
                )
            )
        ).one_or_none()
        if prior is not None:
            raise AIExecutionDeferred("already_dispatched")
        if approval is not None:
            checkpoint = await approvals.consume(attempt_id, actor)
            used = checkpoint.usage
            if any(
                getattr(used, name) >= getattr(spec.effective_limits, name)
                for name in (
                    "requests",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "spend_usd",
                )
            ):
                raise AIBudgetExhausted("AI task has no budget remaining for tool resume")
            limits = AITaskLimits.model_validate(
                spec.effective_limits.model_dump()
                | {
                    "requests": spec.effective_limits.requests - used.requests,
                    "input_tokens": spec.effective_limits.input_tokens - used.input_tokens,
                    "output_tokens": spec.effective_limits.output_tokens - used.output_tokens,
                    "total_tokens": spec.effective_limits.total_tokens - used.total_tokens,
                    "spend_usd": spec.effective_limits.spend_usd - used.spend_usd,
                }
            )
        else:
            limits = spec.effective_limits
        upper = spec.price.upper(limits).model_copy(update={"tool_calls": 1 if checkpoint else 0})
        await AIBudgetService(dispatch).reserve(budget.id, key, upper, allow_existing=False)
    try:
        remaining_seconds = (deadline - get_datetime_utc()).total_seconds()
        with fail_after(max(0, remaining_seconds)):
            if checkpoint is None:
                result = await begin_tool_decision(
                    spec, contract, permitted, model, spec.tool_versions
                )
            else:
                result = await resume_tool_decision(
                    spec,
                    contract,
                    checkpoint,
                    model,
                    spec.tool_versions,
                    deps=AIQueryContext(
                        session=session, actor_id=actor.id, policy=spec.data_policy
                    ),
                )
    except BaseException as exc:
        async with SessionFactory() as settlement, settlement.begin():
            await AIBudgetService(settlement).settle(budget.id, key, None)
        if isinstance(exc, TimeoutError | UsageLimitExceeded):
            raise AIBudgetExhausted("AI task execution budget exhausted") from None
        raise
    async with SessionFactory() as settlement, settlement.begin():
        await AIBudgetService(settlement).settle(
            budget.id, key, result.usage, model_used=result.model_used
        )
        if isinstance(result, AIDeferredResult):
            await AIToolApprovalService(settlement).stage(attempt_id, actor.id, result, deadline)
    if isinstance(result, AIDeferredResult):
        raise AIExecutionDeferred("waiting_approval")
    return result.decision.model_dump(mode="json")
