"""Work-group CRUD and membership decisions."""

from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.users.domain.auth_entity import AuthAuditEventEntity
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.dto import WorkGroupCreateDTO, WorkGroupUpdateDTO
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from core.ref_id import open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException


class WorkGroupService:
    """Own group state changes; callers commit the containing transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_group(self, ref_id: str, *, include_deleted: bool = False) -> WorkGroupEntity:
        group_id, _ = open_ref_id(ref_id)
        group = await self.session.get(WorkGroupEntity, group_id)
        if group is None or (group.deleted_at is not None and not include_deleted):
            raise NotFoundException("Work group not found")
        return group

    async def create_group(self, data: WorkGroupCreateDTO, actor_id: UUID) -> WorkGroupEntity:
        group = WorkGroupEntity(**data.model_dump())
        self.session.add(group)
        self.session.add(AuthAuditEventEntity(user_id=actor_id, event_type="work_group.created"))
        await self.session.flush()
        return group

    async def update_group(self, ref_id: str, **values: object) -> WorkGroupEntity:
        group = await self.get_group(ref_id)
        self._check_version(ref_id, group)
        group.sqlmodel_update(values)
        group.updated_at = get_datetime_utc()
        self.session.add(group)
        try:
            await self.session.flush()
        except StaleDataError as exc:
            raise VersionConflictException("Work group version is stale") from exc
        return group

    async def replace_group(
        self, ref_id: str, data: WorkGroupUpdateDTO, actor_id: UUID
    ) -> WorkGroupEntity:
        group = await self.update_group(ref_id, **data.model_dump())
        self.session.add(
            AuthAuditEventEntity(
                user_id=actor_id,
                event_type="work_group.updated",
                details={"work_group_id": str(group.id)},
            )
        )
        return group

    async def delete_group(self, ref_id: str, actor_id: UUID) -> None:
        group = await self.get_group(ref_id)
        self._check_version(ref_id, group)
        group.deleted_at = get_datetime_utc()
        group.is_active = False
        self.session.add_all(
            [
                group,
                AuthAuditEventEntity(
                    user_id=actor_id,
                    event_type="work_group.deleted",
                    details={"work_group_id": str(group.id)},
                ),
            ]
        )
        await self.session.flush()

    async def add_member(
        self, group_ref_id: str, user_id: UUID, *, actor_id: UUID | None = None
    ) -> WorkGroupMemberEntity:
        group = await self.get_group(group_ref_id)
        if not group.is_active:
            raise VersionConflictException("Work group is inactive")
        user = await self.session.get(UserEntity, user_id)
        if user is None or user.deleted_at is not None:
            raise NotFoundException("Active user not found")
        key = (group.id, user_id)
        membership = await self.session.get(WorkGroupMemberEntity, key)
        if membership is None:
            inserted = (
                await self.session.exec(
                    insert(WorkGroupMemberEntity)
                    .values(
                        WORK_GROUP_ID=group.id,
                        USER_ID=user_id,
                        IS_ACTIVE=True,
                        JOINED_AT=get_datetime_utc(),
                        ADDED_BY_USER_ID=actor_id,
                    )
                    .on_conflict_do_nothing(index_elements=["WORK_GROUP_ID", "USER_ID"])
                    .returning(
                        WorkGroupMemberEntity.__table__.c.USER_ID  # ty:ignore[unresolved-attribute]
                    )
                )
            ).first()
            membership = await self.session.get(WorkGroupMemberEntity, key)
            if membership is None:
                raise RuntimeError("Inserted work-group member could not be reloaded")
            if inserted is not None:
                if actor_id is not None:
                    self._audit_member("added", actor_id, group.id, user_id)
                await self.session.flush()
                return membership
        if not membership.is_active:
            membership.is_active = True
            membership.left_at = None
            membership.joined_at = get_datetime_utc()
            membership.updated_at = membership.joined_at
            self.session.add(membership)
            if actor_id is not None:
                self._audit_member("added", actor_id, group.id, user_id)
            await self.session.flush()
        return membership

    async def deactivate_member(
        self, group_ref_id: str, user_id: UUID, *, actor_id: UUID
    ) -> WorkGroupMemberEntity:
        group = await self.get_group(group_ref_id)
        member = await self.session.get(WorkGroupMemberEntity, (group.id, user_id))
        if member is None:
            raise NotFoundException("Work group member not found")
        if member.is_active:
            member.is_active = False
            member.left_at = get_datetime_utc()
            member.updated_at = member.left_at
            self.session.add(member)
            self._audit_member("deactivated", actor_id, group.id, user_id)
            await self.session.flush()
        return member

    async def remove_member(self, group_ref_id: str, user_id: UUID, *, actor_id: UUID) -> None:
        group = await self.get_group(group_ref_id)
        member = await self.session.get(WorkGroupMemberEntity, (group.id, user_id))
        if member is None:
            return
        await self.session.delete(member)
        self._audit_member("removed", actor_id, group.id, user_id)
        await self.session.flush()

    async def is_active_member(self, user_id: UUID, group_id: UUID) -> bool:
        statement = (
            select(WorkGroupMemberEntity.user_id)
            .join(
                WorkGroupEntity, col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id)
            )
            .join(UserEntity, col(UserEntity.id) == col(WorkGroupMemberEntity.user_id))
            .where(
                col(WorkGroupMemberEntity.user_id) == user_id,
                col(WorkGroupMemberEntity.work_group_id) == group_id,
                col(WorkGroupMemberEntity.is_active).is_(True),
                col(WorkGroupEntity.is_active).is_(True),
                col(WorkGroupEntity.deleted_at).is_(None),
                col(UserEntity.deleted_at).is_(None),
            )
        )
        return (await self.session.exec(statement)).first() is not None

    @staticmethod
    def _check_version(ref_id: str, group: WorkGroupEntity) -> None:
        if group.version != open_ref_id(ref_id)[1]:
            raise VersionConflictException("Work group version is stale")

    def _audit_member(self, action: str, actor_id: UUID, group_id: UUID, user_id: UUID) -> None:
        self.session.add(
            AuthAuditEventEntity(
                user_id=actor_id,
                event_type=f"work_group.member_{action}",
                details={"work_group_id": str(group_id), "user_id": str(user_id)},
            )
        )
