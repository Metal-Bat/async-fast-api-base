"""Low-cardinality operational telemetry for the BPMS runtime."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
from opentelemetry import metrics, trace

_CARTABLE_STATUSES = frozenset({"OPEN", "CLAIMED", "IN_PROGRESS"})
_WAIT_KINDS = frozenset({"HUMAN", "EVENT", "TIMER", "BACKGROUND"})
_COMPENSATION_STATUSES = frozenset({"PENDING", "RUNNING", "EXECUTING", "FAILED"})
_COMPONENTS = frozenset(
    {"process", "step", "timer", "event", "outbox", "attachment", "compensation", "scheduler"}
)
_SPAN_OPERATIONS = frozenset({"scheduler.snapshot"})
_FAILURE_SIGNALS = frozenset(
    {
        "publish_failed",
        "snapshot_failed",
        "timer_failed",
        "process_failed",
        "step_failed",
        "compensation_failed",
    }
)


@dataclass(frozen=True, slots=True)
class BPMSOperationalSnapshot:
    """Current operational queues and their oldest actionable age."""

    cartable_backlog: dict[str, int] = field(default_factory=dict)
    wait_oldest_age_seconds: dict[str, float] = field(default_factory=dict)
    outbox_pending: int = 0
    outbox_oldest_age_seconds: float = 0.0
    compensation_backlog: dict[str, int] = field(default_factory=dict)


class BPMSTelemetry:
    """Emit BPMS metrics, spans, and redacted failure logs through OpenTelemetry."""

    def __init__(self, *, meter: Any, tracer: Any, logger: Any) -> None:
        self._tracer = tracer
        self._logger = logger
        self._process_duration = meter.create_histogram(
            "bpms.process.duration", unit="s", description="Terminal process duration."
        )
        self._step_duration = meter.create_histogram(
            "bpms.step.duration", unit="s", description="Terminal step execution duration."
        )
        self._wait_oldest_age = meter.create_gauge(
            "bpms.wait.oldest_age", unit="s", description="Age of the oldest active wait."
        )
        self._cartable_backlog = meter.create_gauge(
            "bpms.cartable.backlog", unit="{item}", description="Active human-work backlog."
        )
        self._retry = meter.create_counter(
            "bpms.retry", unit="{retry}", description="Recoverable BPMS retries."
        )
        self._failure = meter.create_counter(
            "bpms.failure", unit="{failure}", description="Terminal BPMS failures."
        )
        self._timer_lag = meter.create_histogram(
            "bpms.timer.lag", unit="s", description="Scheduled action delay after its due time."
        )
        self._event_wait = meter.create_histogram(
            "bpms.event.wait", unit="s", description="Time an event subscription remained active."
        )
        self._outbox_backlog = meter.create_gauge(
            "bpms.outbox.backlog", unit="{message}", description="Unpublished outbox messages."
        )
        self._outbox_oldest_age = meter.create_gauge(
            "bpms.outbox.oldest_age",
            unit="s",
            description="Age of the oldest unpublished outbox message.",
        )
        self._attachment_cleanup = meter.create_counter(
            "bpms.attachment.cleanup",
            unit="{upload}",
            description="Abandoned upload cleanup outcomes.",
        )
        self._compensation = meter.create_counter(
            "bpms.compensation", unit="{operation}", description="Compensation outcomes."
        )
        self._compensation_backlog = meter.create_gauge(
            "bpms.compensation.backlog",
            unit="{operation}",
            description="Outstanding compensation work.",
        )

    def record_snapshot(self, snapshot: BPMSOperationalSnapshot) -> None:
        """Publish an absolute snapshot while dropping unknown label values."""
        for status, count in snapshot.cartable_backlog.items():
            if status in _CARTABLE_STATUSES:
                self._cartable_backlog.set(count, attributes={"status": status})
        for wait_kind, age in snapshot.wait_oldest_age_seconds.items():
            if wait_kind in _WAIT_KINDS:
                self._wait_oldest_age.set(max(0.0, age), attributes={"wait_kind": wait_kind})
        self._outbox_backlog.set(max(0, snapshot.outbox_pending))
        self._outbox_oldest_age.set(max(0.0, snapshot.outbox_oldest_age_seconds))
        for status, count in snapshot.compensation_backlog.items():
            if status in _COMPENSATION_STATUSES:
                self._compensation_backlog.set(count, attributes={"status": status})

    def record_process_event(
        self,
        event_type: str,
        *,
        occurred_at: datetime,
        process_started_at: datetime,
        step_started_at: datetime | None = None,
        wait_kind: str | None = None,
    ) -> None:
        """Translate the bounded process event catalog into counters and durations."""
        if event_type.endswith(".retry") or event_type == "step.retry_started":
            component = "timer" if event_type.startswith("timer.") else "step"
            self._retry.add(1, attributes={"component": component})
        if event_type in {"step.failed", "step.timed_out"}:
            self._failure.add(1, attributes={"component": "step"})
        elif event_type == "process.failed":
            self._failure.add(1, attributes={"component": "process"})
        elif event_type == "timer.failed":
            self._failure.add(1, attributes={"component": "timer"})
        elif event_type == "compensation.failed":
            self._failure.add(1, attributes={"component": "compensation"})

        step_outcomes = {
            "step.completed": "COMPLETED",
            "step.failed": "FAILED",
            "step.timed_out": "TIMED_OUT",
        }
        if step_started_at is not None and event_type in step_outcomes:
            attributes = {
                "outcome": step_outcomes[event_type],
                "wait_kind": wait_kind if wait_kind in _WAIT_KINDS else "NONE",
            }
            self._step_duration.record(
                self._seconds(step_started_at, occurred_at), attributes=attributes
            )

        process_outcomes = {
            "process.completed": "COMPLETED",
            "process.failed": "FAILED",
            "process.cancelled": "CANCELLED",
            "process.compensated": "COMPENSATED",
        }
        if event_type in process_outcomes:
            self._process_duration.record(
                self._seconds(process_started_at, occurred_at),
                attributes={"outcome": process_outcomes[event_type]},
            )

        if event_type.startswith("compensation."):
            outcome = event_type.removeprefix("compensation.").upper()
            if outcome in {"STARTED", "COMPLETED", "FAILED"}:
                self._compensation.add(1, attributes={"outcome": outcome})

    def record_timer(
        self, due_at: datetime, observed_at: datetime, *, kind: str, outcome: str
    ) -> None:
        """Record scheduled-action lag using code-owned kind and outcome values."""
        safe_kind = kind if kind in {"DELAY", "DEADLINE", "RETRY", "ESCALATION"} else "OTHER"
        safe_outcome = outcome if outcome in {"FIRED", "FAILED", "LATE"} else "OTHER"
        self._timer_lag.record(
            self._seconds(due_at, observed_at),
            attributes={"kind": safe_kind, "outcome": safe_outcome},
        )

    def record_event_wait(
        self, registered_at: datetime, observed_at: datetime, *, outcome: str
    ) -> None:
        """Record an event subscription's active duration without its type or correlation key."""
        safe_outcome = outcome if outcome in {"CONSUMED", "EXPIRED", "CANCELLED"} else "OTHER"
        self._event_wait.record(
            self._seconds(registered_at, observed_at), attributes={"outcome": safe_outcome}
        )

    def record_outbox_retry(self) -> None:
        """Count a recoverable broker publication failure."""
        self._retry.add(1, attributes={"component": "outbox"})

    def record_attachment_cleanup(self, count: int, *, outcome: str) -> None:
        """Count deleted or failed cleanup candidates without storage identifiers."""
        safe_outcome = outcome if outcome in {"DELETED", "FAILED"} else "OTHER"
        self._attachment_cleanup.add(max(0, count), attributes={"outcome": safe_outcome})

    def start_span(self, operation: str, *, component: str) -> Any:
        """Start one code-owned operational span with bounded attributes."""
        if operation not in _SPAN_OPERATIONS or component not in _COMPONENTS:
            raise ValueError("Unsupported BPMS operational span")
        return self._tracer.start_as_current_span(
            f"bpms.{operation}", attributes={"bpms.component": component}
        )

    def log_failure(self, component: str, signal: str, error: BaseException) -> None:
        """Log actionable failure metadata without exception text, payloads, or identifiers."""
        if component not in _COMPONENTS or signal not in _FAILURE_SIGNALS:
            raise ValueError("Unsupported BPMS operational failure signal")
        self._logger.warning(
            "bpms.operation_failed",
            component=component,
            signal=signal,
            error_type=type(error).__name__,
        )

    @staticmethod
    def _seconds(started_at: datetime, ended_at: datetime) -> float:
        return max(0.0, (ended_at - started_at).total_seconds())


bpms_telemetry = BPMSTelemetry(
    meter=metrics.get_meter("fast_api_sample.bpms"),
    tracer=trace.get_tracer("fast_api_sample.bpms"),
    logger=structlog.get_logger("fast_api_sample.bpms"),
)
