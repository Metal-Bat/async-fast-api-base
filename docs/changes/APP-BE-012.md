# APP-BE-012 — Exact dependency repair guidance

Backlog: APP-BE-012
Date: 2026-10-08
Area: designer/readiness

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete thirteen-stage `mise run check` passed after D01 additive migration approval, D07 exact SDK exceptions and explicit approval of the ten exact non-secret baseline entries. The baseline update preserved all scanner rules and existing entries.

Observed commands, original failures, required service counts, tested source hash and private report are linked in [through-014-verification.md](../delivery/through-014-verification.md) and [through-014-gate.json](../delivery/through-014-gate.json). No required-profile test was skipped. This closes the backend task; later producers, frontend/browser acceptance and deployment retain their own task boundaries.

## Preparation history

The following original sections preserve earlier failures and pending-approval observations. Their PARTIAL/BLOCKED statements describe preparation and are superseded by the observed completion above.

## Summary

Projected the authoritative publication pipeline into safe node/pointer repairs and exact authorized pins, with optional client-renderer checks and empty-candidate facts. Implementation is prepared; formal closure remains blocked by the specific
secret-baseline approval and final whole-project gate.

## Why

Complete the remaining delivery scope through 014 while preserving existing ownership,
immutable published/version pins, existing wire envelopes and actual authorization.

## What Changed

src/apps/designer/application/readiness.py; domain/readiness.py; presentation/routes.py; tests/apps/designer/test_dependency_readiness.py; tests/integration/test_setup_dependency_readiness.py. See the concrete C06/C07 handoffs for exact route, bounds, side-effect,
compatibility, authorization and missing-producer behavior.

## Architecture

### Before

Existing health, publication validation, case notifications and delivery owners existed;
application projections and non-case inbox/event hooks were absent.

### After

Existing owners remain authoritative. Read-only projections do not provision or execute.
Notification effects stage through the same business transaction and existing outbox/
worker; no second validator, scheduler, provider engine or shared cache was introduced.

### Reason

Current facts and current authority must control readiness and notification visibility,
without inventing successful execution or granting access through stored references.

## Compatibility

BaseDTO snake_case, existing success/page/error envelopes and en/fa Swagger are retained.
011/012 add no tables; 014 is additive on D01's approved chain. Legacy notification case
fields remain required, and retained IDs/read/delivery state are preserved. New non-case
rows are excluded from legacy search and protected by typed unified targets. No dependency
upgrade, shared reset, peer mutation, deployment or downstream SMTP claim.

## Validation

Commands/results, original failures, service boundaries and final gate are recorded in
`docs/delivery/through-014-verification.md`. Test-first seams and actual owned PostgreSQL/
Celery/TLS gateway/storage checks were exercised. SDK exceptions are exactly D07.

Result: PARTIAL pending the exact ten-entry security baseline approval and successful
final `mise run check`. No partially verified deliverable is marked DONE.

## Backlog Impact

Enabled:

- 011/012 unblock their frontend checklist/repair consumers; 014 supplies the inbox
  contract for APP-FE-012 and later calendar/reminder/support producers.

Blocked:

- Formal closure through APP-BE-014: specific baseline approval/full gate.
- MAP-07/08/10/11/13 producer work remains in APP-BE-024/023/017/015.

Superseded:

- None; existing owners and task IDs remain intact.

Conflicts:

- None; D01 is approved. All unfinished APP dependencies were reviewed; later hosted,
  frontend, provider and acceptance evidence remains separate.

## References

Commit: None (uncommitted work)

Pull Request: None

Additional notes: `docs/delivery/readiness-handoff.md`,
`docs/delivery/unified-notifications-handoff.md`, `docs/delivery/wave-four/manifest.json`,
`docs/delivery/secret-baseline-review.json`, `docs/delivery/approved-decisions.json`.
