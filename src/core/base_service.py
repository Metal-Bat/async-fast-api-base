from typing import Any, cast

from core.base_entity import BaseEntity
from core.base_repository import BaseCrudRepository
from core.ref_id import open_ref_id
from utils.exceptions import NotFoundException
from utils.pagination import Page, SearchRequest


class BaseCrudService[
    TEntity: BaseEntity,
    TQuery: SearchRequest,
    TRepo: BaseCrudRepository[Any],
]:
    """Async CRUD service that wraps ``BaseCrudRepository``.

    Subclass and supply the concrete types as type arguments:

        class UserService(BaseCrudService[UserEntity, UserQuery, UserRepository]):
            pass

    Attributes:
        repo: Concrete repository for the managed entity.
    """

    def __init__(self, repo: TRepo) -> None:
        self.repo = repo

    async def create(self, obj: TEntity) -> TEntity:
        """Persist *obj* and return it with server-generated fields populated."""
        return cast(TEntity, await self.repo.create(obj))

    async def list(self, query_params: TQuery) -> Page[TEntity]:
        """Return a paginated response for the given filter/sort/page parameters."""
        items: list[TEntity] = list(await self.repo.list(query_params))
        total = await self.repo.count(query_params)
        return Page[TEntity](
            items=items, total=total, page=query_params.page, size=query_params.size
        )

    async def get_by_id(self, ref_id: str) -> TEntity:
        """Resolve *ref_id* and return its entity, or raise ``NotFoundException``."""
        id, _ = open_ref_id(ref_id)
        item = await self.repo.get_by_id(id)
        if item is None:
            raise NotFoundException(f"{self.repo.model.__name__} not found")
        return cast(TEntity, item)

    async def update(self, ref_id: str, data: dict[str, Any]) -> TEntity:
        """Resolve *ref_id*, verify its version, apply *data*, and persist.

        Raises:
            NotFoundException: when no entity with *id* exists.
        """
        id, version = open_ref_id(ref_id)
        item = await self.repo.get_by_id(id)
        if item is None:
            raise NotFoundException(f"{self.repo.model.__name__} not found")
        values = data.copy()
        values.pop("ref_id", None)
        values.pop("refId", None)
        values["version"] = version
        return cast(TEntity, await self.repo.update(item, values))

    async def delete(self, ref_id: str) -> None:
        """Resolve *ref_id*, verify its version, and soft-delete the entity.

        Raises:
            NotFoundException: when no entity with *id* exists.
        """
        id, version = open_ref_id(ref_id)
        item = await self.repo.get_by_id(id)
        if item is None:
            raise NotFoundException(f"{self.repo.model.__name__} not found")
        await self.repo.delete(item, expected_version=version)
