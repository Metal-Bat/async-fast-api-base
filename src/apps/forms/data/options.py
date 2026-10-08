"""Current, actor-visible UMS choices; never trust a previously displayed key."""

from typing import Literal
from uuid import UUID

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from core.ref_id import create_ref_id, open_ref_id


class DomainOptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def choices(
        self,
        selector: Literal["users", "work_groups"],
        actor_id: UUID,
        managed: bool,
        *,
        group_ref: str | None = None,
        search: str | None = None,
        selected: list[str] | None = None,
        page: int = 1,
        size: int = 100,
    ) -> tuple[list[tuple[str, str]], int]:
        model = UserEntity if selector == "users" else WorkGroupEntity
        label = col(UserEntity.username) if selector == "users" else col(WorkGroupEntity.name)
        statement = select(model).where(col(model.deleted_at).is_(None))
        if selector == "work_groups":
            statement = statement.where(col(WorkGroupEntity.is_active).is_(True))
            if not managed:
                statement = statement.where(
                    col(WorkGroupEntity.id).in_(
                        select(WorkGroupMemberEntity.work_group_id).where(
                            WorkGroupMemberEntity.user_id == actor_id,
                            col(WorkGroupMemberEntity.is_active).is_(True),
                        )
                    )
                )
        elif bool(group_ref):
            try:
                group_id, version = open_ref_id(group_ref)
            except TypeError, ValueError:
                return [], 0
            group = await self.session.get(WorkGroupEntity, group_id, populate_existing=True)
            if group is None or group.deleted_at or not group.is_active or group.version != version:
                return [], 0
            membership = await self.session.get(
                WorkGroupMemberEntity, (group_id, actor_id), populate_existing=True
            )
            if not managed and (membership is None or not membership.is_active):
                return [], 0
            statement = statement.where(
                col(UserEntity.id).in_(
                    select(WorkGroupMemberEntity.user_id).where(
                        WorkGroupMemberEntity.work_group_id == group_id,
                        col(WorkGroupMemberEntity.is_active).is_(True),
                    )
                )
            )
        elif not managed:
            statement = statement.where(UserEntity.id == actor_id)
        if bool(search):
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            statement = statement.where(label.ilike("%" + escaped + "%", escape="\\"))
        requested: dict[UUID, set[int]] = {}
        if selected is not None:
            for ref in selected:
                try:
                    identifier, version = open_ref_id(ref)
                    requested.setdefault(identifier, set()).add(version)
                except ValueError, TypeError:
                    continue
            if not requested:
                return [], 0
            statement = statement.where(col(model.id).in_(requested))
        # Current revisions are filtered in SQL, before count/pagination.
        if requested:
            from sqlalchemy import or_

            statement = statement.where(
                or_(
                    *(
                        (col(model.id) == identifier) & col(model.version).in_(versions)
                        for identifier, versions in requested.items()
                    )
                )
            )
        total = (
            await self.session.exec(select(func.count()).select_from(statement.subquery()))
        ).one()
        rows = (
            await self.session.exec(
                statement.order_by(label, col(model.id)).offset((page - 1) * size).limit(size)
            )
        ).all()
        return [
            (
                create_ref_id(row.id, row.version),
                row.username if isinstance(row, UserEntity) else row.name,
            )
            for row in rows
        ], total
