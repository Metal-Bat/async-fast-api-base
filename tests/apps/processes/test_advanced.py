"""State-table and randomized invariant tests for advanced execution."""

import random

from apps.processes.domain.advanced import (
    CompensationItem,
    decide_join,
    pending_compensations,
    visit_allowed,
)


def test_all_join_releases_once_all_branches_arrive() -> None:
    assert decide_join(("ARRIVED", "WAITING", "ARRIVED"), "ARRIVE") == "WAIT"
    assert decide_join(("ARRIVED", "ARRIVED", "ARRIVED"), "ARRIVE") == "RELEASE"
    assert decide_join(("ARRIVED", "CANCELLED"), "ARRIVE") == "RELEASE"
    assert decide_join(("ARRIVED", "CANCELLED"), "FAIL") == "FAIL"
    assert decide_join(("ARRIVED", "FAILED"), "ARRIVE") == "FAIL"


def test_loop_visits_are_bounded_independently_from_retries() -> None:
    assert visit_allowed(2, 3)
    assert not visit_allowed(3, 3)
    assert visit_allowed(50, None)


def test_compensation_resumes_in_reverse_order_without_completed_reversals() -> None:
    items = [
        CompensationItem(1, "a", "COMPLETED"),
        CompensationItem(2, "b", "FAILED"),
        CompensationItem(3, "c"),
    ]
    assert [item.source_id for item in pending_compensations(items)] == ["c", "b"]


def test_random_join_arrival_order_cannot_release_early() -> None:
    randomizer = random.Random(15015)
    for branch_count in range(2, 20):
        for _ in range(20):
            arrived = [False] * branch_count
            order = list(range(branch_count))
            randomizer.shuffle(order)
            releases = 0
            for index in order:
                arrived[index] = True
                decision = decide_join(
                    tuple("ARRIVED" if value else "ACTIVE" for value in arrived), "ARRIVE"
                )
                releases += decision == "RELEASE"
                assert (decision == "RELEASE") is all(arrived)
            assert releases == 1
