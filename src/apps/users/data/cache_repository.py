"""Read cache namespace for public user search and detail models."""

from apps.users.domain.entity import UserEntity
from core.cache_repository import BaseCacheRepository
from core.cache_session import register_cached_model


class UserCacheRepository(BaseCacheRepository):
    def __init__(self, *, ttl_seconds: int = 30 * 60) -> None:
        super().__init__("users", ttl_seconds=ttl_seconds)


register_cached_model(UserEntity, "users")
