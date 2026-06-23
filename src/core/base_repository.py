"""Generic async CRUD repository built on SQLModel + AsyncSession."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlmodel import Sequence, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.base_entity import BaseEntity
from utils.date_utils import get_datetime_utc
from utils.pagination import apply_query


class BaseCrudRepository[EntityType: BaseEntity]:
    """Async CRUD repository for a single SQLModel entity type.

    Subclass and provide the concrete entity as the type argument:

        class UserRepository(BaseCrudRepository[UserEntity]):
            pass

    Type parameters:
        EntityType: The SQLModel entity class managed by this repository.
    """

    def __init__(self, session: AsyncSession, model: type[EntityType]) -> None:
        self.session = session
        self.model = model

    async def create(self, obj: EntityType) -> EntityType:
        """Persist *obj* and return it with any server-generated fields (e.g. id, created_at) populated."""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def list(self, query_params: BaseModel) -> Sequence[EntityType]:
        """Return a paginated, filtered, and sorted page of entities.

        Filtering, ordering, and pagination are derived from *query_params*
        (typically produced by :func:`~utils.pagination.auto_query_model`).
        """
        query = select(self.model)
        query = apply_query(query=query, model=self.model, query_params=query_params)
        result = await self.session.exec(query)
        return result.all()

    async def count(self, query_params: BaseModel) -> int:
        """Return the total number of entities matching the filters in *query_params*.

        Pagination (page / page_size) is intentionally ignored so the caller
        gets the full count regardless of the current page.
        """
        query = select(func.count()).select_from(self.model)
        query = apply_query(
            query=query, model=self.model, query_params=query_params, paginate=False
        )
        result = await self.session.exec(query)
        return result.one()

    async def get_by_id(self, id: UUID) -> EntityType | None:
        """Fetch a single entity by primary key, or ``None`` if not found."""
        return await self.session.get(self.model, id)

    async def update(self, db_obj: EntityType, update_dict: dict[str, Any]) -> EntityType:
        """Apply *update_dict* onto *db_obj*, stamp *updated_at*, and persist the changes."""
        for key, value in update_dict.items():
            setattr(db_obj, key, value)
        db_obj.updated_at = get_datetime_utc()
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, db_obj: EntityType) -> None:
        """Soft-delete *db_obj* by stamping *deleted_at* and persisting the change."""
        db_obj.deleted_at = get_datetime_utc()
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
