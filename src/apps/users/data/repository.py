from apps.users.domain.entity import UserEntity
from core.base_repository import BaseCrudRepository


class UserRepository(BaseCrudRepository[UserEntity]):
    pass
