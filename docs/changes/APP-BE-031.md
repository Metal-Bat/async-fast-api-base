# APP-BE-031 — Paired contracts, hosted gate and rebuilt runtime

Backlog: APP-BE-031
Date: 2026-10-10
Area: contracts, hosted tooling, runtime verification

## Summary

local producer/consumer source and complete paths/components/security checks, both full gates, deliberate incompatible contracts/failing-tool negative checks and actual rebuilt image are implemented/locally verified. Actual hosted run remains NOT_RUN; immutable reviewed commits/default-branch workflow publication and dispatch are still needed.

## Why

Reuse completed owners and preserve historical evidence while closing concrete delivery gaps. Local fixtures do not establish hosted, deployed or owner acceptance.

## What Changed

scripts/producer_identity.py; scripts/verify_release_pair.py; scripts/hosted_gate.py; .github/workflows/paired-delivery.yml; scripts/build_runtime_image.py; tests/integration/test_runtime_image.py. See the operations handoff for exact commands, resource bounds, private evidence, failure behavior and limitations.

## Architecture

### Before

Existing application services, outbox, workers, disposable runners and contract snapshots provided separate verification seams.

### After

The same owners supply the combined local rehearsal, guarded resource lifecycle and full contract comparisons. No parallel permission, workflow, notification or execution system is added.

### Reason

Keep domain authority with existing services and make cross-process evidence reviewable.

## Compatibility

No database revisions, dependencies or public wire fields change. Migration chain remains `0001_schema -> 0002_required_data`. JSON remains BaseDTO/snake_case with existing envelopes and stable errors. Added mise commands require explicit private disposable ownership; hosted provisioning refuses existing operator configuration. No shared data, paid provider, deployment or image publication is performed.

## Validation

Commands executed through the documented focused runners and current paired verification:

Current pair comparison passed. Runtime image sha256:eb8d524f57ac1879c5fc04ee5c13522709705dc618c72a789593bff7e88d1f5a passed 1 actual service probe in 17.52 seconds. Hosted ownership/ref/config refusal tests and DTO/security/source-drift negative tests passed. No hosted run occurred.

Result: PARTIAL. Full current backend/peer gates and exact source comparison remain required. Only the two previously accepted D07 SDK warning exceptions apply; no new suppression or mandatory skip is accepted.

## Backlog Impact

Enabled:

- APP-BE-023/027/028/029/031/032, within their actual acceptance boundaries.

Blocked:

- APP-BE-031/032: actual hosted and final paired acceptance remain unverified.

Superseded:

- None; historical verification and IDs are preserved.

Conflicts:

- None newly approved. Hard supervisor loss and protected-effect restore remain explicit limitations.

## References

Commit: None

Pull Request: None

Additional notes: [operations handoff](../delivery/DEMO-OPERATIONS-HANDOFF.md), [capability ledger](../delivery/BACKEND-CAPABILITY-LEDGER.md), [connected evidence](../delivery/connected-workflow-verification.json), [image evidence](../delivery/runtime-image-verification.json). Unfinished relationships were reviewed; task remains IN_PROGRESS.


## Historical summary before current closeout

Current complete producer/consumer contracts compare successfully. A guarded pinned hosted workflow and source-only image automation are implemented. Current image startup and instrumented SQL passed. Actual hosted execution and stable full candidate gates remain unverified.


## Current closeout — 2026-10-11

local producer/consumer source and complete paths/components/security checks, both full gates, deliberate incompatible contracts/failing-tool negative checks and actual rebuilt image are implemented/locally verified. Actual hosted run remains NOT_RUN; immutable reviewed commits/default-branch workflow publication and dispatch are still needed.

Validation result: PARTIAL: local checks pass; actual hosted/full acceptance remains blocked.

Commands executed: `mise run check` (backend, all sixteen stages), `mise run check` (final frozen frontend), `mise exec -- npm run ci:gates` (actual matching frontend). Backend start/end source identity matches; 983 default tests, one doctest and 132 mandatory service cases pass with zero mandatory skips. The 221 default opt-in exclusions remain listed. Frontend: 545 unit tests; all twelve commands pass with zero tool diagnostics and unchanged source. The repaired peer additionally passes all four actual en/fa approval/receipt and lost-reply cases.

The strict failed full-gate attempt, SQLite connection regression/fix and passing strict restore rerun remain in [final verification](../delivery/main-tasks-final-verification.json). The runtime image context still matches tested source. Evidence/backlog documents were updated after the stable gate; application, contracts, tests, migrations, dependencies and runtime configuration were unchanged afterward.

Backlog impact: APP-BE-031/032 remain BLOCKED; no deployed or USER_ACCEPTED claim. Commit/PR: None. Existing decisions and historical failed/partial results are preserved.
