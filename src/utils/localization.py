from core.i18n import resolve_language, translate
from utils.errors import ErrorCode


def localize_error(error: ErrorCode, language: str | None = None) -> str:
    """Translate an enum error, falling back to its safe English text."""
    return translate(error.text, language)


__all__ = ["localize_error", "resolve_language"]
