---
tags: [operations]
---

# BPMS operational observability

BPMS application metrics use the `bpms.*` OpenTelemetry namespace. The scheduler records one
aggregate snapshot per leader tick; process events and owning operations record transitions and
durations. Application metrics flow through OTLP to the Collector's Prometheus exporter on port
8889. Jaeger remains the trace viewer.

## Signals and initial targets

These targets are the starting production objectives. Tune them only from measured traffic and
document the new value with the operational reason.

| Signal | Labels | Initial target and operator action |
| --- | --- | --- |
| `bpms.process.duration` | `outcome` | Track p50/p95/p99 by terminal outcome. Alert when completed p95 exceeds the workflow's agreed service target for 15 minutes. |
| `bpms.step.duration` | `outcome`, `wait_kind` | Track p95 for synchronous/background work separately from human/event waits. Investigate a sustained two-times increase from the seven-day baseline. |
| `bpms.wait.oldest_age` | `wait_kind` | Alert when background/timer age exceeds the owning timeout, or when human/event age exceeds its business deadline. Inspect the exact wait through authorized process APIs. |
| `bpms.cartable.backlog` | `status` | Alert on sustained growth for 30 minutes and on any item past its due time. Scale or reroute work through governed work-item operations. |
| `bpms.retry` | `component` | Alert when the five-minute retry rate is more than twice its seven-day baseline. Check provider, broker, timer, or handler health before retrying work. |
| `bpms.failure` | `component` | Page on any sharp terminal-failure increase; use the process timeline and trace correlation to diagnose the affected records. |
| `bpms.timer.lag` | `kind`, `outcome` | Target p95 below two scheduler polling intervals. Check scheduler leadership, database load, and automation workers when exceeded for 10 minutes. |
| `bpms.event.wait` | `outcome` | Track consumed/expired duration separately. Alert on an expiry-rate increase, then inspect adapter delivery and correlation configuration. |
| `bpms.outbox.backlog` | none | Target zero during steady state. Alert when positive for more than five minutes. |
| `bpms.outbox.oldest_age` | none | Target below two scheduler polling intervals. Check broker reachability and publisher confirmation failures when exceeded. |
| `bpms.attachment.cleanup` | `outcome` | Alert on failed cleanup; compare deleted volume with upload traffic and storage growth. |
| `bpms.compensation` | `outcome` | Page on `FAILED`; operator reconciliation is required before an ambiguous external reversal can resume. |
| `bpms.compensation.backlog` | `status` | Target no sustained `RUNNING`, `EXECUTING`, or `FAILED` work. Inspect the process timeline and governed recovery action. |

## Cardinality and redaction

Metric labels accept only code-owned component, status, outcome, wait-kind, and timer-kind values.
They never include process, request, step, user, workflow, task, attachment, connection, event type,
correlation key, error code, or storage identifiers. Unknown label values are dropped or collapsed
to `OTHER`.

The `bpms.scheduler.snapshot` span contains only `bpms.component=scheduler`. Existing scheduler,
outbox, Celery, FastAPI, SQLAlchemy, Redis, and S3 instrumentation carries trace correlation; no
business payload is added by this contract.

`bpms.operation_failed` logs contain only the bounded component/signal and exception class name.
They omit exception text and `exc_info`, because provider messages can contain URLs, credentials,
headers, form values, correlation material, or object keys. Use trace/request correlation and the
authorized domain timeline for record-level diagnosis.

## Failure behavior

Telemetry export and snapshot collection do not own domain state. A failed snapshot writes the
redacted `snapshot_failed` signal and the scheduler continues durable timer and outbox work. Metrics
may therefore have a collection gap during a database or Collector outage; PostgreSQL runtime state
and the append-only process timeline remain authoritative.
