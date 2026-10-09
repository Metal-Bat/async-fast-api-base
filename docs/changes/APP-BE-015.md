# APP-BE-015 — Safe support episodes

Backlog: APP-BE-015
Date: 2026-10-08
Area: support/errors/task lifecycle

## Summary

An independent support recorder coalesces sanitized episodes, provides bounded authenticated client intake, audited operator transitions and current-capability MAP-13 fanout. New task failures retain safe type/code metadata without raw task inputs or exception stacks.

## Why

Technical failures previously lacked rollback-safe support identities and safe bounded operator inspection.

## What Changed

An independent support recorder coalesces sanitized episodes, provides bounded authenticated client intake, audited operator transitions and current-capability MAP-13 fanout. New task failures retain safe type/code metadata without raw task inputs or exception stacks. Exact routes, bounds, privacy, retention, lifecycle and delivery distinctions are
recorded in [through-020-handoff.md](../delivery/through-020-handoff.md). Generated en/fa
OpenAPI and schemas in docs/delivery/wave-four derive from the implemented owners.

## Architecture

### Before

Previously request/task errors had correlation and attempt owners but no dedicated safe support projection.

### After

The new support domain owns episode storage and safe APIs; existing exception handlers, task lifecycle, history and notification outbox invoke it through independent persistence.

### Reason

Keep the failed business transaction separate while preventing private diagnostic snapshots or notification recursion.

## Compatibility

Additive i015_support_incidents; support.incidents.manage is created without automatic existing grants; existing response envelopes gain support metadata on technical failures. Initial and workspace migration bytes are preserved under approved D01.
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

- APP-BE-023, APP-BE-029; APP-FE-013/032

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
