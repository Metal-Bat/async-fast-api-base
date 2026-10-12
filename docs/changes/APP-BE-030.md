# APP-BE-030 — Wave-three backend review

Latest completion — 2026-10-09: **DONE / VERIFIED_WITH_EXCEPTION** for implemented review scope. Final verification and the current scoped section below supersede the earlier PARTIAL verdict. Historical review text and failures are preserved; explicitly blocked later capabilities remain with their owners.


Backlog: APP-BE-030
Date: 2026-10-08
Area: quality/review

## Summary

Current completion review (2026-10-09): IN_PROGRESS/IMPLEMENTED for the final delivery
scope. Historical warning/comment-drift blockers below are resolved by accepted
decisions and the passing through-020 and fresh fifteen-stage gates. Restoration
authority, replay, workspace concurrency, immutable provenance, safe blockers and
size-bound findings are inspected and repaired with actual regressions; see
`docs/delivery/backend-review.md`. Review of unimplemented protected-effect/demo/release
capabilities remains open, rather than being inferred from the passing current tree.

Reviewed the wave-one-to-three diff plus focused B09–B14 context; repaired unexpected skip masking, child-parent lookup gaps, migration test safety/order, raw SQL typing/blocking async calls and a preexisting SQLite resource leak. Recorded exact evidence and remaining blockers.

## Why

Complete the authorized backlog through dependency wave three by extending existing owners and retaining observed failures as completion blockers.

## What Changed

docs/delivery/backend-review.md; affected source/test repairs linked in the findings register

## Architecture

Existing persistence, query, cache, template and task owners remain authoritative. No new applied schema, execution authority or production effect was introduced. New JSON models inherit BaseDTO; canonical names remain snake_case.

## Compatibility

Blocked on strict warnings and migration drift. Real live-cache acceptance has passed. Review verdict is BLOCKED, scoped to inspected owners; later product capabilities are not certified.

## Validation

The common evidence is recorded in docs/delivery/wave-three-verification.md. Native failure probes, focused regressions, all historical quality stages and disposable PostgreSQL tests were executed. Expected probes are assertions, not application readiness evidence. Required migration drift remains a failing assertion. No masked SDK warning is classified as absent.

Observed final checks: historical gate 720 default passes/130 opt-in skips, one doctest/four PostgreSQL workflow passes and hooks; strict gate five SDK failures; foundation profile 15 passes/one comment-drift failure, no skips. Logs and exact source hashes are linked in the common verification record.

Result: PARTIAL. This record documents prepared work and observed limits, not DONE/strict readiness.

## Backlog Impact

APP-BE-030 remains open with the specific blocker above. Dependent tasks are not silently promoted. Historical completed task records remain unchanged.

## References

Commit: baseline 995829eebd9483ac6b589c1648fc799c650ad464 plus current uncommitted changes.

Pull Request: None

Contracts/scenarios: A02/A16/A18/A20/A24; APP-BE-002

Additional notes: docs/delivery/backend-review.md

## Current scoped repair and acceptance — 2026-10-09

### Summary

Preserve committed upload objects when a subsequent refresh fails or is cancelled, and keep the async loop responsive during RabbitMQ confirmation. This updates the historical review above; its original failures and scope remain evidence rather than current unresolved SDK/migration blockers. Backend review closes only implemented scope; explicitly blocked capabilities retain their original owners.

### Why and what changed

`UserUploadService._store` in `src/apps/media/application/service.py` incorrectly ran destructive pre-commit cleanup after a successful commit if refresh failed. Refresh now runs outside that cleanup boundary. `dispatch_outbox` in `src/apps/tasks/application/outbox.py` performed synchronous network waits on the async loop; existing AnyIO moves only the publisher call to a managed thread, with no detached task or shared session work. Regression owners: `tests/apps/media/application/test_service.py`, `tests/apps/tasks/application/test_outbox.py`, `tests/integration/test_private_transfers.py`. The existing producer exporter is regenerated for exact source identity; public artifact schemas stay compatible.

### Architecture

Before: a post-commit read triggered compensating object deletion; broker confirmation ran directly on the async loop.

After: compensation remains inside the commit-failure boundary; a managed worker thread performs bounded broker I/O while the async owner retains the locked outbox transaction.

Reason: prevent committed upload data loss and loop starvation without replacing storage, outbox, worker, session or workflow owners.

### Compatibility

Existing routes, operation IDs, authentication, envelopes, file/report formats, permissions, private headers and error values remain. No entity, migration, dependency, environment, mise configuration, frontend or shared-data change. Unknown outcomes and whole-pair transfer limits are not claimed resolved; APP-BE-027 remains blocked. Exactly the two D07 SDK exceptions remain approved.

### Validation

Result: PASS for implemented backend review scope, VERIFIED_WITH_EXCEPTION under exactly the two approved D07 SDK exceptions. Initial media regressions failed twice because cleanup deleted the object; the responsiveness regression failed because the loop could not service the concurrent task. An initial test collection attempt imported unavailable Asyncer; corrected to the existing AnyIO dependency without adding packages. One sandbox focused run stalled and was interrupted; the same responsiveness case passed outside the sandbox. No warning suppression, test skip or scanner baseline change was introduced.

### Backlog impact and limitations

Reviewed all unfinished APP/follow-up relationships. APP-BE-030 owns these repairs. Remaining whole-pair transfer acceptance is APP-BE-027/031 and APP-FE-036; protected policy and operations remain APP-BE-021–025; core demo/reset/release remain APP-BE-028/029/031/032; conversation/actions remain APP-BE-033–038. No parent or frontend acceptance is inferred. Peer source identification and backend Swagger browser acceptance are separate from paired feature/deployed/user acceptance.

### References

Commit: None; changes remain uncommitted. Baseline HEAD: 9999641f8e37077829ebbe7159a6cd794fb94b91. Pull request: None.

Current findings register; canonical APP backlog; existing consistency evidence.

Observed focused commands for the current slice:

- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run pytest tests/apps/tasks/application/test_outbox.py tests/apps/media/application/test_service.py tests/delivery/test_transfer_bounds.py -q` — 23 passed outside the sandbox.
- `rtk proxy env FLOW_TEST_PROFILE=delivery-transfers APP_BE_ARTIFACT_DIR=/tmp/app-be-030-transfer-evidence UV_CACHE_DIR=/tmp/app-be-uv-cache uv run --env-file .envs/.backend python scripts/run_flow_test.py` — 13 passed, zero skips; owned PostgreSQL/S3/worker/Node profile and new committed-upload retention. Final gate reruns these against the final outbox source.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run ty check` — passed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run pytest tests/docs/test_consistency_contracts.py tests/scripts/test_contract_inventory.py tests/docs/test_frontend_docs.py::test_documentation_links_are_portable_and_targets_exist -q` — 20 passed.

Producer export requires both repository/source import roots and the existing synthetic test configuration. Earlier invocations lacking import roots/settings failed; loading the local environment directly also exposed its incompatible LOG_OUTPUTS syntax before output generation. The corrected invocation is `rtk proxy env PYTHONPATH=src:. UV_CACHE_DIR=/tmp/app-be-uv-cache uv run python -c 'import tests.conftest; from scripts.export_wave_four_contracts import main; main()'`. It uses the same synthetic configuration as the deterministic generator tests and performs no service/data writes. No environment file is modified.

Final executed command: `rtk proxy env APP_BE_ARTIFACT_DIR=/tmp/app-be-030-final-browser mise run check` — all 15 stages passed, 873 default tests with 182 opt-in integration exclusions, one doctest and 85 required integration tests with zero failures/skips. Start/end source SHA256: `f74ff6fa52ac8dabb1cf2e348f9f02029c36bdfef200dac4fbe3f65f517ba4a3`, identical. The secret scanner reports no findings and all applicable pre-commit hooks passed. Private logs and full source proof remain in the gated artifact directory recorded in portable verification.

APP-BE-030 is DONE for inspected implemented scope; APP-BE-032 can credit this prerequisite but remains blocked by APP-BE-029/031. Next in the requested sequence is APP-BE-021, pending the explicitly requested owner decision on the exact pilot policy. No approval is inferred from silence or the general implementation request.
