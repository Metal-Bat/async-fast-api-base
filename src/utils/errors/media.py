from core.i18n import _
from utils.errors.base import ErrorCode


class MediaError(ErrorCode):
    """Stable numeric codes and English fallback messages."""

    UPLOAD_TOO_LARGE = (3001, _("The upload exceeds the size limit."))
    INVALID_IMAGE = (3002, _("The uploaded content is not a valid image."))
    UPLOAD_RATE_LIMIT = (3003, _("The upload limit was exceeded. Try again later."))
    INVALID_FILE = (3004, _("The uploaded content is not a supported file."))
