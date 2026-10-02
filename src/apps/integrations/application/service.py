"""Connection authorization, metadata lifecycle, and pinned adapter execution."""

from sqlalchemy import ColumnElement
from sqlmodel import col, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.integrations.application.providers import ConnectionProvider, StatusProvider
from apps.integrations.domain.contracts import AdapterResult, ConnectionPin
from apps.integrations.domain.dto import (
    AIConnectionConfig,
    ConnectionConfig,
    ConnectionCreateDTO,
    ConnectionQuery,
    ConnectionUpdateDTO,
    GrantDTO,
    SecretRotationDTO,
)
from apps.integrations.domain.entity import IntegrationConnectionEntity as Connection
from apps.integrations.domain.entity import IntegrationConnectionGrantEntity as Grant
from apps.step_types.application.registry import get_registry
from apps.users.domain.auth_entity import AuthAuditEventEntity
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    NotAllowedException,
    NotFoundException,
    ServiceUnavailableException,
    ValidationDetailsException,
    VersionConflictException,
)
from utils.pagination import Page, paginate_entities
from utils.select import SelectOption, SelectQuery


class ConnectionService:
    def __init__(self, session: AsyncSession, provider: ConnectionProvider) -> None:
        self.session = session
        self.provider = provider

    def visible(self, actor: UserEntity, *, manage: bool = False) -> ColumnElement[bool]:
        capability = (
            col(Grant.can_manage).is_(True)
            if manage
            else or_(col(Grant.can_use).is_(True), col(Grant.can_manage).is_(True))
        )
        member = (
            select(WorkGroupMemberEntity.work_group_id)
            .join(
                WorkGroupEntity, col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id)
            )
            .where(
                WorkGroupMemberEntity.user_id == actor.id,
                col(WorkGroupMemberEntity.is_active).is_(True),
                col(WorkGroupEntity.is_active).is_(True),
                col(WorkGroupEntity.deleted_at).is_(None),
            )
        )
        grant = (
            select(Grant.id)
            .where(
                col(Grant.integration_connection_id) == col(Connection.id),
                col(Grant.deleted_at).is_(None),
                capability,
                or_(Grant.user_id == actor.id, col(Grant.work_group_id).in_(member)),
            )
            .exists()
        )
        return or_(actor.is_superuser, Connection.owner_user_id == actor.id, grant)

    async def get(
        self, ref_id: str, actor: UserEntity, *, manage: bool = False, update: bool = False
    ) -> Connection:
        if actor.deleted_at is not None:
            raise NotAllowedException("Inactive actor")
        entity_id, version = open_ref_id(ref_id)
        row = await self.session.get(
            Connection, entity_id, with_for_update=update, populate_existing=True
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Connection not found")
        allowed = (
            await self.session.exec(
                select(Connection.id).where(
                    Connection.id == entity_id, self.visible(actor, manage=manage)
                )
            )
        ).first()
        if allowed is None:
            raise NotAllowedException("Connection access denied")
        if update and row.version != version:
            raise VersionConflictException("Connection is stale")
        return row

    async def search(self, query: ConnectionQuery, actor: UserEntity) -> Page[Connection]:
        if actor.deleted_at:
            raise NotAllowedException("Inactive actor")
        return await paginate_entities(
            self.session,
            Connection,
            query,
            criteria=(self.visible(actor),),
            default_ordering=("code", "id"),
        )

    async def select_for_workflow(
        self, kind: str, query: SelectQuery, actor: UserEntity
    ) -> Page[SelectOption[str]]:
        """Return usable, verified connections that this actor may pin in a workflow."""
        if actor.deleted_at:
            raise NotAllowedException("Inactive actor")
        statement = select(Connection).where(
            col(Connection.deleted_at).is_(None),
            col(Connection.kind) == kind,
            col(Connection.status) == "ACTIVE",
            col(Connection.verification_status) == "VERIFIED",
            self.visible(actor),
        )
        if query.search:
            escaped = query.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            statement = statement.where(col(Connection.name).ilike(f"%{escaped}%", escape="\\"))
        total = (
            await self.session.exec(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
        ).one()
        rows = (
            await self.session.exec(
                statement.order_by(Connection.code, col(Connection.id))
                .offset((query.page - 1) * query.size)
                .limit(query.size)
            )
        ).all()
        return Page[SelectOption[str]](
            items=[
                SelectOption(key=create_ref_id(row.id, row.version), value=row.name) for row in rows
            ],
            page=query.page,
            size=query.size,
            total=total,
        )

    async def create(self, data: ConnectionCreateDTO, actor: UserEntity) -> Connection:
        self.provider.validate(data.provider, data.kind, data.non_secret_config)
        row = Connection(**data.model_dump(), owner_user_id=actor.id)
        self.session.add(row)
        await self.session.flush()
        self._audit(row, actor, "created")
        return row

    async def update(self, ref_id: str, data: ConnectionUpdateDTO, actor: UserEntity) -> Connection:
        row = await self.get(ref_id, actor, manage=True, update=True)
        self._not_revoked(row)
        row.sqlmodel_update(data.model_dump())
        await self._changed(row, actor, "updated")
        return row

    async def rotate(self, ref_id: str, data: SecretRotationDTO, actor: UserEntity) -> Connection:
        row = await self.get(ref_id, actor, manage=True, update=True)
        self._not_revoked(row)
        row.secret_ref, row.secret_version = data.secret_ref, data.secret_version
        row.verification_status = "UNVERIFIED"
        await self._changed(row, actor, "rotated")
        return row

    async def revoke(self, ref_id: str, actor: UserEntity) -> Connection:
        row = await self.get(ref_id, actor, manage=True, update=True)
        row.status = "REVOKED"
        await self._changed(row, actor, "revoked")
        return row

    async def delete(self, ref_id: str, actor: UserEntity) -> None:
        row = await self.revoke(ref_id, actor)
        row.deleted_at = get_datetime_utc()
        await self.session.flush()

    async def verify(self, ref_id: str, actor: UserEntity) -> Connection:
        row = await self.get(ref_id, actor, manage=True, update=True)
        self._active(row)
        try:
            if row.kind == "AI":
                config = AIConnectionConfig.model_validate(row.non_secret_config)
                self.provider.validate(row.provider, row.kind, config)
                success = (
                    await self.provider.verify_ai(self._pin(row))
                    if isinstance(self.provider, StatusProvider)
                    else False
                )
            else:
                result = await self.provider.invoke(self._pin(row))
                success = 200 <= result.status_code < 300
        except Exception:  # noqa: BLE001 -- This boundary must redact all provider exceptions.
            success = False
        row.verification_status = "VERIFIED" if success else "FAILED"
        await self._changed(row, actor, "verified" if success else "verification_failed")
        return row

    async def pin(
        self, ref_id: str, actor: UserEntity, *, handler_key: str, handler_version: str
    ) -> ConnectionPin:
        row = await self.get(ref_id, actor, update=True)
        self._active(row)
        handler = get_registry().resolve(handler_key, handler_version)
        compatible = {
            ("service_task", "SERVICE"),
            ("notification", "NOTIFICATION"),
        }
        if (handler.handler_key, row.kind) not in compatible:
            raise ValidationDetailsException(
                [{"pointer": "/connection_ref", "code": "connection.handler_incompatible"}]
            )
        self.provider.validate(
            row.provider, row.kind, ConnectionConfig.model_validate(row.non_secret_config)
        )
        if row.verification_status != "VERIFIED":
            raise VersionConflictException("Connection is not verified")
        return self._pin(row)

    async def pin_service(self, ref_id: str, actor: UserEntity) -> ConnectionPin:
        """Authorize and pin one approved SERVICE connection for trusted step code."""
        row = await self.get(ref_id, actor, update=True)
        self._active(row)
        if row.kind != "SERVICE":
            raise ValidationDetailsException(
                [{"pointer": "/connection_ref", "code": "connection.handler_incompatible"}]
            )
        self.provider.validate(
            row.provider, row.kind, ConnectionConfig.model_validate(row.non_secret_config)
        )
        if row.verification_status != "VERIFIED":
            raise VersionConflictException("Connection is not verified")
        return self._pin(row)

    async def pin_ai(
        self, ref_id: str, actor: UserEntity, model_id: str, *, lock: bool = True
    ) -> tuple[ConnectionPin, AIConnectionConfig]:
        """Authorize a configured model, optionally locking during publication/staging."""
        row = await self.get(ref_id, actor, update=lock)
        if row.version != open_ref_id(ref_id)[1]:
            raise VersionConflictException("Connection is stale")
        self._active(row)
        if row.kind != "AI":
            raise ValidationDetailsException(
                [{"pointer": "/connection_ref", "code": "connection.handler_incompatible"}]
            )
        config = AIConnectionConfig.model_validate(row.non_secret_config)
        self.provider.validate(row.provider, row.kind, config)
        if model_id not in config.models:
            raise NotAllowedException("Model is not allowed by this connection")
        if row.verification_status != "VERIFIED":
            raise VersionConflictException("AI connection is not verified")
        return self._pin(row), config

    async def recheck_ai(
        self, pin: ConnectionPin, model_id: str, actor: UserEntity
    ) -> AIConnectionConfig:
        """Recheck authorization, revocation, model and credential pin before each call."""
        row = await self.get(pin.connection_ref, actor)
        self._active(row)
        config = AIConnectionConfig.model_validate(row.non_secret_config)
        self.provider.validate(row.provider, row.kind, config)
        if (
            row.kind != "AI"
            or row.provider != pin.provider
            or config.endpoint_key != pin.endpoint_key
            or row.secret_ref != pin.secret_ref
            or row.secret_version != pin.secret_version
            or model_id not in config.models
            or row.verification_status != "VERIFIED"
        ):
            raise VersionConflictException("AI connection contract changed or was revoked")
        return config

    async def execute(self, pin: ConnectionPin, actor: UserEntity) -> AdapterResult:
        # The pin is an internal trusted execution snapshot, never an HTTP request body.
        row = await self.get(pin.connection_ref, actor)
        self._active(row)
        if (row.provider, row.kind, row.non_secret_config["endpoint_key"]) != (
            pin.provider,
            pin.kind,
            pin.endpoint_key,
        ):
            raise VersionConflictException("Connection contract changed")
        try:
            return await self.provider.invoke(pin)
        except Exception:  # noqa: BLE001 -- This boundary must redact all provider exceptions.
            raise ServiceUnavailableException("Integration unavailable") from None

    async def grant(self, ref_id: str, data: GrantDTO, actor: UserEntity) -> Grant:
        row = await self.get(ref_id, actor, manage=True, update=True)
        self._not_revoked(row)
        user_id = open_ref_id(data.user_ref_id)[0] if data.user_ref_id else None
        group_id = open_ref_id(data.work_group_ref_id)[0] if data.work_group_ref_id else None
        target = (
            await self.session.get(UserEntity, user_id)
            if user_id
            else await self.session.get(WorkGroupEntity, group_id)
        )
        if (
            target is None
            or target.deleted_at
            or isinstance(target, WorkGroupEntity)
            and not target.is_active
        ):
            raise NotFoundException("Active grant target not found")
        grant = (
            await self.session.exec(
                select(Grant).where(
                    Grant.integration_connection_id == row.id,
                    Grant.user_id == user_id,
                    Grant.work_group_id == group_id,
                    col(Grant.deleted_at).is_(None),
                )
            )
        ).one_or_none()
        if grant is None:
            grant = Grant(integration_connection_id=row.id, user_id=user_id, work_group_id=group_id)
            self.session.add(grant)
        grant.can_use, grant.can_manage = data.can_use or data.can_manage, data.can_manage
        await self._changed(row, actor, "grant_changed", target=str(user_id or group_id))
        return grant

    async def remove_grant(self, ref_id: str, grant_ref_id: str, actor: UserEntity) -> None:
        row = await self.get(ref_id, actor, manage=True, update=True)
        grant = await self.session.get(Grant, open_ref_id(grant_ref_id)[0])
        if grant is None or grant.integration_connection_id != row.id or grant.deleted_at:
            raise NotFoundException("Grant not found")
        grant.deleted_at = get_datetime_utc()
        await self._changed(
            row, actor, "grant_removed", target=str(grant.user_id or grant.work_group_id)
        )

    @staticmethod
    def _pin(row: Connection) -> ConnectionPin:
        return ConnectionPin(
            connection_ref=create_ref_id(row.id, row.version),
            provider=row.provider,
            kind=row.kind,
            endpoint_key=row.non_secret_config["endpoint_key"],
            secret_ref=row.secret_ref,
            secret_version=row.secret_version,
        )

    @staticmethod
    def _not_revoked(row: Connection) -> None:
        if row.status == "REVOKED":
            raise VersionConflictException("Connection is revoked")

    @staticmethod
    def _active(row: Connection) -> None:
        if row.status != "ACTIVE":
            raise VersionConflictException("Connection is unavailable")

    def _audit(
        self, row: Connection, actor: UserEntity, action: str, *, target: str | None = None
    ) -> None:
        self.session.add(
            AuthAuditEventEntity(
                user_id=actor.id,
                event_type=f"connection.{action}",
                details={"connection_id": str(row.id), "target": target},
            )
        )

    async def _changed(
        self, row: Connection, actor: UserEntity, action: str, *, target: str | None = None
    ) -> None:
        row.updated_at = get_datetime_utc()
        self._audit(row, actor, action, target=target)
        await self.session.flush()
