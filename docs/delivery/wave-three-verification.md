# Waves one through three: observed verification

Date: 2026-10-08. Scope: APP-BE-001, 002, 003, 013, 004, 006, 030. Baseline commit: `995829eebd9483ac6b589c1648fc799c650ad464`; changes are uncommitted. Raw logs remain private in /tmp. No peer write, production deployment, paid-provider call or shared database reset occurred.

APP-BE-001 is DONE as baseline/intake analysis. The other six tasks have prepared implementations/design/review but remain open. D01 migration approval and D07 warning-exception approval have no owner response recorded. Backlog copies are synchronized; dependent tasks are not promoted to DONE from partial evidence.

| Command/evidence | Observed outcome |
| --- | --- |
| Initial unchanged `mise run check` | 685 default passes, 119 opt-in skips, one doctest, four disposable PostgreSQL workflow passes; all applicable hooks passed |
| Focused gate/map/catalog/query/runner regressions | 49 passes; native negative probes deliberately asserted Ruff, ty, Python warning and pytest failures |
| Strict resource-cleanup/query/gate checks | 16 passes with -W error |
| Exact SDK filter configuration and exclusion regressions | Seven passes with -W error; deliberate warnings captured inside their assertion context |
| Current `mise run check` | Lock, format, lint, docstrings, typing, security and doctest passed; test stage failed: five SDK tests, 715 passes, 130 explicit opt-in skips |
| Current `mise run check-baseline` default suite | 720 passes, 130 opt-in integration skips; four fresh PostgreSQL workflow passes and all applicable hooks passed |
| Disposable populated migration/seed/live-query profile | Initial result: 14 passes, one failure at Alembic schema drift. Fixture data/pin/media/history assertions passed before the drift assertion |

Strict report: `/tmp/app-be-check-26i1vvvd/report.json`, with per-stage commands, times, return codes, installed/locked tool versions, individual test exclusions, git/diff/source hashes and private logs. Raw complete output: `/tmp/app-be-strict-completion.log`. Strict flow/precommit stages were not run after the failed test stage; they must not be claimed passed by that invocation. The separately run historical gate retains its exact two pre-existing SDK filters and is not warning-free readiness.

Baseline output: `/tmp/app-be-baseline-completion.log`. Required integration output/JUnit: `/tmp/app-be-foundation-reviewed.log` and `/tmp/app-be-foundation-reviewed.xml`. The cache acceptance test uses an owned temporary Dragonfly container, a private namespace and a random local port. Targeted cache acceptance passed (one test; fifteen deliberately deselected); `/tmp/app-be-cache-acceptance.log` and its JUnit retain that scope. The full profile rerun separately retains every required outcome. Docker's existing sample_cache image is the test prerequisite; no production cache is cleared.

SDK blockers: Cohere 7.2.0 invokes deprecated asyncio coroutine detection; Google GenAI 2.29.0 uses the deprecated private typing union alias. Targeted compatible upgrades resolved those same versions. No SDK file patch, monkeypatch, blanket filter or new ignore was added. The strict runner exposes actual provider-construction failures. An exception, if approved, must be labeled VERIFIED_WITH_EXCEPTION and cannot claim strict warning-free readiness.

Migration blocker: current head c24f913ab601 lacks five model column comments on WORKFLOW_WORKSPACE. The minimal additive repair is specified in [migration-verification.md](migration-verification.md); neither existing revision was edited. The failing Alembic assertion remains active. Destructive tests verify the exact owned disposable database and local host, and cleanup removes it after failure as well as success.

Default skips are environmental opt-ins, including PostgreSQL, storage, workers, recovery/volume and migration profiles. They do not establish those capabilities. The required foundation profile runs its seed, live-query, selector, authorization, cache and migration scenarios explicitly. Broader worker/provider/storage/browser/rebuilt-image acceptance remains later-wave scope.

The API snapshots/inventory remain the APP-BE-001 baseline, with 314 operations and 425 schemas. These changes add no HTTP route or wire field. The permission inventory, current query matrix, notification design and scoped findings register link the exact owning files and remaining acceptance work.

The strict evidence above predates only small cache/authorization fixture refinements and the final documentation annotations; application behavior is unchanged. A final strict rerun is recorded below after completion.


Final observed outcomes:

- Complete foundation profile: **15 passed, one failed**, zero skipped with native -W error. The sole failure is the five-comment Alembic drift assertion. Real seed concurrency, selector/restore counts, authenticated restore denial and Dragonfly cache invalidation passed. All owned database/container resources were removed.
- Final strict gate: **715 passed, five SDK failures, 130 documented opt-in skips**. Earlier stages including security/typecheck/doctest passed. Evidence: `/tmp/app-be-strict-reviewed-final.log`, `/tmp/app-be-check-_yrd1faq/report.json`. Flow/precommit did not run in this failed strict invocation.
- Historical complete gate: exit zero, **720 passed, 130 opt-in skips**, one doctest, **four real PostgreSQL workflow tests**, all applicable hooks passed. Evidence: `/tmp/app-be-baseline-completion.log`. This run retains only the two original SDK exceptions and is not strict readiness.
- AST graph refreshed successfully; no semantic LLM extraction or paid call was requested. `git diff --check` passed. Backlog copies differenced only in Markdown whitespace before being synchronized.

Subsequent record annotations change documentation only. The private strict report hashes the exact source state at its own invocation, including untracked files; it is not a deployment/tree-cleanliness assertion.

## Wave-four decision update — 2026-10-08

D01 additive migration policy and D07 two exact SDK exceptions are now owner-approved
in `docs/delivery/approved-decisions.json`. Statements above about missing approval
are historical. Both applied migrations remain byte-identical; the final owned
foundation profile passes 16 tests with no skips at the new single head, including
upgrade preservation and schema-drift check. Additive revisions repair the five
comments and introduce users-owned preferences and compact help state.

The complete gate remains blocked by eight independently reviewed secret-scanner
false positives awaiting specific baseline authorization; no SDK approval is inferred
for that separate security control. Current evidence: `docs/delivery/wave-four-verification.md`.
