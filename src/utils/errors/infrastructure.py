from core.i18n import _
from utils.errors.base import ErrorCode


class InfrastructureError(ErrorCode):
    """Stable error numbers without exposing backend exception details."""

    DATABASE_UNAVAILABLE = (4001, _("The database is temporarily unavailable."))
    DATA_CONFLICT = (4002, _("The operation conflicts with existing data."))
    CACHE_UNAVAILABLE = (4003, _("The cache service is temporarily unavailable."))
    STORAGE_UNAVAILABLE = (4004, _("The file storage service is temporarily unavailable."))
    BROKER_UNAVAILABLE = (4005, _("The task broker is temporarily unavailable."))
