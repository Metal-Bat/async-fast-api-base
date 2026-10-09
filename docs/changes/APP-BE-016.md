# APP-BE-016 — Workflow-aware calendar

Backlog: APP-BE-016
Date: 2026-10-08
Area: calendar/users/work items

## Summary

Added private event CRUD/history/search/report with exact intent replay, current references, active team membership, half-open overlap and strict IANA/date/instant semantics. Actual due_at values are immutable calendar projections under existing cartable authority.

## Why

A bounded personal/team calendar and actual deadline projection were missing.

## What Changed

Added private event CRUD/history/search/report with exact intent replay, current references, active team membership, half-open overlap and strict IANA/date/instant semantics. Actual due_at values are immutable calendar projections under existing cartable authority. Exact routes, bounds, privacy, retention, lifecycle and delivery distinctions are
recorded in [through-020-handoff.md](../delivery/through-020-handoff.md). Generated en/fa
OpenAPI and schemas in docs/delivery/wave-four derive from the implemented owners.

## Architecture

### Before

Work item due_at and users/groups existed; no manual calendar owner existed.

### After

Calendar owns manual events; users/groups own membership; work-item services remain the authority for derived deadline points.

### Reason

Avoid duplicate mutable workflow deadlines and apply visibility before counts and pagination.

## Compatibility

Additive j016_calendar_events following i015; Gregorian en/fa only; snake_case existing envelopes and private headers; no new package or environment settings. Initial and workspace migration bytes are preserved under approved D01.
Existing framework logs and historical diagnostic rows are outside the new safe projection.
No peer repository mutation, deployment, live-vendor or browser acceptance is claimed.

## Validation

Commands executed:

- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run delivery-through-020-test` — 9 passed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run delivery-transfer-test` — 6 passed, including actual reminder scheduler/broker/Celery recovery.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run delivery-foundation-test` — 16 passed, including migration installation/upgrade/drift.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run ty check` — passed.

Result: PASS with exactly the approved D07 SDK exceptions (VERIFIED_WITH_EXCEPTION).
The complete fourteen-stage gate passed; every required scenario ran without skips.
Command: `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check` — exit 0.
See [through-020-verification.md](../delivery/through-020-verification.md) for source hashes,
per-stage counts, default exclusions, original failed attempts and D07.

## Backlog Impact

Enabled:

- APP-BE-017, APP-BE-029; APP-FE-014

Blocked:

- None added; later approval/integration/reset/browser acceptance keeps its existing dependencies.

Superseded:

- None.

Conflicts:

- None. All unfinished APP-BE tasks were reviewed; the new contracts do not close their separate scope.

## References

Commit: None (uncommitted work)

Pull Request: None

Additional notes: [Backend handoff](../delivery/through-020-handoff.md),
[verification](../delivery/through-020-verification.md), original task in docs/delivery/BACKEND-BACKLOG.md.
