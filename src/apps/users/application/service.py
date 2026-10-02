from pydantic import TypeAdapter

from apps.users.data.cache_repository import UserCacheRepository
from apps.users.data.repository import UserRepository
from apps.users.domain.dto import UserDTO, UserQuery
from apps.users.domain.entity import UserEntity
from core.base_service import BaseCrudService
from core.deps import SessionDep
from utils.pagination import Page


def get_user_service(session: SessionDep) -> UserService:
    return UserService(UserRepository(session, UserEntity))


class UserService(
    BaseCrudService[
        UserEntity,
        UserQuery,
        UserRepository,
    ]
):
    def __init__(self, repo: UserRepository, cache: UserCacheRepository | None = None) -> None:
        super().__init__(repo)
        self.cache = cache or UserCacheRepository()

    async def list_public(self, query: UserQuery) -> Page[UserDTO]:
        """Cache one validated public page including its total count."""
        adapter = TypeAdapter(Page[UserDTO])

        async def load() -> Page[UserDTO]:
            return adapter.validate_python(
                await super(UserService, self).list(query), from_attributes=True
            )

        return await self.cache.get_or_load(f"page:{query.model_dump_json()}", adapter, load)

    async def get_public_by_id(self, ref_id: str) -> UserDTO:
        """Cache one public user detail by its versioned reference."""
        adapter = TypeAdapter(UserDTO)

        async def load() -> UserDTO:
            return adapter.validate_python(
                await super(UserService, self).get_by_id(ref_id), from_attributes=True
            )

        return await self.cache.get_or_load(f"detail:{ref_id}", adapter, load)
