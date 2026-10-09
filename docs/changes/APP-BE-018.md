# APP-BE-018 — Authorized metric dictionary and chart data

Backlog: APP-BE-018
Date: 2026-10-08
Area: reporting analytics

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete fourteen-stage gate passed,
including all actual analytics scenarios with no required-profile skips. D07 and the exact
ten prior baseline entries are owner-approved; no further scanner exception was added.
Command: `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check` — exit 0.
See [through-020 verification](../delivery/through-020-verification.md) and
[gate summary](../delivery/through-020-gate.json) for source hashes, counts and limits.

## Preparation history

The PARTIAL/BLOCKED sections below preserve earlier observations and are superseded
by the completion above. No production-scale or frontend acceptance is claimed.

## Summary

Registered chart-neutral day/status metrics aggregate authorized live request/work populations before paging and return typed list drill-downs.

Implementation is prepared and real-service evidence is recorded. Completion remains
blocked until the final full gate passes; the proposed secret-baseline review has
not been approved. Do not interpret this record as DONE or strict readiness.

## Why

Wave four extends existing owners to meet the delivery backlog without duplicating
identity, authoring, execution, media or reporting infrastructure.

## What Changed

- reporting/domain/analytics.py; reporting/application/analytics.py; reporting/presentation/analytics.py; requests/work_items query owners
- Contracts C10; detailed behavior, defaults, compatibility, ownership,
  failure handling and peer instructions: `docs/delivery/wave-four-handoff.md`.
- Generated en/fa OpenAPI, inspector matrix, metric dictionary and metadata schema:
  `docs/delivery/wave-four/manifest.json`.

## Architecture

### Before

Existing application owners supplied the baseline behavior, with the gaps documented
in `docs/delivery/baseline-and-reuse.md`.

### After

Fixed SQL aggregation reuses owning list predicates. Civil-date half-open DST bounds, explicit units, valid-sample means and unknown counts avoid inferred approvals, fake zeros or monetary sums. No shared cache; receipts/business outcomes remain explicitly unavailable.

### Reason

Keep authority and transaction boundaries with their existing owners; expose typed
bounded interfaces that normal editors can consume safely.

## Compatibility

No additional schema for this task.
JSON remains BaseDTO snake_case with existing success/page/public-error envelopes.
No dependency/lock upgrade, deployment, shared-data reset or applied migration rewrite.
Frontend handoff is prepared; browser integration and owner acceptance remain separate.

## Validation

Commands and actual safe results are centralized in
`docs/delivery/wave-four-verification.md`, including failed intermediate attempts.

Result: PARTIAL — relevant database/worker/boundary tests passed, but the complete
quality gate is blocked by unapproved exact secret-scanner false positives. The two
SDK warning exceptions are separately owner-approved as VERIFIED_WITH_EXCEPTION;
this is not warning-free readiness.

## Backlog Impact

Enabled:

- APP-BE-029 (once the final gate permits completion)

Blocked:

- APP-BE-018: final gate and exact secret-baseline approval

Superseded:

- None

Conflicts:

- None; D01 additive policy and D07 exact SDK exceptions are owner-approved.

All unfinished APP tasks and their existing dependency edges were reviewed. No
later capability is marked complete by this implementation.

## References

Commit: None (uncommitted work)

Pull Request: None

Additional notes: `docs/delivery/wave-four-handoff.md`,
`docs/delivery/approved-decisions.json`, `docs/delivery/secret-baseline-review.json`.

## Through-020 validation follow-up — 2026-10-08

The actual owned application profile passed 29 tests after adding a controlled-clock
submission lifecycle fixture (immutable submitted_at is never rewritten). A 23-hour New
York DST range counts only the inclusive-start/exclusive-end population; every status
bucket matches its authorized list drilldown. Real draft cancellation with no submitted_at
produces an unknown terminal duration, not zero. Soft-deleted requests and inactive actors
are excluded/denied. Existing seven metric-spec unit checks pass. The earlier four-row
EXPLAIN plan is small-fixture evidence only; scale certification belongs to APP-BE-028/031.

Command: `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run delivery-wave-four-test` — 29 passed.
Result: PARTIAL until the complete through-020 gate. All unfinished dependencies reviewed;
APP-BE-029 and APP-FE-015 can consume the contract, while later demo/performance acceptance
retains its own scope. See [through-020 handoff](../delivery/through-020-handoff.md).
