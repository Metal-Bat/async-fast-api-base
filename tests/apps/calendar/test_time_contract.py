"""Gregorian dates, explicit timezone offsets and bounded calendar windows."""

from typing import Any

import pytest
from pydantic import ValidationError

from apps.calendar.domain.dto import CalendarInput, CalendarQuery


def test_calendar_preserves_all_day_dates_and_rejects_unsupported_calendar():
    values: dict[str, Any] = {
        "command_key": "one",
        "title": "Meeting",
        "schedule": {
            "kind": "all_day",
            "start_date": "2028-02-29",
            "end_date": "2028-03-01",
            "timezone": "Asia/Dubai",
        },
    }
    event = CalendarInput.model_validate(values)
    assert event.schedule.model_dump(mode="json")["start_date"] == "2028-02-29"
    with pytest.raises(ValidationError):
        CalendarInput.model_validate(values | {"calendar": "persian"})
    with pytest.raises(ValidationError):
        CalendarInput.model_validate(
            values | {"schedule": values["schedule"] | {"end_date": "2028-02-29"}}
        )


def test_explicit_offsets_disambiguate_fold_and_reject_gap_or_wrong_zone():
    values: dict[str, Any] = {
        "command_key": "one",
        "title": "Meeting",
        "schedule": {
            "kind": "timed",
            "start_at": "2026-11-01T01:15:00-04:00",
            "end_at": "2026-11-01T01:45:00-04:00",
            "timezone": "America/New_York",
        },
    }
    assert CalendarInput.model_validate(values).schedule.kind == "timed"
    for replacement in (
        {"start_at": "2026-03-08T02:15:00-05:00", "end_at": "2026-03-08T03:45:00-04:00"},
        {"start_at": "2026-11-01T01:15:00"},
        {"timezone": "invalid"},
    ):
        with pytest.raises(ValidationError):
            CalendarInput.model_validate(values | {"schedule": values["schedule"] | replacement})


def test_calendar_window_and_reminder_configuration_are_bounded():
    assert (
        CalendarQuery.model_validate({"start_date": "2026-10-01", "end_date": "2026-11-01"}).size
        == 20
    )
    with pytest.raises(ValidationError):
        CalendarQuery.model_validate({"start_date": "2026-01-01", "end_date": "2027-01-01"})
    with pytest.raises(ValidationError):
        CalendarInput.model_validate(
            {
                "command_key": "one",
                "title": "Meeting",
                "reminder_offsets": [0, 0],
                "schedule": {
                    "kind": "all_day",
                    "start_date": "2026-10-01",
                    "end_date": "2026-10-02",
                    "timezone": "UTC",
                },
            }
        )


def test_calendar_http_routes_are_authenticated_private_and_separate_derived_deadlines():
    from main import app

    paths = app.openapi()["paths"]
    for path, method in (
        ("/api/v1/calendar/events/search", "post"),
        ("/api/v1/calendar/events/{ref_id}", "put"),
        ("/api/v1/calendar/events/{ref_id}/history", "post"),
    ):
        operation = paths[path][method]
        assert operation["security"]
        assert "Cache-Control" in operation["responses"]["200"]["headers"]
