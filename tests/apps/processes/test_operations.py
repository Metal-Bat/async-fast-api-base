"""Operational snapshot behavior for the BPMS scheduler."""

from datetime import timedelta

from apps.processes.application.operations import build_operational_snapshot
from utils.date_utils import get_datetime_utc


def test_snapshot_projects_only_aggregate_counts_and_ages() -> None:
    now = get_datetime_utc()

    snapshot = build_operational_snapshot(
        now=now,
        cartable_rows=[("OPEN", 4), ("IN_PROGRESS", 2)],
        wait_rows=[
            ("HUMAN", now - timedelta(seconds=90)),
            ("EVENT", now - timedelta(seconds=45)),
        ],
        outbox_row=(3, now - timedelta(seconds=12)),
        compensation_rows=[("PENDING", 2), ("FAILED", 1)],
    )

    assert snapshot.cartable_backlog == {"OPEN": 4, "IN_PROGRESS": 2}
    assert snapshot.wait_oldest_age_seconds == {"HUMAN": 90.0, "EVENT": 45.0}
    assert snapshot.outbox_pending == 3
    assert snapshot.outbox_oldest_age_seconds == 12.0
    assert snapshot.compensation_backlog == {"PENDING": 2, "FAILED": 1}
