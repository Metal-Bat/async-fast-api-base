"""Process command matrix and public route contract."""

import pytest

from apps.processes.domain.state import transition
from main import app


@pytest.mark.parametrize(
    ("source", "command", "target"),
    [
        ("RUNNING", "wait", "WAITING"),
        ("RUNNING", "pause", "PAUSED"),
        ("WAITING", "resume", "RUNNING"),
        ("PAUSED", "resume", "RUNNING"),
        ("FAILED", "retry", "RUNNING"),
        ("RUNNING", "complete", "COMPLETED"),
        ("WAITING", "cancel", "CANCELLED"),
    ],
)
def test_process_command_matrix(source: str, command: str, target: str) -> None:
    assert transition(source, command) == target  # ty:ignore[invalid-argument-type]


@pytest.mark.parametrize("status", ["COMPLETED", "CANCELLED"])
def test_terminal_processes_reject_every_command(status: str) -> None:
    for command in ("wait", "resume", "pause", "complete", "fail", "cancel", "retry"):
        with pytest.raises(ValueError, match="invalid"):
            transition(status, command)  # ty:ignore[invalid-argument-type]


def test_process_routes_expose_idempotent_control_commands() -> None:
    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/processes/{ref_id}"]
    for command in ("resume", "pause", "cancel", "retry", "timeout"):
        assert "post" in paths[f"/api/v1/processes/{{ref_id}}/{command}"]
