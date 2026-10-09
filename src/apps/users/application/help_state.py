"""Persist explicit self acknowledgment only; release metadata grants no business access."""

from pydantic import TypeAdapter
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.users.domain.entity import UserEntity
from apps.users.domain.help_entity import HelpStateEntity
from apps.users.domain.help_state import (
    HelpAction,
    HelpActionResult,
    HelpReleaseMetadata,
    HelpResetResult,
    HelpStateDTO,
    HelpStatePage,
    HelpStateQuery,
)
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException
from utils.pagination import Page

MAX_HELP_STATE_RECORDS = 512


class HelpStateService:
    """Callers commit; this compact table contains no help content, payloads or durations."""

    def __init__(self, session: AsyncSession, metadata: HelpReleaseMetadata | None) -> None:
        self.session = session
        self.metadata = metadata

    async def _active(self, actor: UserEntity, *, lock: bool = False) -> UserEntity:
        user = await self.session.get(
            UserEntity, actor.id, with_for_update=lock, populate_existing=True
        )
        if user is None or user.deleted_at is not None:
            raise NotFoundException("Active self profile not found")
        return user

    async def read(self, actor: UserEntity, query: HelpStateQuery) -> HelpStatePage:
        """A list retrieval never acknowledges content or updates a timestamp."""
        user = await self._active(actor)
        statement = select(HelpStateEntity).where(HelpStateEntity.user_id == user.id)
        if query.locale is not None:
            statement = statement.where(HelpStateEntity.locale == query.locale)
        total = (
            await self.session.exec(select(func.count()).select_from(statement.subquery()))
        ).one()
        rows = (
            await self.session.exec(
                statement.order_by(
                    col(HelpStateEntity.help_key),
                    col(HelpStateEntity.revision),
                    col(HelpStateEntity.locale),
                )
                .offset((query.page - 1) * query.size)
                .limit(query.size)
            )
        ).all()
        return HelpStatePage(
            release_key=self.metadata.release_key if self.metadata else None,
            states=Page(
                items=TypeAdapter(list[HelpStateDTO]).validate_python(rows, from_attributes=True),
                total=total,
                page=query.page,
                size=query.size,
            ),
        )

    def _compatibility(self, action: HelpAction) -> HelpActionResult | None:
        if self.metadata is None:
            return HelpActionResult(saved=False, reason="manifest_unavailable")
        item = next(
            (item for item in self.metadata.items if item.help_key == action.help_key), None
        )
        if item is None:
            return HelpActionResult(saved=False, reason="unknown_key")
        if item.revision != action.revision:
            return HelpActionResult(saved=False, reason="stale_revision")
        if action.locale not in item.locales:
            return HelpActionResult(saved=False, reason="unsupported_locale")
        return None

    async def record(
        self, actor: UserEntity, action: HelpAction, *, dismiss: bool = False
    ) -> HelpActionResult:
        """Use an atomic tuple upsert; repeats preserve first-open/first-dismiss timestamps."""
        incompatible = self._compatibility(action)
        if incompatible is not None:
            return incompatible
        user = await self._active(actor, lock=True)
        key = (user.id, action.help_key, action.revision, action.locale)
        existing = await self.session.get(HelpStateEntity, key)
        if existing is None:
            total = (
                await self.session.exec(
                    select(func.count())
                    .select_from(HelpStateEntity)
                    .where(HelpStateEntity.user_id == user.id)
                )
            ).one()
            if total >= MAX_HELP_STATE_RECORDS:
                return HelpActionResult(saved=False, reason="state_limit")
        now = get_datetime_utc()
        updates = (
            {"DISMISSED_AT": func.coalesce(HelpStateEntity.dismissed_at, now)}
            if dismiss
            else {
                "FIRST_VIEWED_AT": func.coalesce(HelpStateEntity.first_viewed_at, now),
                "LAST_VIEWED_AT": func.greatest(HelpStateEntity.last_viewed_at, now),
            }
        )
        await self.session.exec(
            insert(HelpStateEntity)
            .values(
                USER_ID=user.id,
                HELP_KEY=action.help_key,
                REVISION=action.revision,
                LOCALE=action.locale,
                FIRST_VIEWED_AT=None if dismiss else now,
                LAST_VIEWED_AT=None if dismiss else now,
                DISMISSED_AT=now if dismiss else None,
            )
            .on_conflict_do_update(
                index_elements=["USER_ID", "HELP_KEY", "REVISION", "LOCALE"], set_=updates
            )
        )
        row = await self.session.get(HelpStateEntity, key, populate_existing=True)
        if row is None:
            raise RuntimeError("Persisted help state could not be reloaded")
        return HelpActionResult(
            saved=True, reason="saved", state=HelpStateDTO.model_validate(row, from_attributes=True)
        )

    async def reset(self, actor: UserEntity) -> HelpResetResult:
        """Delete only this actor's acknowledgment metadata; repeated resets are safe."""
        user = await self._active(actor, lock=True)
        total = (
            await self.session.exec(
                select(func.count())
                .select_from(HelpStateEntity)
                .where(HelpStateEntity.user_id == user.id)
            )
        ).one()
        await self.session.exec(
            delete(HelpStateEntity).where(col(HelpStateEntity.user_id) == user.id)
        )
        return HelpResetResult(deleted_records=total)
