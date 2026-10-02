"""Tests for locale negotiation and translated public messages."""

from pathlib import Path

from babel.messages.pofile import read_po

from core.i18n import _, get_translations, resolve_language, use_language
from utils.errors import AuthError, CommonError, InfrastructureError, MediaError
from utils.localization import localize_error


def test_public_error_codes_are_globally_unique_and_localized() -> None:
    errors = [*CommonError, *AuthError, *MediaError, *InfrastructureError]
    numbers = [error.number for error in errors]
    assert len(numbers) == len(set(numbers))
    assert all(1000 <= number < 5000 for number in numbers)
    assert CommonError.NOT_FOUND.number == 1003
    assert AuthError.INVALID_CREDENTIALS.number == 2001
    assert MediaError.INVALID_IMAGE.number == 3002
    assert InfrastructureError.DATA_CONFLICT.number == 4002

    locale_root = Path(__file__).resolve().parents[2] / "src" / "locales"
    for language in ("en", "fa"):
        with (locale_root / language / "LC_MESSAGES" / "messages.po").open() as source:
            catalog = read_po(source)
        message_ids = {message.id for message in catalog if message.id}
        assert {error.text for error in errors} <= message_ids
        for error in errors:
            assert localize_error(error, language) == get_translations(language).gettext(error.text)


def test_language_negotiation_and_fallback() -> None:
    assert resolve_language("en;q=0.5,fa-IR;q=0.9") == "fa"
    assert resolve_language("PERSIAN") == "fa"
    assert resolve_language("fa;q=0,en") == "en"
    assert resolve_language("fa;q=invalid") == "en"
    assert resolve_language("../../unknown") == "en"
    assert localize_error(CommonError.NOT_FOUND, "de") == CommonError.NOT_FOUND.text


def test_gettext_shorthand_uses_request_local_language() -> None:
    with use_language("fa"):
        assert _("Resource not found.") == "مورد درخواستی یافت نشد."
    assert _("Resource not found.") == "Resource not found."
