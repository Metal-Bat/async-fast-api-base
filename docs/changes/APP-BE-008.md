# APP-BE-008 — Authorized selectors and durable resource links

Backlog: APP-BE-008
Date: 2026-10-08
Area: designer resource links

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete thirteen-stage `mise run check` passed after D01 additive migration approval, D07 exact SDK exceptions and explicit approval of the ten exact non-secret baseline entries. The baseline update preserved all scanner rules and existing entries.

Observed commands, original failures, required service counts, tested source hash and private report are linked in [through-014-verification.md](../delivery/through-014-verification.md) and [through-014-gate.json](../delivery/through-014-gate.json). No required-profile test was skipped. This closes the backend task; later producers, frontend/browser acceptance and deployment retain their own task boundaries.

## Preparation history

The following original sections preserve earlier failures and pending-approval observations. Their PARTIAL/BLOCKED statements describe preparation and are superseded by the observed completion above.

## Summary

Bounded selected-value summaries and opaque stable links refresh current refs while preserving immutable version identity and owner policies.

Implementation is prepared and real-service evidence is recorded. Completion remains
blocked until the final full gate passes; the proposed secret-baseline review has
not been approved. Do not interpret this record as DONE or strict readiness.

## Why

Wave four extends existing owners to meet the delivery backlog without duplicating
identity, authoring, execution, media or reporting infrastructure.

## What Changed

- core/resource_locator.py; designer/application/resource_links.py; designer/domain/resource_links.py; designer/presentation/resource_links.py
- Contracts C03; detailed behavior, defaults, compatibility, ownership,
  failure handling and peer instructions: `docs/delivery/wave-four-handoff.md`.
- Generated en/fa OpenAPI, inspector matrix, metric dictionary and metadata schema:
  `docs/delivery/wave-four/manifest.json`.

## Architecture

### Before

Existing application owners supplied the baseline behavior, with the gaps documented
in `docs/delivery/baseline-and-reuse.md`.

### After

Explicit code-owned dispatch delegates to each existing domain service. Encrypted kind/UUID locators grant no authority and are invalidated by key replacement. Readability and selection eligibility remain distinct; no arbitrary ORM resolver or URLs.

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

- APP-BE-009, APP-BE-011, APP-BE-012, APP-BE-014, APP-BE-015, APP-BE-016, APP-BE-026 (once the final gate permits completion)

Blocked:

- APP-BE-008: final gate and exact secret-baseline approval

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
