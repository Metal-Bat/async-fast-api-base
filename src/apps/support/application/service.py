"""Dedicated current support authority; caller owns command commit."""

from datetime import datetime

from pydantic import TypeAdapter
from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.support.domain.dto import (
    Category,
    IncidentDTO,
    IncidentHistoryDTO,
    IncidentQuery,
    IncidentState,
)
from apps.support.domain.entity import SupportIncidentEntity, SupportIncidentHistory
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from core.history import audit_context
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, NotFoundException, VersionConflictException
from utils.pagination import Page, PageRequest, paginate_entities


async def require_support(session: AsyncSession, actor: UserEntity) -> None:
    permissions = await user_permissions(actor, session)
    if "*" not in permissions and "support.incidents.manage" not in permissions:
        raise NotAllowedException()


class IncidentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def dto(row: SupportIncidentEntity) -> IncidentDTO:
        return IncidentDTO(
            ref_id=create_ref_id(row.id, row.version),
            support_ref=row.id,
            category=TypeAdapter(Category).validate_python(row.category),
            error_code=row.error_code,
            operation=row.operation,
            state=TypeAdapter(IncidentState).validate_python(row.state),
            occurrence_count=row.occurrence_count,
            first_seen_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
        )

    async def get(
        self, ref_id: str, actor: UserEntity, *, write: bool = False
    ) -> SupportIncidentEntity:
        await require_support(self.session, actor)
        identity, version = open_ref_id(ref_id)
        row = await self.session.get(
            SupportIncidentEntity, identity, populate_existing=True, with_for_update=write
        )
        if row is None or row.deleted_at is not None or row.expires_at <= get_datetime_utc():
            raise NotFoundException()
        if write and row.version != version:
            raise VersionConflictException()
        return row

    async def search(self, query: IncidentQuery, actor: UserEntity) -> Page[IncidentDTO]:
        await require_support(self.session, actor)
        page = await paginate_entities(
            self.session,
            SupportIncidentEntity,
            query,
            criteria=(col(SupportIncidentEntity.expires_at) > get_datetime_utc(),),
            default_ordering=("-last_seen_at", "id"),
        )
        return Page(
            items=[self.dto(row) for row in page.items],
            total=page.total,
            page=page.page,
            size=page.size,
        )

    async def transition(self, ref_id: str, actor: UserEntity, state: str) -> IncidentDTO:
        row = await self.get(ref_id, actor, write=True)
        if row.state == "RESOLVED" or (state == "ACKNOWLEDGED" and row.state != "OPEN"):
            raise VersionConflictException()
        row.state = state
        row.updated_at = get_datetime_utc()
        with audit_context(modifier_type="user", modifier_id=str(actor.id), reason=None):
            self.session.add(row)
            await self.session.flush()
        return self.dto(row)

    async def history(
        self, ref_id: str, actor: UserEntity, query: PageRequest
    ) -> Page[IncidentHistoryDTO]:
        row = await self.get(ref_id, actor)
        statement = (
            select(
                SupportIncidentHistory.c.CHANGED_AT,
                SupportIncidentHistory.c.OPERATION,
                SupportIncidentHistory.c.FROM_STATE,
                SupportIncidentHistory.c.TO_STATE,
            )
            .where(SupportIncidentHistory.c.ENTITY_ID == row.id)
            .order_by(SupportIncidentHistory.c.CHANGED_AT, SupportIncidentHistory.c.ID)
            .limit(1001)
        )
        records = (await self.session.exec(statement)).all()
        from utils.pagination import paginate_values

        if len(records) > 1000:
            raise VersionConflictException("History exceeds bounded projection")
        return paginate_values(
            [
                IncidentHistoryDTO(
                    changed_at=item[0],
                    operation=item[1],
                    from_state=item[2],
                    to_state=item[3],
                )
                for item in records
            ],
            query,
        )


async def prune_incidents(session: AsyncSession, now: datetime | None = None) -> int:
    """Purge at most 100 expired episodes per existing maintenance invocation, including audit."""
    now = now or get_datetime_utc()
    ids = (
        await session.exec(
            select(SupportIncidentEntity.id)
            .where(col(SupportIncidentEntity.expires_at) <= now)
            .order_by(col(SupportIncidentEntity.expires_at))
            .limit(100)
            .with_for_update(skip_locked=True)
        )
    ).all()
    if ids:
        await session.exec(
            delete(SupportIncidentEntity).where(col(SupportIncidentEntity.id).in_(ids))
        )
    return len(ids)
