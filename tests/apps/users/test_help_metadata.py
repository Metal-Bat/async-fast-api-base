"""Release compatibility accepts only bounded metadata, never content or tracking payloads."""

import pytest
from pydantic import ValidationError

from apps.users.domain.help_state import HelpAction, HelpReleaseMetadata


def test_metadata_does_not_accept_html_or_event_payloads():
    release = HelpReleaseMetadata(
        release_key="synthetic-acceptance",
        items=[{"help_key": "requests.start", "revision": "1", "locales": ["en", "fa"]}],
    )
    assert release.items[0].locales == ["en", "fa"]
    with pytest.raises(ValidationError):
        HelpReleaseMetadata(
            release_key="synthetic",
            items=[
                {
                    "help_key": "requests.start",
                    "revision": "1",
                    "locales": ["en"],
                    "html": "<b>Not metadata</b>",
                }
            ],
        )
    with pytest.raises(ValidationError):
        HelpAction.model_validate(
            {"help_key": "requests.start", "revision": "1", "locale": "en", "actor_id": "other"}
        )


@pytest.mark.parametrize(
    "items",
    [
        [{"help_key": "../unsafe", "revision": "1", "locales": ["en"]}],
        [{"help_key": "requests.start", "revision": "1", "locales": ["en", "en"]}],
        [{"help_key": "requests.start", "revision": "1", "locales": ["en"]}] * 2,
    ],
)
def test_release_keys_and_locales_are_distinct_and_safe(items):
    with pytest.raises(ValidationError):
        HelpReleaseMetadata(release_key="synthetic", items=items)


def test_help_release_loader_is_bounded_and_compatible_with_missing_metadata(tmp_path, monkeypatch):
    from apps.users.data.help_release import load_help_release
    from core.settings import settings

    monkeypatch.setattr(settings, "HELP_RELEASE_METADATA_FILE", None)
    assert load_help_release() is None
    path = tmp_path / "metadata.json"
    monkeypatch.setattr(settings, "HELP_RELEASE_METADATA_FILE", path)
    assert load_help_release() is None
    path.write_bytes(b" " * 65_537)
    assert load_help_release() is None
    path.write_text('{"schema_version":1,"release_key":"synthetic","items":[]}')
    release = load_help_release()
    assert release is not None and release.release_key == "synthetic"
    path.write_text('{"schema_version":1,"release_key":"synthetic","items":[],"html":"forbidden"}')
    assert load_help_release() is None
