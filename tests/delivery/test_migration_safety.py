"""Destructive migration acceptance rejects unowned/shared database targets."""

import pytest
from tests.integration.test_migrations import require_disposable_database


@pytest.mark.parametrize(
    "name,owned", [("application", "application"), ("bpms_flow_" + "a" * 32, "other")]
)
def test_migration_roundtrip_refuses_non_owned_database(monkeypatch, name, owned):
    monkeypatch.setenv("POSTGRES_DB", name)
    monkeypatch.setenv("FLOW_TEST_OWNED_DATABASE", owned)
    with pytest.raises(RuntimeError, match="owned disposable"):
        require_disposable_database()
