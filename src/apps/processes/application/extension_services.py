"""Scoped application capabilities for one trusted step attempt."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from anyio import fail_after, to_thread
from pydantic_ai.exceptions import UsageLimitExceeded
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.agent_service import AIAgentService
from apps.ai.application.budget_service import AIBudgetService
from apps.ai.application.decision import pinned_decision, run_decision
from apps.ai.application.errors import AIBudgetExhausted
from apps.ai.application.providers import close_model, create_model
from apps.ai.domain.entity import AIReservationEntity, AITaskBudgetEntity
from apps.integrations.application.providers import ConnectionProvider, StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.contracts import ConnectionPin
from apps.processes.domain.automation import AutomationSnapshot
from apps.processes.domain.entity import ProcessInstanceEntity
from apps.requests.domain.entity import BusinessRequestEntity
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, VersionConflictException


class ProcessStepServices:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        process_id: UUID,
        request_id: UUID,
        connection_pin: ConnectionPin | None = None,
        provider: ConnectionProvider | None = None,
        ai_snapshot: AutomationSnapshot | None = None,
    ) -> None:
        self.session = session
        self.actor_id = actor_id
        self.process_id = process_id
        self.request_id = request_id
        self.connection_pin = connection_pin
        self.provider = provider
        self.ai_snapshot = ai_snapshot

    async def request_priority(self) -> int:
        process = await self.session.get(ProcessInstanceEntity, self.process_id)
        if process is None or process.business_request_id != self.request_id:
            raise VersionConflictException("Step request scope is unavailable")
        request = await self.session.get(BusinessRequestEntity, self.request_id)
        if request is None:
            raise VersionConflictException("Step request is unavailable")
        return request.priority

    async def has_permission(self, permission: str) -> bool:
        actor = await self.session.get(UserEntity, self.actor_id)
        if actor is None or actor.deleted_at is not None:
            raise NotAllowedException("Step execution principal is unavailable")
        permissions = await user_permissions(actor, self.session)
        return "*" in permissions or permission in permissions

    async def connection_status(self) -> int:
        if self.connection_pin is None or self.provider is None:
            raise NotAllowedException("No connection was pinned for this step")
        actor = await self.session.get(UserEntity, self.actor_id)
        if actor is None or actor.deleted_at is not None:
            raise NotAllowedException("Step execution principal is unavailable")
        result = await ConnectionService(self.session, self.provider).execute(
            self.connection_pin, actor
        )
        return result.status_code

    async def ai_decision(
        self, agent_ref: str, execution_id: UUID, attempt_id: UUID, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Reserve once before network dispatch and keep uncertain charges held."""
        snapshot = self.ai_snapshot
        if (
            snapshot is None
            or snapshot.ai_agent_ref != agent_ref
            or snapshot.ai_decision is None
            or snapshot.connection is None
            or not isinstance(self.provider, StatusProvider)
        ):
            raise VersionConflictException("AI execution pin is unavailable")
        actor = await self.session.get(UserEntity, self.actor_id)
        if actor is None or actor.deleted_at is not None:
            raise NotAllowedException("AI execution principal is unavailable")
        agent, spec = await AIAgentService(self.session).published(agent_ref, actor)
        if agent.checksum != snapshot.ai_agent_checksum:
            raise VersionConflictException("AI agent pin changed")
        contract, permitted = pinned_decision(spec, data)
        if contract.schema_hash != snapshot.ai_decision.schema_hash:
            raise VersionConflictException("AI decision options changed after dispatch")
        connection = await ConnectionService(self.session, self.provider).recheck_ai(
            snapshot.connection, spec.model_id, actor
        )
        credential = await to_thread.run_sync(
            self.provider.secrets.resolve,
            snapshot.connection.secret_ref,
            snapshot.connection.secret_version,
        )
        endpoint = (
            self.provider.endpoints[connection.endpoint_key]
            if connection.endpoint_key != "hosted"
            else None
        )
        model = create_model(
            spec.provider_key,
            spec.model_id,
            credential.get_secret_value(),
            endpoint=endpoint,
            region=connection.region,
            account=connection.account,
        )
        budget = (
            await self.session.exec(
                select(AITaskBudgetEntity).where(
                    AITaskBudgetEntity.step_execution_id == execution_id
                )
            )
        ).one_or_none()
        if budget is None:
            raise VersionConflictException("AI task budget was not staged")
        if spec.data_policy.allowed_tools:
            from apps.ai.application.tool_runtime import execute_tool_decision

            return await execute_tool_decision(
                self.session,
                actor=actor,
                attempt_id=attempt_id,
                budget=budget,
                spec=spec,
                contract=contract,
                permitted=permitted,
                model=model,
            )
        upper = spec.price.upper(spec.effective_limits)
        key = str(attempt_id)
        # A prior reservation may represent a network call whose outcome is unknown.
        async with SessionFactory() as budget_session, budget_session.begin():
            prior = (
                await budget_session.exec(
                    select(AIReservationEntity).where(
                        AIReservationEntity.task_budget_id == budget.id,
                        AIReservationEntity.reservation_key == key,
                    )
                )
            ).one_or_none()
            if prior is not None:
                raise VersionConflictException("AI attempt was already dispatched")
            await AIBudgetService(budget_session).reserve(
                budget.id, key, upper, allow_existing=False
            )
        try:
            deadline = budget.created_at + timedelta(seconds=spec.effective_limits.elapsed_seconds)
            with fail_after(max(0, (deadline - get_datetime_utc()).total_seconds())):
                result = await run_decision(spec, contract, permitted, model)
        except BaseException as exc:
            async with SessionFactory() as budget_session, budget_session.begin():
                await AIBudgetService(budget_session).settle(budget.id, key, None)
            if isinstance(exc, TimeoutError | UsageLimitExceeded):
                raise AIBudgetExhausted("AI task execution budget exhausted") from None
            raise
        finally:
            await close_model(model)
        async with SessionFactory() as budget_session, budget_session.begin():
            await AIBudgetService(budget_session).settle(
                budget.id, key, result.usage, model_used=result.model_used
            )
        return result.decision.model_dump(mode="json")
