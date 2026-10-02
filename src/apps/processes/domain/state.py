"""Explicit process command and state-transition policy."""

from typing import Literal

type ProcessStatus = Literal[
    "RUNNING",
    "WAITING",
    "PAUSED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "COMPENSATING",
    "COMPENSATION_FAILED",
    "COMPENSATED",
]
type ProcessCommand = Literal[
    "wait",
    "resume",
    "pause",
    "complete",
    "fail",
    "cancel",
    "retry",
    "compensate",
]

_TRANSITIONS: dict[ProcessStatus, dict[ProcessCommand, ProcessStatus]] = {
    "RUNNING": {
        "wait": "WAITING",
        "pause": "PAUSED",
        "complete": "COMPLETED",
        "fail": "FAILED",
        "cancel": "CANCELLED",
    },
    "WAITING": {
        "resume": "RUNNING",
        "pause": "PAUSED",
        "fail": "FAILED",
        "cancel": "CANCELLED",
    },
    "PAUSED": {"resume": "RUNNING", "cancel": "CANCELLED"},
    "FAILED": {"retry": "RUNNING", "cancel": "CANCELLED", "compensate": "COMPENSATING"},
    "COMPLETED": {},
    "CANCELLED": {"compensate": "COMPENSATING"},
    "COMPENSATING": {},
    "COMPENSATION_FAILED": {"compensate": "COMPENSATING"},
    "COMPENSATED": {},
}


def transition(status: ProcessStatus, command: ProcessCommand) -> ProcessStatus:
    """Return the legal target state or reject the command deterministically."""
    try:
        return _TRANSITIONS[status][command]
    except KeyError as exc:
        raise ValueError(f"Command {command} is invalid for process state {status}") from exc
