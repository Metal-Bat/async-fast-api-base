# APP-BE-032 — Expanded restore and truthful support handoff

Backlog: APP-BE-032
Date: 2026-10-10
Area: restore, operations documentation

## Summary

local backend gate, repeated rehearsal, private/personal/support/protected-order restore and owned broker/worker/scheduler recovery verified. Capability ledger records remaining broad browser, hosted, named vendor, live AI, deployed and owner acceptance boundaries; DEMO_READY/USER_ACCEPTED absent.

## Why

Reuse completed owners and preserve historical evidence while closing concrete delivery gaps. Local fixtures do not establish hosted, deployed or owner acceptance.

## What Changed

tests/integration/restore_personal_fixture.py; tests/integration/test_bpms_restore.py; scripts/run_flow_test.py; scripts/run_check.py; docs/delivery/BACKEND-CAPABILITY-LEDGER.md. See the operations handoff for exact commands, resource bounds, private evidence, failure behavior and limitations.

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

Expanded actual PostgreSQL/S3 restore passed: 1 case, 8.04 seconds. The restore profile is now mandatory in the final gate. The later 2-case owned restore run passed in 16.34 seconds, including protected UNKNOWN-order restore, fail-closed execution/generic resume, authorized original-identity receipt lookup and no duplicate effect. Full candidate acceptance remains unverified.

Result: PARTIAL. Full current backend/peer gates and exact source comparison remain required. Only the two previously accepted D07 SDK warning exceptions apply; no new suppression or mandatory skip is accepted.

## Backlog Impact

Enabled:

- APP-BE-023/027/028/029/031/032, within their actual acceptance boundaries.

Blocked:

- APP-BE-031/032: actual hosted and final paired acceptance remain unverified.

Superseded:

- None; historical verification and IDs are preserved.

Conflicts:

- None newly approved. Hard supervisor loss and broader production failover remain explicit limitations.

## References

Commit: None

Pull Request: None

Additional notes: [operations handoff](../delivery/DEMO-OPERATIONS-HANDOFF.md), [capability ledger](../delivery/BACKEND-CAPABILITY-LEDGER.md), [connected evidence](../delivery/connected-workflow-verification.json), [image evidence](../delivery/runtime-image-verification.json). Unfinished relationships were reviewed; task remains IN_PROGRESS.

## Operational recovery follow-up — 2026-10-10

Actual owned broker and worker interruption now has focused evidence (1 case, 6.15
seconds). The test rechecks immutable Docker ownership and worker/parent start
identities, pauses/resumes only those resources, replaces the fenced scheduler
leader, retains the original unpublished task ID through broker failure, and
recovers one persisted reminder despite duplicate delivery. This test is mandatory
in the transfer profile. It establishes local recovery, not production failover.
See [operational evidence](../delivery/operational-recovery-verification.json).


## Historical summary before current closeout

Owned backup/restore now verifies personal preferences, help, saved views/defaults, favorite, calendar, inbox and durable incidents alongside existing pins, private bytes and encrypted credential versions. Capability boundaries and operator procedures are explicit; full acceptance remains partial.


## Current closeout — 2026-10-11

local backend gate, repeated rehearsal, private/personal/support/protected-order restore and owned broker/worker/scheduler recovery verified. Capability ledger records remaining broad browser, hosted, named vendor, live AI, deployed and owner acceptance boundaries; DEMO_READY/USER_ACCEPTED absent.

Validation result: PARTIAL: local checks pass; actual hosted/full acceptance remains blocked.

Commands executed: `mise run check` (backend, all sixteen stages), `mise run check` (final frozen frontend), `mise exec -- npm run ci:gates` (actual matching frontend). Backend start/end source identity matches; 983 default tests, one doctest and 132 mandatory service cases pass with zero mandatory skips. The 221 default opt-in exclusions remain listed. Frontend: 545 unit tests; all twelve commands pass with zero tool diagnostics and unchanged source. The repaired peer additionally passes all four actual en/fa approval/receipt and lost-reply cases.

The strict failed full-gate attempt, SQLite connection regression/fix and passing strict restore rerun remain in [final verification](../delivery/main-tasks-final-verification.json). The runtime image context still matches tested source. Evidence/backlog documents were updated after the stable gate; application, contracts, tests, migrations, dependencies and runtime configuration were unchanged afterward.

Backlog impact: APP-BE-031/032 remain BLOCKED; no deployed or USER_ACCEPTED claim. Commit/PR: None. Existing decisions and historical failed/partial results are preserved.
