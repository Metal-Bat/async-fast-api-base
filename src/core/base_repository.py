import builtins
from typing import Any
from uuid import UUID

from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.base_entity import BaseEntity
from utils.date_utils import get_datetime_utc
from utils.exceptions import VersionConflictException
from utils.pagination import SearchRequest, apply_query


class BaseCrudRepository[EntityType: BaseEntity]:
    """Async CRUD repository for a single SQLModel entity type.

    Subclass and provide the concrete entity as the type argument:

        class UserRepository(BaseCrudRepository[UserEntity]):
            pass

    Attributes:
        model: SQLModel entity class managed by this repository.
    """

    def __init__(self, session: AsyncSession, model: type[EntityType]) -> None:
        self.session = session
        self.model = model

    async def create(self, obj: EntityType) -> EntityType:
        """Persist an entity and populate its database-generated fields.

        Args:
            obj: Entity to persist.

        Returns:
            The refreshed entity.
        """
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def list(self, query_params: SearchRequest) -> builtins.list[EntityType]:
        """Return a paginated, filtered, and sorted page of entities.

        Filtering, ordering, and pagination are derived from ``query_params``.

        Args:
            query_params: Validated filters, ordering, and pagination.

        Returns:
            Matching entities.
        """
        query = select(self.model)
        query = apply_query(
            query=query,
            model=self.model,
            query_params=query_params,
            default_ordering=self.model.__default_ordering__,
        )
        result = await self.session.exec(query)
        return list(result.all())

    async def count(self, query_params: SearchRequest) -> int:
        """Return the total number of entities matching the filters in *query_params*.

        Pagination (page / size) is intentionally ignored so the caller
        gets the full count regardless of the current page.
        """
        query = select(func.count()).select_from(self.model)
        query = apply_query(
            query=query, model=self.model, query_params=query_params, paginate=False
        )
        result = await self.session.exec(query)
        return result.one()

    async def get_by_id(self, id: UUID) -> EntityType | None:
        """Fetch a single entity by primary key.

        Args:
            id: Internal entity UUID.

        Returns:
            The entity, or ``None`` when it does not exist.
        """
        return await self.session.get(self.model, id)

    async def update(self, db_obj: EntityType, update_dict: dict[str, Any]) -> EntityType:
        """Apply *update_dict* onto *db_obj*, stamp *updated_at*, and persist the changes."""
        values = update_dict.copy()
        expected_version = values.pop("version", None)
        if expected_version is not None and expected_version != db_obj.version:
            raise VersionConflictException(
                f"Expected version {expected_version}, but current version is {db_obj.version}"
            )

        for key, value in values.items():
            setattr(db_obj, key, value)
        db_obj.updated_at = get_datetime_utc()
        self.session.add(db_obj)
        try:
            await self.session.flush()
        except StaleDataError as exc:
            raise VersionConflictException("The entity was modified by another request") from exc
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, db_obj: EntityType, expected_version: int | None = None) -> None:
        """Soft-delete *db_obj* by stamping *deleted_at* and persisting the change."""
        if expected_version is not None and expected_version != db_obj.version:
            raise VersionConflictException(
                f"Expected version {expected_version}, but current version is {db_obj.version}"
            )
        db_obj.deleted_at = get_datetime_utc()
        self.session.add(db_obj)
        try:
            await self.session.flush()
        except StaleDataError as exc:
            raise VersionConflictException("The entity was modified by another request") from exc
        await self.session.refresh(db_obj)
