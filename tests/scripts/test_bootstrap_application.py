"""Installation ownership and credentials are checked before connecting to services."""

import os
import stat

import pytest
from scripts.bootstrap_application import open_manifest, validate_demo_environment


@pytest.mark.parametrize("environment", ["production", "stage", "", "prod"])
def test_demo_refuses_non_development_environments(environment):
    with pytest.raises(ValueError, match="Demo"):
        validate_demo_environment(environment, "localhost", "bpms_demo_example", True)


@pytest.mark.parametrize(
    "host,database,enabled",
    [
        ("remote.invalid", "bpms_demo_example", True),
        ("localhost", "postgres", True),
        ("localhost", "bpms_demo_example", False),
    ],
)
def test_demo_requires_explicit_local_owned_database(host, database, enabled):
    with pytest.raises(ValueError, match="Demo"):
        validate_demo_environment("local", host, database, enabled)


def test_manifest_is_private_and_reuses_credentials(tmp_path):
    path = tmp_path / "installation.json"
    with open_manifest(path, database="bpms_demo_example", create=True) as first:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert first.accounts
        assert len({account.password for account in first.accounts}) == len(first.accounts)
    with open_manifest(path, database="bpms_demo_example", create=False) as second:
        assert first == second


def test_manifest_refuses_public_file_without_changing_it(tmp_path):
    path = tmp_path / "installation.json"
    path.write_text("private-input")
    path.chmod(0o644)
    with (
        pytest.raises(ValueError, match="private"),
        open_manifest(path, database="bpms_demo_example", create=False),
    ):
        pass
    assert path.read_text() == "private-input"


def test_manifest_refuses_symlink_and_wrong_database(tmp_path):
    target = tmp_path / "owned.json"
    with open_manifest(target, database="bpms_demo_example", create=True):
        pass
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with (
        pytest.raises((OSError, ValueError)),
        open_manifest(link, database="bpms_demo_example", create=False),
    ):
        pass
    with (
        pytest.raises(ValueError, match="database"),
        open_manifest(target, database="other", create=False),
    ):
        pass


def test_check_never_creates_missing_credentials(tmp_path):
    path = tmp_path / "missing.json"
    with (
        pytest.raises(FileNotFoundError),
        open_manifest(path, database="bpms_demo_example", create=False),
    ):
        pass
    assert not path.exists()


def test_manifest_refuses_multiple_hard_links(tmp_path):
    target = tmp_path / "owned.json"
    with open_manifest(target, database="bpms_demo_example", create=True):
        pass
    os.link(target, tmp_path / "second.json")
    with (
        pytest.raises(ValueError, match="private"),
        open_manifest(target, database="bpms_demo_example", create=False),
    ):
        pass
