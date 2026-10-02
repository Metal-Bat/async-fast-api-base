"""Integration tests for Alembic migration round trips."""

import os
import subprocess

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_MIGRATION_INTEGRATION") != "1",
        reason="uses the configured disposable integration database",
    ),
]


def test_alembic_empty_upgrade_downgrade_upgrade_round_trip() -> None:
    """Build, remove, and rebuild the schema in a disposable configured database."""
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    subprocess.run(["alembic", "downgrade", "base"], check=True)
    subprocess.run(["alembic", "upgrade", "head"], check=True)
