# APP-BE-010 — Minimal multilingual help acknowledgments

Backlog: APP-BE-010
Date: 2026-10-08
Area: users help state

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete thirteen-stage `mise run check` passed after D01 additive migration approval, D07 exact SDK exceptions and explicit approval of the ten exact non-secret baseline entries. The baseline update preserved all scanner rules and existing entries.

Observed commands, original failures, required service counts, tested source hash and private report are linked in [through-014-verification.md](../delivery/through-014-verification.md) and [through-014-gate.json](../delivery/through-014-gate.json). No required-profile test was skipped. This closes the backend task; later producers, frontend/browser acceptance and deployment retain their own task boundaries.

## Preparation history

The following original sections preserve earlier failures and pending-approval observations. Their PARTIAL/BLOCKED statements describe preparation and are superseded by the observed completion above.

## Summary

Only explicit self-owned seen/dismissed timestamps are persisted per frontend help key, exact revision and locale; content stays frontend-owned.

Implementation is prepared and real-service evidence is recorded. Completion remains
blocked until the final full gate passes; the proposed secret-baseline review has
not been approved. Do not interpret this record as DONE or strict readiness.

## Why

Wave four extends existing owners to meet the delivery backlog without duplicating
identity, authoring, execution, media or reporting infrastructure.

## What Changed

- users/domain/help*.py; users/data/help_release.py; users/application/help_state.py; users/presentation/help_state.py
- Contracts C05; detailed behavior, defaults, compatibility, ownership,
  failure handling and peer instructions: `docs/delivery/wave-four-handoff.md`.
- Generated en/fa OpenAPI, inspector matrix, metric dictionary and metadata schema:
  `docs/delivery/wave-four/manifest.json`.

## Architecture

### Before

Existing application owners supplied the baseline behavior, with the gaps documented
in `docs/delivery/baseline-and-reuse.md`.

### After

Compact bounded users-owned state with atomic tuple upsert. Reads are inert, repeats preserve first timestamps, reset removes only help metadata, and incompatible release metadata performs no writes. No history/event/content subsystem is added.

### Reason

Keep authority and transaction boundaries with their existing owners; expose typed
bounded interfaces that normal editors can consume safely.

## Compatibility

Additive compact help-state migration on the approved chain; HELP_RELEASE_METADATA_FILE is optional. Missing metadata returns explicit compatibility results.
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

- APP-BE-010: final gate and exact secret-baseline approval

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
