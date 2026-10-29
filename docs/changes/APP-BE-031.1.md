# APP-BE-031.1 — Local binding-schema rollout

Backlog: APP-BE-031.1
Date: 2026-10-27
Area: migrations/local operations

## Summary

The existing local database is upgraded from `0003_arabic` to the reviewed
`0004_binding_source_schema`. The API and all readiness dependencies are healthy.
A restored rehearsal and canonical row checks preceded the actual upgrade.

## Why

The existing development database lacked the source-schema column needed by current
binding authoring. The owner explicitly requested rehearsal and local application;
existing business data, published graphs and active pins had to survive.

## What Changed

- Stopped and resumed the existing API, worker, reporting worker and scheduler.
- Created a private custom-format backup, restored an owned rehearsal database,
  verified legacy rows, and upgraded the rehearsal through Alembic.
- Applied the same existing forward revision to development and rechecked row digests,
  the schema marker and added constraint. Only the owned rehearsal database was removed.
- Preserved all 103 business tables and 189,438 rows, excluding the newly nullable
  binding column from before/after legacy comparisons.

The durable private backup is
`.demo-seed/fd8798e8b92b1482/backups/2026-10-27-before-0004.dump`, mode 0600 in an
owned 0700 directory. SHA-256:
`c3a35a659eb4145241565eb3f5fda2079fe274b83c7f849ab818df9837524422`.
The original rehearsal backup is also retained; safe receipts record both locations.
No backup contents, credentials or private row values are copied to review evidence.

## Architecture

No architecture change. The existing Alembic lineage and operational owners are reused.

## Compatibility

No applied revision edit, blind stamp, reset, published-payload rewrite or active-pin
change. The reviewed nullable forward migration preserves legacy bindings. This
operation targets only the existing local development database and supplies no
hosted deployment or user acceptance under APP-BE-031/032.

## Validation

The owned rollout helper invoked `pg_dump`, `pg_restore` and the normal
`python -m alembic upgrade head` for the rehearsal and actual target. Both reached
`0004_binding_source_schema`; canonical legacy-row digests match. Current `/health`
and `/ready` return 200, with PostgreSQL, cache, broker and S3 up.

Frontend evidence directory: `artifacts/seed-processes-2026-10-27/` contains
`migration-rollout.json`, `migration-preservation.json`, `durable-backup.json` and
`development-health.json`. Native full-gate logs and exact source comparisons live
there separately. Documentation-qualified completion remains gated by its final
completion receipt; D07 permits only VERIFIED_WITH_EXCEPTION for backend gates.

Result: local rollout PASS; full completion is conditional on the final receipt.

## Backlog Impact

Enabled: APP-BE-019.UX02 and APP-BE-005.3 local authoring/execution.

Blocked: APP-BE-031/032 hosted/runtime/recovery/user gates retain their own evidence.

Superseded: None.

Conflicts: None. All unfinished backlog owners were reviewed; no parent is closed.

## References

Commit: None.

Pull Request: None.

Additional notes: `docs/changes/DB-002.md`, `docs/delivery/approved-decisions.json`.


## Full-gate completion candidate — 2026-10-27

The preliminary sixteen-stage `mise run check` completed with native exit 0 and
VERIFIED_WITH_EXCEPTION: 1,039 default tests plus 234 documented opt-in exclusions,
one doctest and 146 mandatory service scenarios, zero required skips and zero emitted
diagnostics. Only documentation changed during that run. The final documentation-qualified
full run and exact source comparison are recorded separately in the frontend checkout's
`artifacts/seed-processes-2026-10-27/completion.json`; missing/failed evidence keeps the
candidate incomplete. D07's two exact accepted SDK exceptions remain unchanged and do
not establish strict/demo readiness. All failed/partial attempts are retained separately.
