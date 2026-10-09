"""Typed self settings reject privilege input and preserve omitted groups."""

import pytest
from pydantic import ValidationError

from apps.users.domain.preferences import PreferencesPatch, UserPreferences


def test_preference_defaults_and_group_patch_semantics():
    defaults = UserPreferences()
    assert defaults.locale.calendar == "gregory"
    assert defaults.appearance.theme_key == "blue"
    patch = PreferencesPatch(ref_id="current", appearance={"theme_mode": "dark"})
    assert patch.model_dump(exclude_unset=True) == {
        "ref_id": "current",
        "appearance": {"theme_mode": "dark"},
    }
    reset = PreferencesPatch(ref_id="current", appearance=None)
    assert reset.model_dump(exclude_unset=True) == {"ref_id": "current", "appearance": None}


@pytest.mark.parametrize(
    "payload",
    [
        {"actor_id": "other"},
        {"is_superuser": True},
        {"appearance": {"theme_key": "unknown"}},
        {"locale": {"timezone": "Not/AZone"}},
        {"locale": {"calendar": "persian"}},
        {"appearance": {"theme_mode": None}},
        {"workspace": {"page_size": 101}},
    ],
)
def test_preferences_reject_invalid_or_privileged_input(payload):
    with pytest.raises(ValidationError):
        PreferencesPatch(ref_id="current", **payload)
