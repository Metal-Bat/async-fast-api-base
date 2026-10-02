from typing import cast

from redis import exceptions

from utils.external_errors import ExternalError


def _catalog() -> dict[type[BaseException], ExternalError]:
    """Discover localizable redis-py exception types."""
    result: dict[type[BaseException], ExternalError] = {}
    for name in dir(exceptions):
        error_type = getattr(exceptions, name)
        if isinstance(error_type, type) and issubclass(error_type, BaseException):
            result[error_type] = ExternalError("cache", name, name, f"cache.{name}")
    return result


CACHE_ERRORS = _catalog()


def localizable_cache_error(exc: BaseException) -> ExternalError:
    """Map any redis-py exception to a stable localization key."""
    for error_type in type(exc).__mro__:
        if error_type in CACHE_ERRORS:
            return CACHE_ERRORS[cast(type[BaseException], error_type)]
    name = type(exc).__name__
    return ExternalError("cache", name, name, f"cache.{name}")
