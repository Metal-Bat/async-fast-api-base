from core.i18n import _
from utils.errors.base import ErrorCode


class CommonError(ErrorCode):
    """Stable numeric codes and English fallback messages."""

    NOT_FOUND = (1003, _("Resource not found."))
    INVALID_REQUEST = (1001, _("The request is invalid."))
    VALIDATION_FAILED = (1002, _("Request validation failed."))
    VERSION_CONFLICT = (1004, _("The resource was modified. Refresh and try again."))
    INVALID_REFERENCE = (1005, _("The resource reference is invalid."))
    INTERNAL_ERROR = (1099, _("An unexpected error occurred."))
    SERVICE_UNAVAILABLE = (1098, _("The service is temporarily unavailable."))
    RATE_LIMITED = (1006, _("Too many requests. Try again later."))
