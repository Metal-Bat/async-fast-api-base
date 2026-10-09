"""One escalation per episode through the existing durable outbox, with no failure loop."""

from uuid import UUID, uuid5

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.support.domain.entity import SupportIncidentEntity
from apps.tasks.application.outbox import enqueue_task
from apps.users.domain.auth_entity import (
    PermissionEntity,
    RoleEntity,
    RolePermissionEntity,
    UserRoleEntity,
)
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory
from core.settings import settings

ALERT_TASK = "bpms.fanout_support_incident"


async def stage_incident_alert(session: AsyncSession, row: SupportIncidentEntity) -> None:
    identity = uuid5(row.id, "support-episode")
    enqueue_task(
        session,
        ALERT_TASK,
        kwargs={"incident_id": str(row.id)},
        queue=settings.CELERY_AUTOMATION_QUEUE,
        task_id=str(identity),
        idempotency_key=identity,
    )


async def fanout_incident(incident_id: UUID, after_user_id: UUID | None = None) -> int:
    from apps.notifications.application.events import stage_notice

    async with SessionFactory() as session, session.begin():
        row = await session.get(SupportIncidentEntity, incident_id, with_for_update=True)
        if row is None or row.state == "RESOLVED" or row.category == "notification":
            return 0
        authorized = (
            select(UserRoleEntity.user_id)
            .join(RoleEntity, col(RoleEntity.id) == col(UserRoleEntity.role_id))
            .join(RolePermissionEntity, col(RolePermissionEntity.role_id) == col(RoleEntity.id))
            .join(
                PermissionEntity,
                col(PermissionEntity.id) == col(RolePermissionEntity.permission_id),
            )
            .where(
                PermissionEntity.name == "support.incidents.manage",
                col(PermissionEntity.deleted_at).is_(None),
                col(RoleEntity.deleted_at).is_(None),
            )
        )
        statement = select(UserEntity).where(
            col(UserEntity.deleted_at).is_(None),
            col(UserEntity.is_superuser).is_(True) | col(UserEntity.id).in_(authorized),
        )
        if after_user_id is not None:
            statement = statement.where(col(UserEntity.id) > after_user_id)
        users = (await session.exec(statement.order_by(col(UserEntity.id)).limit(101))).all()
        for actor in users[:100]:
            await stage_notice(
                session,
                map_id="MAP-13",
                event_id=row.id,
                recipient_id=actor.id,
                target_kind="support",
                target_id=row.id,
            )
        if len(users) > 100:
            cursor = users[99].id
            identity = uuid5(row.id, "support-after:" + str(cursor))
            from apps.tasks.domain.entity import TaskOutboxEntity

            exists = (
                await session.exec(
                    select(TaskOutboxEntity).where(TaskOutboxEntity.task_id == str(identity))
                )
            ).first()
            if exists is None:
                enqueue_task(
                    session,
                    ALERT_TASK,
                    kwargs={"incident_id": str(row.id), "after_user_id": str(cursor)},
                    queue=settings.CELERY_AUTOMATION_QUEUE,
                    task_id=str(identity),
                    idempotency_key=identity,
                )
        return len(users[:100])
