"""Self-owned bounded presets and canonical favorites, with authority checked on every read."""

import json
from hashlib import sha256
from types import SimpleNamespace
from uuid import UUID, uuid5

from pydantic import TypeAdapter, ValidationError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.designer.application.resource_links import ResourceLinkService
from apps.designer.domain.resource_links import ResourceKind, ResourceReference
from apps.users.application.authorization import user_permissions
from apps.users.application.saved_views import PERMISSIONS, validate_preset
from apps.users.domain.entity import UserEntity
from apps.users.domain.personal_entity import PersonalItemEntity
from apps.users.domain.saved_views import (
    AppliedView,
    FavoriteDTO,
    FavoriteInput,
    PersonalHistoryDTO,
    PersonalHistoryQuery,
    PersonalItemQuery,
    SavedViewDTO,
    SavedViewInput,
    ViewScope,
)
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException
from utils.pagination import Page, apply_query, paginate_values


class PersonalCollectionsService:
    """Callers own commit; user-row locks serialize bounds, duplicates and default changes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _actor(self, actor: UserEntity, *, write: bool = False) -> UserEntity:
        current = await self.session.get(
            UserEntity, actor.id, populate_existing=True, with_for_update=write
        )
        if current is None or current.deleted_at is not None:
            raise NotFoundException("Personal item not found")
        return current

    async def _permission(self, actor: UserEntity, scope: str) -> None:
        permissions = await user_permissions(actor, self.session)
        if "*" not in permissions and PERMISSIONS.get(scope) not in permissions:
            raise NotFoundException("Personal item not found")

    async def _owned(
        self, actor: UserEntity, reference: str, kind: str, *, expected: bool = False
    ) -> PersonalItemEntity:
        identity, version = open_ref_id(reference)
        row = await self.session.get(PersonalItemEntity, identity, populate_existing=True)
        if row is None or row.user_id != actor.id or row.kind != kind or row.deleted_at is not None:
            raise NotFoundException("Personal item not found")
        if expected and row.version != version:
            raise VersionConflictException("Personal item reference is stale")
        return row

    async def _rows(
        self, actor: UserEntity, kind: str, query: PersonalItemQuery | None = None
    ) -> list[PersonalItemEntity]:
        statement = select(PersonalItemEntity).where(
            PersonalItemEntity.user_id == actor.id,
            PersonalItemEntity.kind == kind,
            col(PersonalItemEntity.deleted_at).is_(None),
        )
        if query is not None:
            statement = apply_query(
                statement, PersonalItemEntity, query, paginate=False, order=True
            )
        else:
            statement = statement.order_by(col(PersonalItemEntity.id))
        return list((await self.session.exec(statement)).all())

    def _input(self, data: SavedViewInput) -> SavedViewInput:
        try:
            return validate_preset(data)
        except ValueError, TypeError:
            raise ValidationDetailsException(
                [{"pointer": "/query", "code": "saved_view.invalid_contract"}]
            ) from None

    @staticmethod
    def _view(row: PersonalItemEntity) -> SavedViewDTO:
        original = row.document["current"]
        compatible = True
        try:
            validate_preset(SavedViewInput.model_validate(original))
        except ValidationError, ValueError, TypeError:
            compatible = False
        return SavedViewDTO(
            ref_id=create_ref_id(row.id, row.version),
            name=row.name or "",
            resource_kind=TypeAdapter(ViewScope).validate_python(row.scope),
            schema_version=original["schema_version"],
            query=original["query"],
            column_keys=original["column_keys"],
            page_size=original["page_size"],
            is_default=row.is_default,
            compatible=compatible,
            reason="compatible" if compatible else "schema_changed",
        )

    async def create_view(self, actor: UserEntity, data: SavedViewInput) -> SavedViewDTO:
        actor = await self._actor(actor, write=True)
        await self._permission(actor, data.resource_kind)
        data = self._input(data)
        values = data.model_dump(mode="json")
        identity = uuid5(actor.id, "saved-view:" + data.command_key)
        existing = await self.session.get(PersonalItemEntity, identity, populate_existing=True)
        if existing is not None:
            if existing.document.get("creation") != values:
                raise VersionConflictException("Saved-view creation key has another payload")
            if existing.deleted_at is not None:
                raise NotFoundException("Saved view was removed")
            return self._view(existing)
        await self._check_name(actor, data.resource_kind, data.name)
        rows = await self._rows(actor, "view")
        if sum(row.scope == data.resource_kind for row in rows) >= 100:
            raise ValidationDetailsException([{"pointer": "/", "code": "saved_view.limit"}])
        row = PersonalItemEntity(
            id=identity,
            user_id=actor.id,
            kind="view",
            scope=data.resource_kind,
            name=data.name,
            document={"creation": values, "current": values},
        )
        self.session.add(row)
        await self.session.flush()
        return self._view(row)

    async def _check_name(
        self, actor: UserEntity, scope: str, name: str, identity: UUID | None = None
    ) -> None:
        rows = await self._rows(actor, "view")
        if any(row.scope == scope and row.name == name and row.id != identity for row in rows):
            raise VersionConflictException("Saved-view name already exists in this scope")

    async def get_view(self, actor: UserEntity, reference: str) -> SavedViewDTO:
        actor = await self._actor(actor)
        row = await self._owned(actor, reference, "view")
        await self._permission(actor, row.scope)
        return self._view(row)

    async def update_view(
        self, actor: UserEntity, reference: str, data: SavedViewInput
    ) -> SavedViewDTO:
        actor = await self._actor(actor, write=True)
        row = await self._owned(actor, reference, "view")
        await self._permission(actor, row.scope)
        if data.resource_kind != row.scope:
            raise VersionConflictException("Saved-view scope cannot be reassigned")
        data = self._input(data)
        values = data.model_dump(mode="json")
        digest = sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
        if row.document.get("update_key") == data.command_key:
            if row.document.get("update_hash") != digest:
                raise VersionConflictException("Saved-view update key has another payload")
            return self._view(row)
        await self._owned(actor, reference, "view", expected=True)
        await self._check_name(actor, row.scope, data.name, row.id)
        row.name = data.name
        row.document = row.document | {
            "current": values,
            "update_key": data.command_key,
            "update_hash": digest,
        }
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return self._view(row)

    async def search_views(self, actor: UserEntity, query: PersonalItemQuery) -> Page[SavedViewDTO]:
        actor = await self._actor(actor)
        permissions = await user_permissions(actor, self.session)
        rows = await self._rows(actor, "view", query)
        values = [
            self._view(row)
            for row in rows
            if "*" in permissions or PERMISSIONS.get(row.scope) in permissions
        ]
        return paginate_values(values, query)

    async def set_default(self, actor: UserEntity, reference: str) -> SavedViewDTO:
        actor = await self._actor(actor, write=True)
        row = await self._owned(actor, reference, "view")
        await self._permission(actor, row.scope)
        if row.is_default:
            return self._view(row)
        await self._owned(actor, reference, "view", expected=True)
        if not self._view(row).compatible:
            raise VersionConflictException("Incompatible saved view cannot become default")
        for other in await self._rows(actor, "view"):
            if other.scope == row.scope and other.is_default:
                other.is_default = False
                other.updated_at = get_datetime_utc()
        await self.session.flush()
        row.is_default = True
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return self._view(row)

    async def apply_view(self, actor: UserEntity, reference: str) -> AppliedView:
        view = await self.get_view(actor, reference)
        return AppliedView(
            compatible=view.compatible,
            reason=view.reason,
            resource_kind=view.resource_kind,
            query=view.query | {"page": 1, "size": view.page_size} if view.compatible else None,
            column_keys=view.column_keys if view.compatible else [],
        )

    async def _favorite(self, actor: UserEntity, row: PersonalItemEntity) -> FavoriteDTO:
        if row.target_id is None:
            raise NotFoundException("Favorite target not found")
        kind = TypeAdapter(ResourceKind).validate_python(row.scope)
        target = await ResourceLinkService(self.session).mint(
            ResourceReference(kind=kind, ref_id=create_ref_id(row.target_id, 0)), actor
        )
        return FavoriteDTO(ref_id=create_ref_id(row.id, row.version), target=target)

    async def create_favorite(self, actor: UserEntity, data: FavoriteInput) -> FavoriteDTO:
        actor = await self._actor(actor, write=True)
        link = await ResourceLinkService(self.session).mint(data, actor)
        target_id, _ = open_ref_id(link.ref_id)
        identity = uuid5(actor.id, f"favorite:{data.kind}:{target_id}")
        row = await self.session.get(PersonalItemEntity, identity, populate_existing=True)
        if row is None:
            rows = await self._rows(actor, "favorite")
            if len(rows) >= 500 or sum(item.scope == data.kind for item in rows) >= 100:
                raise ValidationDetailsException([{"pointer": "/", "code": "favorite.limit"}])
            row = PersonalItemEntity(
                id=identity, user_id=actor.id, kind="favorite", scope=data.kind, target_id=target_id
            )
            self.session.add(row)
        elif row.deleted_at is not None:
            rows = await self._rows(actor, "favorite")
            if len(rows) >= 500 or sum(item.scope == data.kind for item in rows) >= 100:
                raise ValidationDetailsException([{"pointer": "/", "code": "favorite.limit"}])
            row.deleted_at = None
            row.updated_at = get_datetime_utc()
        await self.session.flush()
        return await self._favorite(actor, row)

    async def get_favorite(self, actor: UserEntity, reference: str) -> FavoriteDTO:
        actor = await self._actor(actor)
        return await self._favorite(actor, await self._owned(actor, reference, "favorite"))

    async def search_favorites(
        self, actor: UserEntity, query: PersonalItemQuery
    ) -> Page[FavoriteDTO]:
        actor = await self._actor(actor)
        values = []
        for row in await self._rows(actor, "favorite", query):
            try:
                values.append(await self._favorite(actor, row))
            except NotFoundException:
                continue
        return paginate_values(values, query)

    async def delete(self, actor: UserEntity, reference: str, kind: str) -> None:
        actor = await self._actor(actor, write=True)
        identity, version = open_ref_id(reference)
        row = await self.session.get(PersonalItemEntity, identity, populate_existing=True)
        if row is None or row.user_id != actor.id or row.kind != kind:
            raise NotFoundException("Personal item not found")
        if row.deleted_at is not None:
            return
        if row.version != version:
            raise VersionConflictException("Personal item reference is stale")
        row.deleted_at = get_datetime_utc()
        row.is_default = False
        await self.session.flush()

    async def history(
        self, actor: UserEntity, reference: str, kind: str, query: PersonalHistoryQuery
    ) -> Page[PersonalHistoryDTO]:
        from apps.users.domain.personal_entity import PersonalItemHistoryTable

        actor = await self._actor(actor)
        row = await self._owned(actor, reference, kind)
        if kind == "view":
            await self._permission(actor, row.scope)
        else:
            await self._favorite(actor, row)
        table = PersonalItemHistoryTable
        fields = SimpleNamespace(
            changed_at=table.c.CHANGED_AT, operation=table.c.OPERATION, id=table.c.ID
        )
        statement = apply_query(
            select(table.c.CHANGED_AT, table.c.OPERATION).where(table.c.ENTITY_ID == row.id),
            fields,
            query,
            default_ordering=("changed_at", "id"),
        )
        entries = (await self.session.exec(statement)).all()
        total = (
            await self.session.exec(
                apply_query(
                    select(func.count()).select_from(table).where(table.c.ENTITY_ID == row.id),
                    fields,
                    query,
                    paginate=False,
                )
            )
        ).one()
        return Page(
            items=[
                PersonalHistoryDTO(changed_at=entry[0], operation=entry[1]) for entry in entries
            ],
            page=query.page,
            size=query.size,
            total=total,
        )
