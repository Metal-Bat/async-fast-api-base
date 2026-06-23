from apps.users.data.repository import UserRepository
from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from core.base_service import BaseCrudService
from core.deps import SessionFactory


async def get_user_service():
    async with SessionFactory() as session:
        repo = UserRepository(session, UserEntity)
        yield UserService(repo)


class UserService(
    BaseCrudService[
        UserEntity,
        UserQuery,
        UserRepository,
    ]
):
    pass
