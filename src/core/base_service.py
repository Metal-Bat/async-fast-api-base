"""Generic async CRUD service built on top of BaseCrudRepository."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from core.base_entity import BaseEntity
from core.base_repository import BaseCrudRepository
from utils.base_schema import PaginatedResponse
from utils.exceptions import NotFoundException


class BaseCrudService[
    TEntity: BaseEntity,
    TQuery: BaseModel,
    TRepo: BaseCrudRepository,
]:
    """Async CRUD service that wraps a :class:`BaseCrudRepository`.

    Subclass and supply the concrete types as type arguments:

        class UserService(BaseCrudService[UserEntity, UserQuery, UserRepository]):
            pass

    Type parameters:
        TEntity: The SQLModel entity class.
        TQuery:  The Pydantic query/filter model (from ``auto_query_model``).
        TRepo:   The concrete repository class for this entity.
    """

    def __init__(self, repo: TRepo) -> None:
        self.repo = repo

    async def create(self, obj: TEntity) -> TEntity:
        """Persist *obj* and return it with server-generated fields populated."""
        return await self.repo.create(obj)

    async def list(self, query_params: TQuery) -> PaginatedResponse[TEntity]:
        """Return a paginated response for the given filter/sort/page parameters."""
        items = await self.repo.list(query_params)
        total = await self.repo.count(query_params)
        return PaginatedResponse[TEntity](items=items, total=total)

    async def get_by_id(self, id: UUID) -> TEntity:
        """Return the entity with *id*, or raise :exc:`NotFoundException`."""
        item = await self.repo.get_by_id(id)
        if item is None:
            raise NotFoundException(f"{self.repo.model.__name__} not found")
        return item

    async def update(self, id: UUID, data: dict[str, Any]) -> TEntity:
        """Apply *data* fields onto the entity with *id* and persist.

        Raises:
            NotFoundException: when no entity with *id* exists.
        """
        item = await self.repo.get_by_id(id)
        if item is None:
            raise NotFoundException(f"{self.repo.model.__name__} not found")
        return await self.repo.update(item, data)

    async def delete(self, id: UUID) -> None:
        """Soft-delete the entity with *id*.

        Raises:
            NotFoundException: when no entity with *id* exists.
        """
        item = await self.repo.get_by_id(id)
        if item is None:
            raise NotFoundException(f"{self.repo.model.__name__} not found")
        await self.repo.delete(item)
