# APP-BE-028 — Connected workflow regression (in progress)

Backlog: APP-BE-028
Date: 2026-10-10
Area: workflows, work items, integration verification

## Summary

shared purchase-connected/1 traverses rich nested/private input, budgeted scripted AI, human supervision, pinned parallel reviews/join, fresh human approval, durable real order and receipt; correction/reject/race/replay/uncertainty/cancellation invariants verified. Browser covers approval/receipt, earlier stages use real backend fixture services.

## Why

Disconnected feature tests did not prove the same case traverses all stages. Read-only acknowledgment was rejected at publication, and generic service output metadata could not express a known operation receipt. The previous blanket subprocess restriction also rejected independent child reviews before a fresh root-local approval.

## What Changed

- Read-only task contracts require nonempty readable scopes; write checks continue to reject modifications.
- Registered business-effect output schemas refine binding validation without changing stored port metadata, graph snapshots or checksums.
- Unprotected pinned child reviews may precede independent root approval. Child-owned effects and inherited child approval remain rejected.
- Existing disposable runner includes the connected cases in mandatory transfer coverage. Database deletion requires an exact locally registered disposable identity.
- The single purchase vector carries the connected profile. Actual S3 bytes, owner denial, hidden projection, persisted notices, worker settlement, duplicate dispatch, approval correction, rejection, authenticated claim races, successor publication and default restoration have focused evidence.

## Architecture

### Before

Feature-specific fixtures verified separate workflows; publication required writable human fields and rejected any subprocess in a protected root graph.

### After

Existing forms, workflow engine, outbox, worker, storage and protected-operation owners execute the connected scenario. Fresh root-local human approval retains its exact effect payload binding. No new store, workflow engine, approval authority or dispatcher is introduced.

### Reason

Exercise composition through the current owners while keeping authorization and immutable pins intact.

## Compatibility

No migrations, dependencies or wire fields changed. Existing generic port metadata, envelopes, private access rules and command replay payloads remain unchanged. English/Farsi Swagger descriptions now explain read-only acknowledgment and trusted receipt refinement.

## Validation

Commands executed:

- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache FLOW_TEST_PROFILE=protected-operations uv run --env-file .envs/.backend python -c 'from scripts import run_flow_test as runner; runner.PROFILES["protected-operations"]=("tests/integration/test_connected_workflow.py",); raise SystemExit(runner.main())'` — latest focused run: 10 passed, 217.26 seconds, owned resources removed.
- Focused Ruff and `ty` checks passed. Earlier failed and interrupted development runs remain in the structured evidence.

Result: PARTIAL. The complete final gate and source comparison, paired browser/fault acceptance and guarded demo rehearsal remain required. Scripted AI establishes no live-provider quality or spend acceptance.

## Backlog Impact

Enabled:

- APP-BE-023, APP-BE-029, APP-BE-031, APP-BE-032 (partial foundations)

Blocked:

- None newly introduced; existing unfinished acceptance remains.

Superseded:

- None

Conflicts:

- None. The accepted root-local approval policy remains unchanged.

## References

Commit: None

Pull Request: None

Additional notes: [structured focused evidence](../delivery/connected-workflow-verification.json), [protected effect policy](../delivery/protected-effect-policy.md). Unfinished task relationships were reviewed; task remains IN_PROGRESS.

## Paired follow-up — 2026-10-10

The actual paired browser now passes ordinary authentication, fresh connected approval,
real worker order, read-only receipt and acknowledgment in en/fa, including a truncated
post-commit approval reply and current-state recovery: 4 passed in 147.85 seconds.
Committed approval replay and changed-key/payload denial passed within the current
10-case connected run (248.52 seconds). Connected order lookup/cancellation variants
passed in the 7-case recovery run (91.23 seconds). Earlier failures remain recorded.
This focused evidence supersedes the earlier statement that paired receipt acceptance
had not run; full current gates and demo/hosted acceptance remain separate.


## Historical summary before current closeout

The saved purchase vector now drives an owned-service connected case with rich nested data and private evidence, scripted budgeted AI, required human supervision, parallel pinned child reviews, fresh root approval, a real sandbox order, a persisted receipt-task notification and read-only receipt acknowledgment. Approve, correction and reject variants run in English and Farsi. This is partial backend evidence; paired browser, full fault variants and demo acceptance remain open.


## Current closeout — 2026-10-11

shared purchase-connected/1 traverses rich nested/private input, budgeted scripted AI, human supervision, pinned parallel reviews/join, fresh human approval, durable real order and receipt; correction/reject/race/replay/uncertainty/cancellation invariants verified. Browser covers approval/receipt, earlier stages use real backend fixture services.

Validation result: PASS within this task’s scoped local/integrated acceptance; VERIFIED_WITH_EXCEPTION under exact D07.

Commands executed: `mise run check` (backend, all sixteen stages), `mise run check` (final frozen frontend), `mise exec -- npm run ci:gates` (actual matching frontend). Backend start/end source identity matches; 983 default tests, one doctest and 132 mandatory service cases pass with zero mandatory skips. The 221 default opt-in exclusions remain listed. Frontend: 545 unit tests; all twelve commands pass with zero tool diagnostics and unchanged source. The repaired peer additionally passes all four actual en/fa approval/receipt and lost-reply cases.

The strict failed full-gate attempt, SQLite connection regression/fix and passing strict restore rerun remain in [final verification](../delivery/main-tasks-final-verification.json). The runtime image context still matches tested source. Evidence/backlog documents were updated after the stable gate; application, contracts, tests, migrations, dependencies and runtime configuration were unchanged afterward.

Backlog impact: this scope is DONE; enables subsequent dependent tasks. APP-BE-031/032 remain blocked. Commit/PR: None. Existing decisions and historical failed/partial results are preserved.
