"""Client release precedence and trusted identity contract."""

import pytest

from apps.clients.domain.contracts import (
    ClientContext,
    ClientTarget,
    ClientVersion,
    ReleaseRange,
    matches_client_targets,
)


def test_numeric_release_order_prereleases_and_ignored_build_metadata() -> None:
    assert ClientVersion.parse("2.9") < ClientVersion.parse("2.10")
    assert ClientVersion.parse("2.10-rc.2") < ClientVersion.parse("2.10-rc.10")
    assert ClientVersion.parse("2.10-rc.10") < ClientVersion.parse("2.10")
    assert ClientVersion.parse("2.10+desktop.5") == ClientVersion.parse("2.10+desktop.6")
    assert ClientVersion.parse("2.10.0") == ClientVersion.parse("2.10")


@pytest.mark.parametrize("value", ["", "latest", "2", "2.01", "2.9.*", "2.10-"])
def test_invalid_release_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        ClientVersion.parse(value)


def test_version_range_is_inclusive_lower_and_exclusive_upper() -> None:
    target = ReleaseRange("2.10", "3.0")
    assert not target.contains("2.9")
    assert target.contains("2.10")
    assert target.contains("2.11-rc.1")
    assert not target.contains("3.0")
    assert not target.contains(None)
    with pytest.raises(ValueError):
        ReleaseRange("3.0", "2.10")


def test_legacy_context_cannot_satisfy_restricted_client_policy() -> None:
    assert ClientContext.legacy().client_id is None
    assert ClientContext.legacy().trusted is False


def test_restricted_start_requires_trusted_registered_identity_and_release() -> None:
    from uuid import UUID

    desktop = UUID(int=1)
    targets = (ClientTarget(desktop, ReleaseRange("2.10", "3.0")),)
    trusted = ClientContext(
        client_id=desktop,
        kind="DESKTOP",
        release="2.10",
        trusted=True,
    )
    public = ClientContext(
        client_id=desktop,
        kind="DESKTOP",
        release="2.10",
        trusted=False,
    )
    android = ClientContext(
        client_id=UUID(int=2),
        kind="ANDROID",
        release="2.10",
        trusted=True,
    )
    assert matches_client_targets(targets, trusted)
    assert not matches_client_targets(targets, public)
    assert not matches_client_targets(targets, android)
    assert not matches_client_targets(targets, ClientContext.legacy())
    assert not matches_client_targets(
        targets,
        ClientContext(
            client_id=desktop,
            kind="DESKTOP",
            release="2.9",
            trusted=True,
        ),
    )
    assert matches_client_targets((), ClientContext.legacy())
