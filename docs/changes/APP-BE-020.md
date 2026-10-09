# APP-BE-020 — Runtime form conformance

Backlog: APP-BE-020
Date: 2026-10-08
Area: forms/work items/runtime

## Summary

Added a versioned twenty-kind fixture and pure/actual published request-review-correction coverage. Attachment mutations now synchronize current upload references into canonical submission data. Partial action validation correctly validates formatted values while preserving hidden fields and nested row identities.

## Why

The twenty-control matrix exposed stale attachment runtime data and reversed arguments in partial formatted-value validation.

## What Changed

Added a versioned twenty-kind fixture and pure/actual published request-review-correction coverage. Attachment mutations now synchronize current upload references into canonical submission data. Partial action validation correctly validates formatted values while preserving hidden fields and nested row identities. Exact routes, bounds, privacy, retention, lifecycle and delivery distinctions are
recorded in [through-020-handoff.md](../delivery/through-020-handoff.md). Generated en/fa
OpenAPI and schemas in docs/delivery/wave-four derive from the implemented owners.

## Architecture

### Before

Existing runtime projection, attachment owner, row editing and pinned definitions already existed.

### After

The same owners now synchronize canonical attachment data and correctly validate partial action data; no new runtime dialect or execution engine.

### Reason

Repair the observed seams while preserving pinned schemas, exact values and writable patch authority.

## Compatibility

No migration or dialect change; attachment mutation responses retain existing shapes and current refs. Decimal values remain canonical strings, never floats. Initial and workspace migration bytes are preserved under approved D01.
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

- APP-BE-028; APP-FE-007/016–019

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
