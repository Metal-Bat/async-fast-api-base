"""Explicit work-item lifecycle rules."""

from typing import Literal

type WorkItemStatus = Literal[
    "OPEN", "CLAIMED", "IN_PROGRESS", "COMPLETED", "REJECTED", "RETURNED", "CANCELLED", "EXPIRED"
]
type WorkItemAction = Literal[
    "claim", "release", "start", "complete", "reject", "return", "cancel", "expire"
]

_TRANSITIONS: dict[tuple[WorkItemStatus, WorkItemAction], WorkItemStatus] = {
    ("OPEN", "claim"): "CLAIMED",
    ("OPEN", "cancel"): "CANCELLED",
    ("OPEN", "expire"): "EXPIRED",
    ("CLAIMED", "release"): "OPEN",
    ("CLAIMED", "start"): "IN_PROGRESS",
    ("CLAIMED", "complete"): "COMPLETED",
    ("CLAIMED", "reject"): "REJECTED",
    ("CLAIMED", "return"): "RETURNED",
    ("CLAIMED", "cancel"): "CANCELLED",
    ("CLAIMED", "expire"): "EXPIRED",
    ("IN_PROGRESS", "release"): "OPEN",
    ("IN_PROGRESS", "complete"): "COMPLETED",
    ("IN_PROGRESS", "reject"): "REJECTED",
    ("IN_PROGRESS", "return"): "RETURNED",
    ("IN_PROGRESS", "cancel"): "CANCELLED",
    ("IN_PROGRESS", "expire"): "EXPIRED",
}


def transition(status: WorkItemStatus, action: WorkItemAction) -> WorkItemStatus:
    """Return the only valid target state for a lifecycle action."""
    try:
        return _TRANSITIONS[(status, action)]
    except KeyError as exc:
        raise ValueError(f"Action {action} is invalid from {status}") from exc
