"""Tests for task request and schedule DTO validation."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from apps.tasks.domain.dto import ManualTaskDTO, PeriodicTaskCreateDTO


def test_interval_schedule_requires_interval() -> None:
    with pytest.raises(ValueError):
        PeriodicTaskCreateDTO(name="test", task_name="system.ping", schedule_type="interval")


def test_clocked_schedule_is_one_off() -> None:
    with pytest.raises(ValueError):
        PeriodicTaskCreateDTO(
            name="test",
            task_name="system.ping",
            schedule_type="clocked",
            clocked_at=datetime.now(UTC),
            one_off=False,
        )


def test_task_requests_cannot_supply_broker_idempotency_headers() -> None:
    with pytest.raises(ValidationError):
        ManualTaskDTO.model_validate(
            {"task_name": "system.ping", "idempotency_key": "caller-controlled"}
        )
    with pytest.raises(ValidationError):
        PeriodicTaskCreateDTO.model_validate(
            {
                "name": "test",
                "task_name": "system.ping",
                "schedule_type": "interval",
                "interval_seconds": 60,
                "headers": {"idempotency_key": "caller-controlled"},
            }
        )


def test_schedule_dto_accepts_valid_clocked_schedule_and_requires_time() -> None:
    now = datetime.now(UTC)
    valid = PeriodicTaskCreateDTO(
        name="once",
        task_name="system.ping",
        schedule_type="clocked",
        clocked_at=now,
        one_off=True,
    )
    assert valid.clocked_at == now
    with pytest.raises(ValidationError, match="clocked_at"):
        PeriodicTaskCreateDTO(
            name="once", task_name="system.ping", schedule_type="clocked", one_off=True
        )
