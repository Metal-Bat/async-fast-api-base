"""Deterministic decisions shared by advanced-flow persistence and tests."""

from dataclasses import dataclass
from typing import Literal

type BranchState = Literal["ACTIVE", "WAITING", "ARRIVED", "CANCELLED", "FAILED"]
type CancelledBranchPolicy = Literal["ARRIVE", "FAIL"]
type JoinDecision = Literal["WAIT", "RELEASE", "FAIL"]


@dataclass(frozen=True, slots=True)
class CompensationItem:
    ordinal: int
    source_id: str
    status: Literal["PENDING", "RUNNING", "EXECUTING", "COMPLETED", "FAILED"] = "PENDING"


def decide_join(
    states: tuple[BranchState, ...], cancelled_policy: CancelledBranchPolicy
) -> JoinDecision:
    """Apply the ALL-join terminal table to one correlation scope."""
    if "FAILED" in states:
        return "FAIL"
    if "CANCELLED" in states and cancelled_policy == "FAIL":
        return "FAIL"
    arrived = {"ARRIVED", "CANCELLED"} if cancelled_policy == "ARRIVE" else {"ARRIVED"}
    return "RELEASE" if states and set(states) <= arrived else "WAIT"


def visit_allowed(completed_visits: int, max_visits: int | None) -> bool:
    """A retry keeps one visit; traversing an edge consumes the next bounded visit."""
    return max_visits is None or completed_visits < max_visits


def pending_compensations(items: list[CompensationItem]) -> list[CompensationItem]:
    """Resume incomplete reversals in strict reverse effect order."""
    return sorted(
        (item for item in items if item.status != "COMPLETED"),
        key=lambda item: (item.ordinal, item.source_id),
        reverse=True,
    )
