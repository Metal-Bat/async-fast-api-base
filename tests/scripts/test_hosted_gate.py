"""Hosted provisioning cannot overwrite local configuration or accept a mutable peer ref."""

import pytest
from scripts.hosted_gate import validate_hosted_environment


@pytest.mark.parametrize(
    "change",
    [
        {"GITHUB_ACTIONS": "false"},
        {"RUNNER_ENVIRONMENT": "self-hosted"},
        {"PEER_SHA": "main"},
        {"GITHUB_WORKSPACE": "/other"},
    ],
)
def test_hosted_setup_refuses_unowned_runner_or_peer(tmp_path, change):
    environment = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "GITHUB_WORKSPACE": str(tmp_path),
        "PEER_SHA": "a" * 40,
    }
    with pytest.raises(ValueError):
        validate_hosted_environment(tmp_path, environment | change)


def test_hosted_setup_refuses_existing_backend_env_before_overwrite(tmp_path):
    (tmp_path / ".envs").mkdir()
    path = tmp_path / ".envs/.backend"
    path.write_text("existing operator configuration")
    with pytest.raises(ValueError):
        validate_hosted_environment(
            tmp_path,
            {
                "GITHUB_ACTIONS": "true",
                "RUNNER_ENVIRONMENT": "github-hosted",
                "GITHUB_WORKSPACE": str(tmp_path),
                "PEER_SHA": "a" * 40,
            },
        )
    assert path.read_text() == "existing operator configuration"
