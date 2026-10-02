"""Authorize registered application clients and bind exact releases to sessions."""

import hashlib
import hmac
import secrets
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.domain.contracts import ClientContext, ClientKind
from apps.clients.domain.dto import ClientCreateDTO, ClientReleaseCreateDTO, ClientUpdateDTO
from apps.clients.domain.entity import ClientEntity, ClientReleaseEntity
from apps.users.domain.auth_entity import AuthSessionEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import InvalidCredentialError, NotFoundException, VersionConflictException
from utils.pagination import Page
from utils.select import SelectOption, SelectQuery


class ClientService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_client(self, data: ClientCreateDTO) -> tuple[ClientEntity, str | None]:
        secret = secrets.token_urlsafe(48) if data.confidential else None
        row = ClientEntity(
            code=data.code,
            name=data.name,
            kind=data.kind,
            platform=data.platform,
            secret_hash=hashlib.sha256(secret.encode()).hexdigest() if secret else None,
        )
        self.session.add(row)
        await self.session.flush()
        return row, secret

    async def get_client(self, ref_id: str, *, update: bool = False) -> ClientEntity:
        client_id, expected = open_ref_id(ref_id)
        row = await self.session.get(
            ClientEntity, client_id, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Client not found")
        if update and row.version != expected:
            raise VersionConflictException("Client is stale")
        return row

    async def update_client(self, ref_id: str, data: ClientUpdateDTO) -> ClientEntity:
        row = await self.get_client(ref_id, update=True)
        row.name = data.name
        row.platform = data.platform
        row.is_active = data.is_active
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def delete_client(self, ref_id: str) -> None:
        row = await self.get_client(ref_id, update=True)
        row.is_active = False
        row.deleted_at = get_datetime_utc()
        await self.session.flush()

    async def rotate_secret(self, ref_id: str) -> tuple[ClientEntity, str]:
        row = await self.get_client(ref_id, update=True)
        if row.secret_hash is None:
            raise VersionConflictException("Public client has no secret")
        secret = secrets.token_urlsafe(48)
        row.secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row, secret

    async def get_release(self, ref_id: str, *, update: bool = False) -> ClientReleaseEntity:
        release_id, expected = open_ref_id(ref_id)
        row = await self.session.get(
            ClientReleaseEntity, release_id, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Client release not found")
        if update and row.version != expected:
            raise VersionConflictException("Client release is stale")
        return row

    async def disable_release(self, ref_id: str) -> ClientReleaseEntity:
        row = await self.get_release(ref_id, update=True)
        row.is_enabled = False
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def select_clients(self, query: SelectQuery) -> Page[SelectOption[str]]:
        statement = select(ClientEntity).where(
            col(ClientEntity.deleted_at).is_(None),
            col(ClientEntity.is_active).is_(True),
        )
        if query.search:
            pattern = "%" + query.search.replace("%", "/%").replace("_", "/_") + "%"
            statement = statement.where(
                or_(
                    col(ClientEntity.code).ilike(pattern, escape="/"),
                    col(ClientEntity.name).ilike(pattern, escape="/"),
                )
            )
        total = (
            await self.session.exec(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
        ).one()
        rows = (
            await self.session.exec(
                statement.order_by(col(ClientEntity.code), col(ClientEntity.id))
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

    async def select_releases(
        self, client_ref_id: str, query: SelectQuery
    ) -> Page[SelectOption[str]]:
        client = await self.get_client(client_ref_id)
        statement = select(ClientReleaseEntity).where(
            ClientReleaseEntity.client_id == client.id,
            col(ClientReleaseEntity.deleted_at).is_(None),
            col(ClientReleaseEntity.is_enabled).is_(True),
        )
        if query.search:
            pattern = "%" + query.search.replace("%", "/%").replace("_", "/_") + "%"
            statement = statement.where(
                col(ClientReleaseEntity.release_version).ilike(pattern, escape="/")
            )
        total = (
            await self.session.exec(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
        ).one()
        rows = (
            await self.session.exec(
                statement.order_by(
                    col(ClientReleaseEntity.release_version), col(ClientReleaseEntity.id)
                )
                .offset((query.page - 1) * query.size)
                .limit(query.size)
            )
        ).all()
        return Page[SelectOption[str]](
            items=[
                SelectOption(key=create_ref_id(row.id, row.version), value=row.release_version)
                for row in rows
            ],
            page=query.page,
            size=query.size,
            total=total,
        )

    async def create_release(
        self, client_id: UUID, data: ClientReleaseCreateDTO
    ) -> ClientReleaseEntity:
        client = await self.session.get(ClientEntity, client_id)
        if client is None or client.deleted_at or not client.is_active:
            raise NotFoundException("Client is unavailable")
        row = ClientReleaseEntity(
            client_id=client_id,
            release_version=data.version,
            api_version=data.api_version,
            renderer_capabilities=data.renderer_capabilities,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def authenticate(
        self, client_key: str | None, secret: str | None, release_version: str | None
    ) -> ClientContext:
        if client_key is None and secret is None and release_version is None:
            return ClientContext.legacy()
        if not client_key or not release_version:
            raise InvalidCredentialError("Client identity and release are required")
        client = (
            await self.session.exec(select(ClientEntity).where(ClientEntity.code == client_key))
        ).one_or_none()
        if client is None or client.deleted_at or not client.is_active:
            raise InvalidCredentialError("Client is unavailable")
        if client.secret_hash is not None:
            digest = hashlib.sha256((secret or "").encode()).hexdigest()
            if not hmac.compare_digest(client.secret_hash, digest):
                raise InvalidCredentialError("Client credentials are invalid")
        elif secret is not None:
            raise InvalidCredentialError("Public clients have no secret")
        release = (
            await self.session.exec(
                select(ClientReleaseEntity).where(
                    ClientReleaseEntity.client_id == client.id,
                    ClientReleaseEntity.release_version == release_version,
                )
            )
        ).one_or_none()
        if release is None or release.deleted_at or not release.is_enabled:
            raise InvalidCredentialError("Client release is unavailable")
        return self._context(client, release)

    async def for_session(self, auth_session: AuthSessionEntity) -> ClientContext:
        if auth_session.client_id is None and auth_session.client_release_id is None:
            return ClientContext.legacy()
        if auth_session.client_id is None or auth_session.client_release_id is None:
            raise InvalidCredentialError("Client session binding is incomplete")
        client = await self.session.get(ClientEntity, auth_session.client_id)
        release = await self.session.get(ClientReleaseEntity, auth_session.client_release_id)
        if (
            client is None
            or release is None
            or client.deleted_at
            or release.deleted_at
            or not client.is_active
            or not release.is_enabled
            or release.client_id != client.id
        ):
            raise InvalidCredentialError("Client session binding is unavailable")
        return self._context(client, release)

    @staticmethod
    def _context(client: ClientEntity, release: ClientReleaseEntity) -> ClientContext:
        return ClientContext(
            client_id=client.id,
            release_id=release.id,
            client_key=client.code,
            kind=cast(ClientKind, client.kind),
            platform=client.platform,
            release=release.release_version,
            api_version=release.api_version,
            renderer_capabilities=frozenset(release.renderer_capabilities),
            trusted=client.secret_hash is not None,
        )
