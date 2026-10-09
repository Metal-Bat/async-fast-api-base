# APP-BE-017 — Durable calendar reminders

Backlog: APP-BE-017
Date: 2026-10-08
Area: calendar/scheduler/notifications

## Summary

Reminder configuration/cancellation belongs to the source transaction. Existing clocked scheduler and outbox invoke bpms.fire_calendar_reminder; MAP-10/11 deliver deduped eligible notices. Old revisions cancel, live authority is checked at fire and delivery, and over-24-hour lag expires with non-recursive support metadata.

## Why

One-off calendar/work reminders needed actual scheduler recovery and current-source checks.

## What Changed

Reminder configuration/cancellation belongs to the source transaction. Existing clocked scheduler and outbox invoke bpms.fire_calendar_reminder; MAP-10/11 deliver deduped eligible notices. Old revisions cancel, live authority is checked at fire and delivery, and over-24-hour lag expires with non-recursive support metadata. Exact routes, bounds, privacy, retention, lifecycle and delivery distinctions are
recorded in [through-020-handoff.md](../delivery/through-020-handoff.md). Generated en/fa
OpenAPI and schemas in docs/delivery/wave-four derive from the implemented owners.

## Architecture

### Before

Existing scheduler, task outbox and notification pipeline supported other sources.

### After

CalendarReminder ledger links source revision/recipient to existing PeriodicTask; existing broker worker and notification delivery remain sole execution owners.

### Reason

Preserve occurrence identity through restart/outage without a second timer loop or invented workflow transition.

## Compatibility

Reminder table is part of j016; no new queue or setting. SENT is staged in-app intent, not external provider receipt. Existing optional email gateway policy remains. Initial and workspace migration bytes are preserved under approved D01.
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

- APP-BE-029; APP-FE-014/012

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
