# APP-BE-027 — Private transfer/report bounds

Backlog: APP-BE-027
Date: 2026-10-08
Area: media/reporting/S3 and verification harness

## Summary

exact authorized Node repair is applied, unknown-length chunked oversize rejection preserves the authenticated session; actual storage/report worker and complete backend/frontend gates now pass.

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
No frontend source was changed. See through-020 evidence.

## Streaming follow-up — 2026-10-09

Status remains PARTIAL. Media/report authorization and access accounting now release
the database session before a slow binary stream. Storage reads are capped at 64 KiB
and these callers enforce the preflight byte count; changed/truncated objects fail the
stream. The existing owners/routes/DTOs/headers remain. English/Farsi Swagger and the
producer manifest were refreshed. No migration, dependency or configuration change.

Focused checks and a mandatory owned real-service transfer profile passed. The actual
Node peer still fails the unknown-size oversized multipart recovery probe. A concrete
two-file transport patch passed that probe only in a temporary peer copy; application
to the actual frontend is pending specific cross-repository authorization. The complete
final backend gate is pending. See [current handoff](../delivery/PRIVATE-TRANSFER-HANDOFF.md).

APP-BE-028 remains blocked on this actual acceptance plus its other predecessors.
Historical paragraphs and results above are preserved and are not current approvals
or a claim of DONE. All unfinished main and assistant tasks were reviewed; no other
feature, browser acceptance or final signoff is closed by this repair.

### Final backend verification — 2026-10-10

`rtk proxy env APP_BE_ARTIFACT_DIR=/tmp/app-be-027-final-browser mise run check`
exited 0. All 15 stages passed: 879 default tests, one doctest, and 86 mandatory
service tests with zero mandatory skips. The default suite's 183 opt-in exclusions
are recorded separately. The exact start/end source hash matches. D07 retains
exactly two accepted SDK exceptions: VERIFIED_WITH_EXCEPTION, not warning-free
readiness. Focused updated transfer/report/documentation checks passed 63 tests.

APP-BE-027 remains BLOCKED/IMPLEMENTED because the actual Node peer's extra streaming
rejection recovery probe failed. The temporary-copy patch passed only the scoped
reproducer; peer changes, full peer gate and broader paired acceptance are pending.
See [structured evidence](../delivery/private-transfer-verification.json). No
frontend, shared data, migration, dependency or environment was changed.

## Authorized actual peer repair — 2026-10-10

The owner approved backend-first and then frontend updates. The exact reviewed two-file
Node repair is applied to the actual peer: unread early failures close the connection,
and oversized private-transfer bodies use bounded discard/drain before returning 413.
The actual unknown-size chunked oversized upload recovery probe passed. This supersedes
the unapplied-patch blocker; current full candidate gates remain required. Existing
baseline approval and D07 warning policy remain accepted and unchanged.


## Historical summary before current closeout

Current completion review (2026-10-09): BLOCKED/IMPLEMENTED. The exact ten baseline
entries are accepted and the fresh fifteen-stage gate passes. The remaining acceptance
gap is graceful recovery while an oversized upload is still streaming through the
paired frontend: a connection reset is possible. Header-only preflight evidence does
not close that gap. The older preparation paragraphs below retain their dated history;
they do not represent current unresolved scanner approval. See
completion verification.

Private upload metadata and report operations use no-store; report artifact size and storage integrity preflight precede transfer accounting, and decode/archive bounds reject excessive work.

Implementation is prepared and real-service evidence is recorded. Completion remains
blocked until the final full gate passes; the proposed secret-baseline review has
not been approved. Do not interpret this record as DONE or strict readiness.


## Current closeout — 2026-10-11

exact authorized Node repair is applied, unknown-length chunked oversize rejection preserves the authenticated session; actual storage/report worker and complete backend/frontend gates now pass.

Validation result: PASS within this task’s scoped local/integrated acceptance; VERIFIED_WITH_EXCEPTION under exact D07.

Commands executed: `mise run check` (backend, all sixteen stages), `mise run check` (final frozen frontend), `mise exec -- npm run ci:gates` (actual matching frontend). Backend start/end source identity matches; 983 default tests, one doctest and 132 mandatory service cases pass with zero mandatory skips. The 221 default opt-in exclusions remain listed. Frontend: 545 unit tests; all twelve commands pass with zero tool diagnostics and unchanged source. The repaired peer additionally passes all four actual en/fa approval/receipt and lost-reply cases.

The strict failed full-gate attempt, SQLite connection regression/fix and passing strict restore rerun remain in [final verification](../delivery/main-tasks-final-verification.json). The runtime image context still matches tested source. Evidence/backlog documents were updated after the stable gate; application, contracts, tests, migrations, dependencies and runtime configuration were unchanged afterward.

Backlog impact: this scope is DONE; enables subsequent dependent tasks. APP-BE-031/032 remain blocked. Commit/PR: None. Existing decisions and historical failed/partial results are preserved.
