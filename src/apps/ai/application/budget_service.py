"""Serialize AI dispatch reservations against one persisted logical-task budget."""

from datetime import timedelta
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.errors import AIBudgetExhausted
from apps.ai.domain.budget import AIBudgetStatus, BudgetAmounts, BudgetLedger
from apps.ai.domain.contracts import AITaskLimits
from apps.ai.domain.entity import AIReservationEntity, AITaskBudgetEntity
from utils.date_utils import get_datetime_utc
from utils.exceptions import VersionConflictException


class AIBudgetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, execution_id: UUID, limits: AITaskLimits, *, price_version: str
    ) -> AITaskBudgetEntity:
        if not price_version or len(price_version) > 128:
            raise ValueError("A pinned price source/version is required")
        row = AITaskBudgetEntity(
            step_execution_id=execution_id,
            effective_limits=limits.model_dump(mode="json"),
            used=BudgetAmounts().model_dump(mode="json"),
            reserved=BudgetAmounts().model_dump(mode="json"),
            price_version=price_version,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def reserve(
        self, budget_id: UUID, key: str, upper: BudgetAmounts, *, allow_existing: bool = True
    ) -> AIReservationEntity:
        if not key or len(key) > 128:
            raise ValueError("A stable reservation key is required")
        row = await self._lock(budget_id)
        existing = (
            await self.session.exec(
                select(AIReservationEntity).where(
                    AIReservationEntity.task_budget_id == budget_id,
                    AIReservationEntity.reservation_key == key,
                )
            )
        ).one_or_none()
        if existing is not None:
            if not allow_existing:
                raise VersionConflictException("AI attempt was already dispatched")
            if existing.upper != upper.model_dump(mode="json"):
                raise VersionConflictException("Reservation key was reused with another bound")
            return existing
        limits = AITaskLimits.model_validate(row.effective_limits)
        if get_datetime_utc() >= row.created_at + timedelta(seconds=limits.elapsed_seconds):
            raise AIBudgetExhausted("AI task elapsed-time budget exhausted")
        ledger = self._ledger(row)
        try:
            ledger.reserve(upper)
        except ValueError:
            raise AIBudgetExhausted("AI task budget exhausted") from None
        row.reserved = ledger.reserved.model_dump(mode="json")
        row.updated_at = get_datetime_utc()
        reservation = AIReservationEntity(
            task_budget_id=budget_id,
            reservation_key=key,
            upper=upper.model_dump(mode="json"),
        )
        self.session.add(reservation)
        await self.session.flush()
        return reservation

    async def settle(
        self,
        budget_id: UUID,
        key: str,
        actual: BudgetAmounts | None,
        *,
        model_used: str | None = None,
    ) -> AIReservationEntity:
        row = await self._lock(budget_id)
        reservation = await self._reservation(budget_id, key)
        if reservation.status == "SETTLED":
            if reservation.actual != (actual.model_dump(mode="json") if actual else None) or (
                model_used is not None and reservation.model_used != model_used
            ):
                raise VersionConflictException("Reservation settlement changed")
            return reservation
        if reservation.status != "RESERVED":
            raise VersionConflictException("Reservation is no longer dispatchable")
        if actual is None:
            reservation.status = "UNKNOWN"
        else:
            ledger = self._ledger(row)
            ledger.settle(BudgetAmounts.model_validate(reservation.upper), actual)
            row.used = ledger.used.model_dump(mode="json")
            row.reserved = ledger.reserved.model_dump(mode="json")
            reservation.actual = actual.model_dump(mode="json")
            reservation.model_used = model_used
            reservation.status = "SETTLED"
        row.updated_at = get_datetime_utc()
        reservation.updated_at = row.updated_at
        await self.session.flush()
        return reservation

    async def not_dispatched(self, budget_id: UUID, key: str) -> AIReservationEntity:
        """Release a hold only after a definitive before-network failure."""
        row = await self._lock(budget_id)
        reservation = await self._reservation(budget_id, key)
        if reservation.status != "RESERVED":
            raise VersionConflictException("Reservation is no longer dispatchable")
        ledger = self._ledger(row)
        ledger.reserved -= BudgetAmounts.model_validate(reservation.upper)
        row.reserved = ledger.reserved.model_dump(mode="json")
        reservation.status = "NOT_DISPATCHED"
        row.updated_at = reservation.updated_at = get_datetime_utc()
        await self.session.flush()
        return reservation

    async def status_for_execution(self, execution_id: UUID) -> AIBudgetStatus:
        row = (
            await self.session.exec(
                select(AITaskBudgetEntity).where(
                    AITaskBudgetEntity.step_execution_id == execution_id
                )
            )
        ).one_or_none()
        if row is None:
            raise VersionConflictException("AI task budget is unavailable")
        unknown = (
            await self.session.exec(
                select(AIReservationEntity.id).where(
                    AIReservationEntity.task_budget_id == row.id,
                    AIReservationEntity.status == "UNKNOWN",
                )
            )
        ).first() is not None
        ledger = self._ledger(row)
        return AIBudgetStatus(
            effective_limits=ledger.limits,
            used=ledger.used,
            reserved=ledger.reserved,
            remaining=ledger.remaining(),
            currency=row.currency,
            price_version=row.price_version,
            unknown_usage=unknown,
        )

    async def _lock(self, budget_id: UUID) -> AITaskBudgetEntity:
        row = await self.session.get(
            AITaskBudgetEntity, budget_id, with_for_update=True, populate_existing=True
        )
        if row is None:
            raise VersionConflictException("AI task budget is unavailable")
        return row

    async def _reservation(self, budget_id: UUID, key: str) -> AIReservationEntity:
        row = (
            await self.session.exec(
                select(AIReservationEntity).where(
                    AIReservationEntity.task_budget_id == budget_id,
                    AIReservationEntity.reservation_key == key,
                )
            )
        ).one_or_none()
        if row is None:
            raise VersionConflictException("AI reservation is unavailable")
        return row

    @staticmethod
    def _ledger(row: AITaskBudgetEntity) -> BudgetLedger:
        return BudgetLedger(
            limits=AITaskLimits.model_validate(row.effective_limits),
            used=BudgetAmounts.model_validate(row.used),
            reserved=BudgetAmounts.model_validate(row.reserved),
        )
