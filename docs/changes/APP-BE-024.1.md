# APP-BE-024.1 — Register scheduler foreign key targets

Backlog: APP-BE-024.1
Date: 2026-10-17
Area: core/celery_scheduler

## Summary

Register the scheduler's required entity modules before any ORM flush so timer retry
events can resolve `BUSINESS_REQUEST` and other referenced tables.

## Why

A fresh Celery beat process imported process entities without their foreign key
targets. SQLAlchemy raised `NoReferencedTableError` during `ProcessEventService.append`
on each retry claim. This is Python metadata registration, not missing database DDL.
Tests importing the API first could conceal the missing startup imports.

## What Changed

- `src/core/celery_scheduler.py` explicitly imports forms, media, requests, step types,
  work groups and workflows entity modules at the existing composition boundary.
- `tests/core/test_celery_scheduler.py` starts an isolated interpreter with the Celery
  app and scheduler, then resolves every registered foreign key. The regression failed
  before the fix with missing `WORKFLOW_TRANSITION`; an intermediate check also exposed
  the missing `WORK_GROUP` target.
- Scheduler leases, retry event transactions, queues and payloads retain their behavior.

## Architecture

No architecture change. Registration stays outside domain entities and application services.

## Compatibility

No migration, API, dependency or configuration changes. Restart the scheduler process
to load the imports. Compose mounts `src`, so the local service needs no image rebuild;
image-based deployments must include the changed source.

## Validation

Commands executed:

- `rtk proxy uv --cache-dir /tmp/uv-cache run pytest -q tests/core/test_celery_scheduler.py -k fresh_process`
  — failed before the fix; the regression passed in the focused scheduler/Celery run.
- `rtk proxy uv --cache-dir /tmp/uv-cache run ruff check src/core/celery_scheduler.py tests/core/test_celery_scheduler.py`
  — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run ruff format --check src/core/celery_scheduler.py tests/core/test_celery_scheduler.py`
  — passed.
- `rtk proxy mise run check` — sandbox attempt could not write the uv cache;
  elevated run exited 1. Formatter, lint, types, security and doctest passed;
  main suite: 1,001 passed, 225 documented opt-in integration skips;
  disposable workflow: four passed. Delivery foundation: 18 failed, beginning with
  asyncpg `InternalClientError: cannot switch to state 11; another operation ...`,
  followed by PostgreSQL connection refusals at localhost:5432. The remaining five
  delivery profiles were not run after this failure. Evidence is in
  `/tmp/app-be-check-rakhmtf2/report.json` and its stage logs.
- `rtk proxy uv --cache-dir /tmp/uv-cache run pytest -q tests/core/test_celery_scheduler.py tests/core/test_celery_app.py`
  — sandbox run stalled after nine tests and was interrupted (exit 130); elevated
  rerun passed all 23 tests.
- `rtk proxy mise run precommit-check` — passed separately after the full gate stopped
  (the XML hook reported no applicable files).
- `rtk proxy graphify update .` — sandbox extraction failed; elevated AST refresh
  succeeded: 15,924 nodes, 39,235 edges. Community-label advisory retained.
- `rtk proxy docker compose restart scheduler` — completed. Recent logs captured with
  `rtk proxy docker compose logs --since 90s scheduler > /tmp/scheduler-after-model-fix.log`.
  After new leadership at 18:39:23 UTC, the captured window through 18:40:17 contains
  344 outbox publications, zero `scheduler.tick_failed`, zero `NoReferencedTableError`.

Result: PARTIAL. Focused regression and actual local scheduler recovery passed;
the complete integrated gate remains blocked by the recorded PostgreSQL failures.
Source baseline: `4a5ec27f9f14eba7ad7fd7bbfa5280a7ed77d272`; initially clean worktree.
Gate start/end source comparison found only `BACKLOG.md` and `CHANGELOG.md` changed;
the change record was also added during validation. Production and test source stayed
identical throughout the gate. No release readiness or hosted acceptance is claimed.

## Backlog Impact

All eight unfinished tasks reviewed. This repair does not alter their acceptance boundaries.

Enabled: None

Blocked: None

Superseded: None

Conflicts: None

## References

Commit: None

Pull Request: None

Additional notes: Related scheduler/runtime work is recorded in `docs/changes/APP-BE-024.md`.

## Current-source verification closure — 2026-10-26

Status: DONE for this bounded task. Verification: VERIFIED_WITH_EXCEPTION under
the existing two exact D07 SDK exceptions; never strict exception-free or demo ready.

The owner requested cross-repository backlog selection and execution. The current
complete backend gate exits 0 and passes all sixteen stages. The exact invocation,
including browser/cache environment, is retained in the peer evidence commands.json:
1,032 default tests, one doctest and 142 mandatory service cases, zero mandatory
skips and emitted diagnostics. The 233 documented default opt-in exclusions are
reported separately. The current-source comparison finds no changed maintained
files between gate start and completion. The original failed/partial evidence
above remains historical and is not removed.

The focused scheduler/Celery and seed/primitive invocation retained in commands.json
passes all 51 tests. The installed
browser is explicitly selected through the existing setting; no test, diagnostic
threshold or timeout is weakened. `rtk proxy mise run workflow-library-test`
separately passes its actual publication/execution/both-branches/rerun-preservation
scenario on an owned migrated database, which is removed afterward.

The current pair separately passes all 44 actual workflow/browser scenarios with
exact live OpenAPI agreement, unchanged functional sources and no browser/service
diagnostics. Existing local infrastructure and API startup are restored, and
health/readiness return 200. The development database remains at 0003_arabic;
rolling out 0004_binding_source_schema is a separate reviewed backup/upgrade action
under APP-BE-031/032. No shared reset, stamp or deployed migration is performed.

Evidence is retained in the peer frontend's artifacts/roadmap-2026-10-26/: the
backend-check-first native report/logs, backend-first-source-comparison.json,
backend-focused.log, workflow-library.log and paired-workflows/manifest.json.
The final documentation-qualified complete gate and actual native result belong
to backend-check-final/ and completion.json there. Missing or failed final evidence
must be reported; this section does not preclaim that later run.

The unfinished-only backlog removes this completed task while preserving its
stable ID and original implementation/history here. APP-BE-031/032 and the
remaining Agent, Calendar, notification, mapper and assistant owners retain their
existing prerequisites and acceptance boundaries. No new feature task is allocated.
Hosted, deployed, manual and user acceptance remain separate.
