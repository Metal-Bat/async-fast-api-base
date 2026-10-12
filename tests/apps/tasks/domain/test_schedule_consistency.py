from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from apps.tasks.domain.dtos.schedules import PeriodicTaskCreateDTO, PeriodicTaskDTO


def schedule(**changes):
    return {
        "name": "consistency",
        "task_name": "apps.tasks.ping",
        "schedule_type": "interval",
        "interval_seconds": 60,
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"start_at": datetime.fromisoformat("2026-01-01T00:00:00")},
        {"cron_minute": "*"},
        {"schedule_type": "crontab", "interval_seconds": None, "cron_minute": "80"},
        {
            "start_at": datetime(2026, 1, 2, tzinfo=UTC),
            "expires_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {
            "schedule_type": "clocked",
            "clocked_at": datetime.now(UTC) + timedelta(days=1),
            "one_off": True,
        },
    ],
)
def test_invalid_schedule_combinations(changes):
    with pytest.raises(ValidationError):
        PeriodicTaskCreateDTO.model_validate(schedule(**changes))


def test_retained_legacy_schedule_remains_readable():
    legacy = schedule(
        interval_seconds=None,
        ref_id="retained",
        created_at=datetime.now(UTC),
        updated_at=None,
        deleted_at=None,
        last_run_at=None,
        total_run_count=0,
    )
    assert PeriodicTaskDTO.model_validate(legacy).interval_seconds is None


@pytest.mark.parametrize("changes", [{"enabled": None}, {"interval_seconds": None}])
def test_update_rejects_null_nonnullable_values(changes):
    from apps.tasks.domain.dtos.schedules import PeriodicTaskUpdateDTO

    with pytest.raises(ValidationError):
        PeriodicTaskUpdateDTO.model_validate(changes)


@pytest.mark.parametrize(
    "values",
    [
        {"schedule_type": "interval", "interval_seconds": 60},
        {"schedule_type": "crontab", "interval_seconds": None, "cron_minute": "*/5"},
        {
            "schedule_type": "clocked",
            "interval_seconds": None,
            "clocked_at": datetime(2026, 12, 1, tzinfo=UTC),
            "one_off": True,
        },
    ],
)
def test_supported_schedule_variants_have_executable_examples(values):
    command = PeriodicTaskCreateDTO.model_validate(schedule(**values))
    assert PeriodicTaskCreateDTO.model_validate_json(command.model_dump_json()) == command


def test_nonfinite_interval_is_not_a_valid_new_schedule():
    with pytest.raises(ValidationError):
        PeriodicTaskCreateDTO.model_validate(schedule(interval_seconds=float("inf")))


@pytest.mark.parametrize(
    "args,kwargs,queue",
    [([1], {}, None), ([], {"unexpected": True}, None), ([], {}, "unconfigured-consistency-queue")],
)
def test_registered_dispatch_rejects_invalid_binding_or_queue(args, kwargs, queue):
    from apps.tasks.application.schedules import validate_dispatch
    from utils.exceptions import ValidationDetailsException

    with pytest.raises(ValidationDetailsException):
        validate_dispatch("system.ping", args, kwargs, queue)
