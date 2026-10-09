# APP-BE-001 — Reconcile baseline and paired contract inventory

Backlog: APP-BE-001
Date: 2026-10-08
Area: delivery/intake

## Summary

Inventoried all 32 APP tasks against existing owners, generated the actual English/Farsi
API snapshots and consumer manifest, and verified the unchanged local baseline.

## Why

The proposed pack misreported the actual migration head and tool versions. Existing
platform features must be extended rather than rebuilt from the plan's prose.

## What Changed

- `docs/delivery/baseline-and-reuse.md` maps every task to source owners and uncovered deltas.
- `docs/delivery/contract-index.md`, localized OpenAPI, API inventory and manifest identify
  314 operations, 425 schemas, source owners, permissions, hashes and installed/locked versions.
- Read-only peer comparison at `afe4bbe5f566c80e7eb45f6ef9f12c041d60139d` found identical
  platform paths and shared schemas; the older base schema lacks 12 operations.
- `BACKLOG.md` links the authoritative delivery supplement without duplicating tasks.
- D01 proposal records the actual committed successor `c24f913ab601`; D02–D06 remain
  proposed constraints without fabricated owner/live-provider/browser signoff.

## Architecture

No architecture change. Existing domain owners, envelopes, immutability and auth remain authoritative.

## Compatibility

No application, schema, dependency or public API change. Both existing migrations are preserved.
This handoff is local evidence; no peer write, deployment or browser acceptance was performed.

## Validation

Commands executed:

- `rtk proxy graphify query "Repository baseline quality gate migrations seed catalogs notifications soft delete query filtering"` — scoped owner discovery.
- `rtk proxy uv run --no-sync alembic heads` and `alembic history` with a writable uv cache
  — one head, `base -> b13a0c7d2e44 -> c24f913ab601`.
- `rtk proxy mise run check` — initial sandbox uv cache error.
- `UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check` — sandbox Bandit socket denial;
  rerun outside the sandbox passed all steps, 685 default tests, 119 explicit opt-in skips,
  one doctest, four PostgreSQL flow tests, applicable all-file hooks. Log:
  `/tmp/app-be-baseline-check-unrestricted.log`. The owned disposable DB was removed.
- Generated schemas through `utils.localized_docs.localized_openapi`; manifest hashes
  and operation/schema comparison were calculated from actual files.

Result: PASS for analysis/intake and baseline local gate; PARTIAL for integrated product readiness.
The two narrowly scoped SDK warning filters remain visible and APP-BE-002 owns strict policy.
119 default integration skips and image/browser/live-provider checks are not completion evidence.

## Backlog Impact

All 32 unfinished APP tasks reviewed.

Enabled:

- APP-BE-002
- APP-BE-013

Blocked:

- APP-BE-004 pending APP-BE-003/D01

Superseded:

None

Conflicts:

- APP-BE-003 retains explicit D01 decision gate; its pack baseline is corrected.

## References

Commit: baseline `995829eebd9483ac6b589c1648fc799c650ad464`

Pull Request: None

Additional notes: `docs/delivery/contract-manifest.json`; `docs/delivery/DECISIONS.md`.
