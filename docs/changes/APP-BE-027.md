# APP-BE-027 — Private transfer/report bounds

Backlog: APP-BE-027
Date: 2026-10-08
Area: media/reporting/S3 and verification harness

## Summary

Current completion review (2026-10-09): BLOCKED/IMPLEMENTED. The exact ten baseline
entries are accepted and the fresh fifteen-stage gate passes. The remaining acceptance
gap is graceful recovery while an oversized upload is still streaming through the
paired frontend: a connection reset is possible. Header-only preflight evidence does
not close that gap. The older preparation paragraphs below retain their dated history;
they do not represent current unresolved scanner approval. See
[completion verification](../delivery/completion-verification.md).

Private upload metadata and report operations use no-store; report artifact size and storage integrity preflight precede transfer accounting, and decode/archive bounds reject excessive work.

Implementation is prepared and real-service evidence is recorded. Completion remains
blocked until the final full gate passes; the proposed secret-baseline review has
not been approved. Do not interpret this record as DONE or strict readiness.

## Why

Wave four extends existing owners to meet the delivery backlog without duplicating
identity, authoring, execution, media or reporting infrastructure.

## What Changed

- media/application/service.py; media/presentation/routes.py; reporting/application/service.py; reporting/tasks.py; utils/s3.py; scripts/transfer_services.py
- Contracts C14; detailed behavior, defaults, compatibility, ownership,
  failure handling and peer instructions: `docs/delivery/wave-four-handoff.md`.
- Generated en/fa OpenAPI, inspector matrix, metric dictionary and metadata schema:
  `docs/delivery/wave-four/manifest.json`.

## Architecture

### Before

Existing application owners supplied the baseline behavior, with the gaps documented
in `docs/delivery/baseline-and-reuse.md`.

### After

Existing media/report owners remain intact. Owned real worker/storage/broker and actual Node boundary verify transport without browser tokens. Report READY means generation, download_count means authorized start, and legacy SHA-metadata absence retains documented size/type compatibility.

### Reason

Keep authority and transaction boundaries with their existing owners; expose typed
bounded interfaces that normal editors can consume safely.

## Compatibility

MAX_REPORT_ARCHIVE_BYTES defaults to 10 MiB (1–64 MiB configurable). Existing larger artifacts cannot download under the new limit. New report object metadata includes SHA256; legacy objects keep size/type compatibility.
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

- APP-BE-028 (once the final gate permits completion)

Blocked:

- APP-BE-027: final gate and exact secret-baseline approval

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

## Through-020 dependency evidence — 2026-10-08

The prior exact baseline review is owner-approved and the final through-020 shared gate
passed. APP-BE-027 remains READY/IMPLEMENTED and is not closed by the narrower user scope.
The owned transfer profile verifies maximum private uploads/downloads, maximum-plus-one
backend rejection, declared-size boundary preflight rejection, session isolation and
actual worker/storage. An oversized client still streaming after peer early rejection
can receive a reset; graceful peer streaming rejection remains paired acceptance work.
The header preflight case sends no invalid body and does not attest that missing behavior.
No frontend source was changed. See [through-020 evidence](../delivery/through-020-verification.md).
