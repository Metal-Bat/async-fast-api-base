"""Behavior contract for bounded BPMS operational telemetry."""

from datetime import timedelta
from unittest.mock import Mock

from core.bpms_observability import BPMSOperationalSnapshot, BPMSTelemetry
from utils.date_utils import get_datetime_utc


def _telemetry() -> tuple[BPMSTelemetry, dict[str, Mock], Mock, Mock]:
    instruments: dict[str, Mock] = {}
    meter = Mock()

    def instrument(name: str, **_kwargs) -> Mock:
        instruments[name] = Mock()
        return instruments[name]

    meter.create_counter.side_effect = instrument
    meter.create_histogram.side_effect = instrument
    meter.create_gauge.side_effect = instrument
    tracer = Mock()
    logger = Mock()
    return BPMSTelemetry(meter=meter, tracer=tracer, logger=logger), instruments, tracer, logger


def test_snapshot_records_current_backlog_and_age_with_bounded_labels() -> None:
    telemetry, instruments, _, _ = _telemetry()
    snapshot = BPMSOperationalSnapshot(
        cartable_backlog={"OPEN": 4, "IN_PROGRESS": 2, "UNKNOWN": 99},
        wait_oldest_age_seconds={"HUMAN": 90.0, "EVENT": 45.0, "SECRET": 999.0},
        outbox_pending=3,
        outbox_oldest_age_seconds=12.5,
        compensation_backlog={"PENDING": 2, "FAILED": 1, "HIDDEN": 8},
    )

    telemetry.record_snapshot(snapshot)

    assert instruments["bpms.cartable.backlog"].set.call_args_list == [
        ((4,), {"attributes": {"status": "OPEN"}}),
        ((2,), {"attributes": {"status": "IN_PROGRESS"}}),
    ]
    assert instruments["bpms.wait.oldest_age"].set.call_args_list == [
        ((90.0,), {"attributes": {"wait_kind": "HUMAN"}}),
        ((45.0,), {"attributes": {"wait_kind": "EVENT"}}),
    ]
    instruments["bpms.outbox.backlog"].set.assert_called_once_with(3)
    instruments["bpms.outbox.oldest_age"].set.assert_called_once_with(12.5)
    assert instruments["bpms.compensation.backlog"].set.call_args_list == [
        ((2,), {"attributes": {"status": "PENDING"}}),
        ((1,), {"attributes": {"status": "FAILED"}}),
    ]


def test_process_events_record_latency_retry_failure_and_compensation() -> None:
    telemetry, instruments, _, _ = _telemetry()
    ended_at = get_datetime_utc()
    process_started_at = ended_at - timedelta(seconds=12)
    step_started_at = ended_at - timedelta(seconds=3)

    telemetry.record_process_event(
        "step.retry_started",
        occurred_at=ended_at,
        process_started_at=process_started_at,
        step_started_at=step_started_at,
        wait_kind="BACKGROUND",
    )
    telemetry.record_process_event(
        "step.failed",
        occurred_at=ended_at,
        process_started_at=process_started_at,
        step_started_at=step_started_at,
        wait_kind="BACKGROUND",
    )
    telemetry.record_process_event(
        "process.failed",
        occurred_at=ended_at,
        process_started_at=process_started_at,
    )
    telemetry.record_process_event(
        "compensation.completed",
        occurred_at=ended_at,
        process_started_at=process_started_at,
    )

    instruments["bpms.retry"].add.assert_called_once_with(1, attributes={"component": "step"})
    instruments["bpms.failure"].add.assert_any_call(1, attributes={"component": "step"})
    instruments["bpms.failure"].add.assert_any_call(1, attributes={"component": "process"})
    instruments["bpms.step.duration"].record.assert_called_once_with(
        3.0,
        attributes={"outcome": "FAILED", "wait_kind": "BACKGROUND"},
    )
    instruments["bpms.process.duration"].record.assert_called_once_with(
        12.0, attributes={"outcome": "FAILED"}
    )
    instruments["bpms.compensation"].add.assert_called_once_with(
        1, attributes={"outcome": "COMPLETED"}
    )


def test_wait_outbox_cleanup_and_failure_signals_exclude_sensitive_values() -> None:
    telemetry, instruments, tracer, logger = _telemetry()
    now = get_datetime_utc()

    telemetry.record_timer(now - timedelta(seconds=4), now, kind="DELAY", outcome="FIRED")
    telemetry.record_event_wait(now - timedelta(seconds=8), now, outcome="CONSUMED")
    telemetry.record_outbox_retry()
    telemetry.record_attachment_cleanup(5, outcome="DELETED")
    telemetry.log_failure("outbox", "publish_failed", ConnectionError("secret-token"))
    telemetry.start_span("scheduler.snapshot", component="scheduler")

    instruments["bpms.timer.lag"].record.assert_called_once_with(
        4.0, attributes={"kind": "DELAY", "outcome": "FIRED"}
    )
    instruments["bpms.event.wait"].record.assert_called_once_with(
        8.0, attributes={"outcome": "CONSUMED"}
    )
    instruments["bpms.retry"].add.assert_called_once_with(1, attributes={"component": "outbox"})
    instruments["bpms.attachment.cleanup"].add.assert_called_once_with(
        5, attributes={"outcome": "DELETED"}
    )
    assert logger.warning.call_args.args == ("bpms.operation_failed",)
    assert logger.warning.call_args.kwargs == {
        "component": "outbox",
        "signal": "publish_failed",
        "error_type": "ConnectionError",
    }
    assert "secret-token" not in repr(logger.warning.call_args)
    tracer.start_as_current_span.assert_called_once_with(
        "bpms.scheduler.snapshot", attributes={"bpms.component": "scheduler"}
    )
