"""Analytics accepts bounded civil-date windows, not SQL or chart-library payloads."""

from datetime import date

import pytest
from pydantic import ValidationError

from apps.reporting.domain.analytics import MetricQuery, metric_window


def test_dst_day_has_exact_utc_boundaries():
    query = MetricQuery(
        metric_key="submitted_requests",
        start_date=date(2026, 3, 8),
        end_date=date(2026, 3, 9),
        timezone="America/New_York",
    )
    start, end = metric_window(query)
    assert (end - start).total_seconds() == 23 * 3600
    assert start.hour == 5 and end.hour == 4


@pytest.mark.parametrize(
    "patch",
    [
        {"metric_key": "arbitrary_sql"},
        {"timezone": "unknown/zone"},
        {"dimension": "user_id"},
        {"sql": "SELECT private_data"},
        {"end_date": "2026-01-01"},
        {"end_date": "2028-01-01"},
    ],
)
def test_metric_queries_reject_unknown_or_excessive_work(patch):
    document = {
        "metric_key": "submitted_requests",
        "start_date": "2026-01-01",
        "end_date": "2026-02-01",
        **patch,
    }
    with pytest.raises(ValidationError):
        MetricQuery.model_validate(document)
