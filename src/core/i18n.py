from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from functools import cache
from pathlib import Path

from babel.support import NullTranslations, Translations

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "fa")
LOCALE_DIRECTORY = Path(__file__).resolve().parents[1] / "locales"

_current_language: ContextVar[str] = ContextVar("current_language", default=DEFAULT_LANGUAGE)


def resolve_language(value: str | None) -> str:
    """Choose the supported language with the highest Accept-Language weight."""
    candidates: list[tuple[float, int, str]] = []
    aliases = {"english": "en", "persian": "fa", "farsi": "fa"}
    for position, item in enumerate((value or DEFAULT_LANGUAGE).split(",")):
        tag, *parameters = item.strip().casefold().split(";")
        quality = 1.0
        for parameter in parameters:
            name, separator, weight = parameter.strip().partition("=")
            if name != "q" or not separator:
                continue
            try:
                quality = float(weight)
            except ValueError:
                quality = 0.0
        language = aliases.get(tag, tag.split("-", 1)[0])
        if language in SUPPORTED_LANGUAGES and 0 < quality <= 1:
            candidates.append((quality, -position, language))
    return max(candidates)[2] if candidates else DEFAULT_LANGUAGE


@cache
def get_translations(language: str) -> Translations | NullTranslations:
    """Load and cache one compiled gettext catalog."""
    return Translations.load(
        dirname=LOCALE_DIRECTORY,
        locales=[resolve_language(language)],
        domain="messages",
    )


def get_language() -> str:
    """Return the request-local negotiated base language."""
    return _current_language.get()


def translate(message: str, language: str | None = None) -> str:
    """Translate a message using an explicit or request-local language."""
    selected = resolve_language(language) if language is not None else _current_language.get()
    return get_translations(selected).gettext(message)


def _(message: str) -> str:
    """Provide the conventional gettext shorthand for application code."""
    return translate(message)


def set_language(value: str | None) -> Token[str]:
    """Set the current request language and return a reset token."""
    return _current_language.set(resolve_language(value))


def reset_language(token: Token[str]) -> None:
    """Restore the language context that preceded a request."""
    _current_language.reset(token)


@contextmanager
def use_language(value: str | None) -> Iterator[str]:
    """Temporarily activate a language outside HTTP middleware."""
    language = resolve_language(value)
    token = _current_language.set(language)
    try:
        yield language
    finally:
        _current_language.reset(token)
