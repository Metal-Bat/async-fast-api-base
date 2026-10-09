"""Real-service verification refuses any database it did not just provision."""

import pytest
from scripts.transfer_services import transfer_services


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
    with pytest.raises(ValueError, match="owned local"), transfer_services(environment):
        pytest.fail("Unsafe services must never start")
