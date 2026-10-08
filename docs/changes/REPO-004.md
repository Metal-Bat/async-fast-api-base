# REPO-004 — Restore local cache and scheduler lifecycle

Backlog: REPO-004
Date: 2026-10-08
Area: deployment/celery/observability

## Summary

Bound local Dragonfly thread allocation, gate application startup on authenticated cache
health, defer scheduler cleanup during signal interruption, and restore SQL query tracing
with a supported SQLAlchemy dependency range.

## Why

The local cache exited because CPU-based allocation selected 12 threads requiring 3 GiB of
available memory. Redis connection and result callback failures followed in workers and beat.
Celery's signal handler called scheduler.close inside Runner.run, producing nested runner
errors. Separately, the SQLAlchemy instrumentor rejected installed SQLAlchemy 2.1.4.

## What Changed

- Cache image defaults to two threads through CACHE_THREADS, quotes the password, uses exec
  for signal delivery and sends startup errors to stderr. Existing named data volumes remain.
- Compose restarts cache unless stopped and checks authenticated PING. Backend, both worker
  services and scheduler wait for cache health. Later outages still use existing runtime retries.
- Scheduler close requests during an active loop defer cleanup to tick's finally block.
  Signal SystemExit propagates after unwinding; the runner and database pool close once.
- SQLAlchemy asyncio is constrained to >=2.0.54,<2.1 and uv.lock selects 2.0.54. Pagination's
  generic annotation matches the 2.0 typing contract; query behavior remains unchanged.
- Tests reproduce interrupting/non-interrupting close and verify a real SQL span in an isolated
  interpreter, avoiding process-global telemetry interference.

## Architecture

No architecture change. PostgreSQL outbox durability and Redis-backed Celery results remain;
no result suppression or instrumentation dependency-check bypass was introduced.

## Compatibility

No API, DTO, schema or migration changes. Existing cache credentials and volumes are preserved.
CACHE_THREADS is an optional cache-container setting, defaulting to two; each thread requires
at least 256 MiB of available memory. Rebuild cache and Python application images to install
both the startup command and locked dependency changes. Health gates apply at startup only.

## Validation

Commands executed:

- Focused scheduler/SQL instrumentation regressions failed before the fixes.
- `rtk proxy docker compose up -d --build --wait cache` — rebuilt cache is healthy with
  authenticated PING and remained healthy after the full gate.
- `rtk proxy mise run check` — PASS: 685 tests passed, 119 opt-in skips, one doctest and four
  disposable PostgreSQL workflow tests passed; lint, types, security and all applicable hooks pass.
- Explicit pre-commit checks for new untracked tests and journal files — PASS.
- A disposable reporting-worker container resolved cache and passed authenticated Celery result
  backend PING, unknown-result read and AsyncResult cleanup without publishing/consuming tasks.
- `rtk proxy graphify update .` — AST graph updated successfully outside sandbox process limits.
- `rtk proxy docker compose build backend` and a retry with
  `rtk proxy docker build --network host -f compose/backend/Dockerfile -t sample_backend .` failed:
  build containers could not resolve files.pythonhosted.org when fetching locked Python wheels.

Result: PARTIAL for application image deployment; the complete source quality gate passed.
Cache was recreated and left running. Reporting-worker connectivity used the existing application
image; the updated dependency is verified in the uv environment, not a newly built application
image. Rebuild/recreate application services after Docker package-download DNS is repaired.
Application workers have not been started and no pending business tasks were deliberately replayed.

## Backlog Impact

All existing unfinished tasks were reviewed; none besides this task existed.

Enabled: None

Blocked: None

Superseded: None. REPO-002's SQLAlchemy 2.1 selection is narrowed for instrumentation compatibility.

Conflicts: None

## References

Commit: None

Pull Request: None

Additional notes: [Dependency operations](../operations/dependencies.md),
[REPO-002](REPO-002.md), [OBS-002](OBS-002.md).
