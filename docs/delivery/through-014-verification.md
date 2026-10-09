# Work through APP-BE-014: verification

Date 2026-10-08. Baseline 995829eebd9483ac6b589c1648fc799c650ad464 plus preserved
uncommitted APP work. Scope extends through 014: 010 reused, 011/012 added as read-only
projections, 013 updated from actual producer/channel evidence, 014 extends existing
notification persistence/outbox/worker. No commit, deployment, peer write or shared reset.

## Completed observations

- Readiness/inbox red tests failed on absent modules; exact client query failed before
  adding its input. Legacy serializer red test proved private content survived target
  revocation, then the serializer was corrected. Logs retain those observed failures.
- Initial readiness PostgreSQL profile: 1 passed (4.60 s). Exact published pins, missing
  form, disabled client, empty candidate groups and setup HTTP authorization: 1 passed
  after integration found and fixed the step_types/step_versions kind mapping (14.51 s).
- Unified account inbox: 1 passed (3.06 s), including rollback, dedupe, stale read,
  unread totals, recipient isolation and exclusion from legacy case searches.
- Real request/work-item event fanout: 1 passed (4.93 s), including repeated occurrence
  convergence, current refs and capability revocation.
- Actual Celery worker + encrypted secret + verified HTTPS email gateway: 1 passed
  (3.91 s), provider receipt and duplicate send handling.
- Complete application profile: 25 passed, no skips (64.49 s).
- Migration foundation: 16 passed, no skips (46.91 s), fresh/old-head upgrades, preservation,
  schema drift and original purchase/HTTP journeys at h014_unified_notifications.
- Complete owned transfer profile: 4 passed, no skips (14.24 s), actual storage/report
  worker, TLS notification worker/gateway and frontend-runtime transfer checks.
- Ruff/type checks passed after narrow SQLModel query/type fixes. Bilingual catalogs
  compiled; generated reference pages and contract snapshots refreshed.

The initial broad suite observed three failures: old admin-reset unit fixture lacked
an async flush/notice seam, generated reference pages were stale, and new subject tags
were not declared. The fixture now preserves its original audit assertions and also
checks the affected notification recipient; reference generation and subject metadata
were corrected. Final strict standalone suite/gate results are appended after execution.
No failed run is counted as a pass or masked by an automatic retry.

Required service tests use the owned disposable runner and clean up their databases,
containers and worker children. The default suite reports opt-in service exclusions;
the selected required profiles execute their service tests without skips. No paid/live
provider calls were made. TLS gateway receipt is a real local transport receipt, not
an SMTP/deployment/user-acceptance claim. Missing later MAP producers remain explicit.

## Approval history (superseded by final closure below)

D01 additive policy and D07's two exact SDK filters persist. New h014 schema preserves
applied revisions. Ten exact file/type/hash false positives are reviewed in
secret-baseline-review.json: eight public revision references, a synthetic local storage
username and a synthetic provisioned secret-reference identifier in the worker test.
The baseline is unchanged. The prior automatic approval review rejected mutating this
security control without specific authorization; generic backlog execution is not that
approval. Final closure requires explicit approval and a successful full mise run check,
with completion labeled VERIFIED_WITH_EXCEPTION for D07 rather than warning-free readiness.

## Final closure — 2026-10-08

The owner explicitly approved the exact ten baseline entries. Only those file/type/hash
tuples were added as non-secrets; byte/structure comparisons verified all existing entries
and scanner settings were preserved. The unchanged scan now reports no findings.

The first post-approval full gate observed 790 default passes but rejected the existing
test_services opt-in exclusion reason. A red/green regression now accepts only that exact
module/reason pair and still rejects xfail, unrelated modules and every required-suite skip.
The required application regression additionally verifies each real committed correction
round emits one applicant notice targeting the new correction work item, including replay.

Final command: `UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check`, exit 0.
Private report: `/tmp/app-be-check-unvbh0u6/report.json`. Public summary: [through-014-gate.json](through-014-gate.json).
Tested tree digest: `75b30d345e9c97d45e8cbd6da4a00571a4e66735bb462b82e7782db0c4b32064`.

| Stage | Result | Passed | Skipped |
|---|---|---:|---:|
| lock-check | PASSED | 0 | 0 |
| fmt-check | PASSED | 0 | 0 |
| lint | PASSED | 0 | 0 |
| docstrings | PASSED | 0 | 0 |
| typecheck | PASSED | 0 | 0 |
| security | PASSED | 0 | 0 |
| doctest | PASSED | 1 | 0 |
| test | PASSED | 791 | 155 |
| flow-test | PASSED | 4 | 0 |
| delivery-foundation-test | PASSED | 16 | 0 |
| delivery-wave-four-test | PASSED | 28 | 0 |
| delivery-transfer-test | PASSED | 4 | 0 |
| precommit-check | PASSED | 0 | 0 |

All thirteen stages passed; required service profiles had no skips or diagnostics.
Both applied migration files remain byte-identical to HEAD. Tracked and new files passed
the repository hooks; final gate-accounting/correction changes also passed focused hooks.
Graphify AST update completed: 15,094 nodes and 35,238 edges. No graph rebuild failure is
classified as success; the sandbox-denied attempt was followed by a successful owned run.

APP-BE-001–014 are complete; APP-BE-019 is also closed as the already implemented required
dependency of 012. Verification is VERIFIED_WITH_EXCEPTION under D07. Missing later
MAP-07/08/10/11/13 producers remain assigned to APP-BE-024/023/017/015. Frontend/browser,
production deployment, live providers and downstream SMTP acceptance remain separate.
Only completion documentation changed after the tested tree; no production/test code
was changed after the successful gate. No commit or deployment was performed.
