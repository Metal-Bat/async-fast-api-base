"""Real-service verification refuses any database it did not just provision."""

import pytest
from scripts.transfer_services import remove_owned_container, transfer_services


@pytest.mark.parametrize(
    "environment",
    [
        {"POSTGRES_DB": "shared", "FLOW_TEST_OWNED_DATABASE": "shared"},
        {"POSTGRES_DB": "bpms_flow_one", "FLOW_TEST_OWNED_DATABASE": "bpms_flow_other"},
        {
            "POSTGRES_DB": "bpms_flow_one",
            "FLOW_TEST_OWNED_DATABASE": "bpms_flow_one",
            "POSTGRES_HOST": "remote",
        },
    ],
)
def test_transfer_harness_refuses_unowned_or_remote_database(environment):
    with (
        pytest.raises(ValueError, match="owned local"),
        transfer_services(environment),
    ):
        pytest.fail("Unsafe services must never start")


def test_transfer_cleanup_refuses_changed_container_ownership(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "scripts.transfer_services._docker", lambda *args: '{"id":"changed","owner":"other"}'
    )
    monkeypatch.setattr(
        "scripts.transfer_services.subprocess.run", lambda *args, **kwargs: calls.append(args)
    )
    with pytest.raises(RuntimeError, match="ownership"):
        remove_owned_container("expected-id", "expected-owner")
    assert calls == []
