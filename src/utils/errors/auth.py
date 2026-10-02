from core.i18n import _
from utils.errors.base import ErrorCode


class AuthError(ErrorCode):
    """Stable numeric codes and English fallback messages."""

    INVALID_CREDENTIALS = (2001, _("Invalid authentication credentials."))
    NOT_ALLOWED = (2002, _("You do not have permission to perform this action."))
    ACCOUNT_LOCKED = (2003, _("The account is temporarily locked."))
    INVALID_TOKEN = (2004, _("The token is invalid or expired."))
    USER_NOT_FOUND = (2005, _("User not found."))
    INACTIVE_USER = (2006, _("The user account is inactive."))
