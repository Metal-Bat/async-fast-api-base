from typing import cast

from amqp import exceptions as amqp_exceptions
from kombu import exceptions as kombu_exceptions

from utils.external_errors import ExternalError


def _catalog() -> dict[type[BaseException], ExternalError]:
    """Discover localizable AMQP and Kombu exception types."""
    result: dict[type[BaseException], ExternalError] = {}
    for module in (amqp_exceptions, kombu_exceptions):
        for name in dir(module):
            error_type = getattr(module, name)
            if isinstance(error_type, type) and issubclass(error_type, BaseException):
                result[error_type] = ExternalError("broker", name, name, f"broker.{name}")
    return result


BROKER_ERRORS = _catalog()


def localizable_broker_error(exc: BaseException) -> ExternalError:
    """Map any Kombu/AMQP exception to a stable localization key."""
    for error_type in type(exc).__mro__:
        if error_type in BROKER_ERRORS:
            return BROKER_ERRORS[cast(type[BaseException], error_type)]
    name = type(exc).__name__
    return ExternalError("broker", name, name, f"broker.{name}")
