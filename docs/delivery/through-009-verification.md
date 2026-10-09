# Tasks through APP-BE-009: verification

Date: 2026-10-08. Candidate includes uncommitted work on backend baseline
`995829eebd9483ac6b589c1648fc799c650ad464`. Scope is APP-BE-001–009 inclusive;
prior wave-four work remains preserved. Implementation is prepared, not final
closure: the specific nine-entry secret-baseline review remains unapproved.

## Observed results

Commands use `UV_CACHE_DIR=/tmp/app-be-uv-cache`, `PYTHONPATH=src` for profiles and
`.envs/.backend` for the owned disposable migration runner.

| Command | Observed result |
| --- | --- |
| `uv run pytest -q tests/apps/users/test_saved_views.py tests/core/test_history_service.py` | 12 passed, 0.43 s: offsets/filter injection, columns/privileges, private-history exclusion and existing operational history |
| `FLOW_TEST_PROFILE=delivery-wave-four PYTEST_ADDOPTS='-k presets_replay -x' uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 1 passed, 19 intentionally deselected, 4.18 s: persisted replay/roundtrip, isolation, renamed/deleted favorite and schema-drift recovery |
| `FLOW_TEST_PROFILE=delivery-wave-four PYTEST_ADDOPTS='-k "saved_view_http or concurrent_default" -x' uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 2 passed, 19 intentionally deselected, 6.21 s: actual ordinary login/private HTTP CRUD and default race |
| `FLOW_TEST_PROFILE=delivery-wave-four PYTEST_ADDOPTS='-k "presets_replay or concurrent_default" -x' uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 2 passed, 19 deselected, 5.07 s: ordinary-role default/favorite races, stale update replay, permission revocation |
| `FLOW_TEST_PROFILE=delivery-wave-four uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 21 passed, no skips, 65.70 s: complete wave-four plus APP-BE-009 acceptance |
| `FLOW_TEST_PROFILE=delivery-foundation uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 16 passed, no skips, 47.41 s: fresh/old-head upgrade, preservation, drift/history, catalogs/live queries and original journeys at the new single head |
| `uv run ruff check . --fix`, `uv run ruff format .`, `uv run ty check` | Passed after targeted formatting/type fixes; final whole-project gate still required |

The DTO/service test initially failed on absent production modules. The HTTP test
captured the missing endpoint as 404 before route implementation. The new private
history test initially failed for both personal and preferences histories, proving
the generic reader exposed them; explicit table policy now prevents that exposure.
One focused preexisting history test relied on unrelated import order; it now imports
its owning model explicitly and passes independently.

All integration databases were uniquely owned and removed in finally blocks.
No shared downgrade/stamp/reset, applied migration rewrite, deployment or peer write
was performed. Earlier verified wave-three/four evidence remains in
`wave-three-verification.md` and `wave-four-verification.md`.

## Approvals and blockers

D01 approved additive migration policy; D07 approved only the two exact SDK warnings,
with passing completion labeled VERIFIED_WITH_EXCEPTION. Those replies do not authorize
changing the separate security baseline. The read-only scan found nine potential
secrets: eight public revision references plus a synthetic local storage username.
`secret-baseline-review.json` identifies exact file/type/hash entries. The baseline is
unchanged; no detection rule/filter/threshold has been weakened. The prior automatic
approval rejection explicitly required specific authorization for this control change.

Additional completed checks:

- Default suite with native warning errors and only D07's exact filters: 781 passed,
  149 explicitly opted-in integration skips, 40.15 s. Required profiles above and
  the transfer profile below execute their selected service tests without skips.
- Owned transfer profile: 3 passed, no skips, 19.97 s; actual storage, worker and
  frontend-runtime transfer checks completed and disposable services were removed.
- Pre-commit on tracked and untracked candidate files: all applicable hooks passed.
- `graphify update .`: succeeded using AST-only updates (14,894 nodes,
  34,635 edges, 776 communities).

The final gate result is recorded below after execution. No required integration
skip is represented as a pass.

Final `mise run check` on the prepared candidate exited 1 at the security stage.
Lock, formatting (759 files), lint, utility docstrings, typing and Bandit passed;
Bandit reported no issues. Detect-secrets reported the nine entries in the review
file. Private gate evidence: `/tmp/app-be-check-g5qtgp0u`; command log:
`/tmp/app-be-009-final-gate.log`. Later gate stages were not executed by this run;
standalone completed profiles/suite/hooks are recorded above. The baseline remains
unchanged pending specific approval.

Remaining standalone stages completed under native warning errors plus the two exact
D07 filters: `mise run doctest` passed 1 test (1.93 s), and `mise run flow-test`
passed all 4 purchase journeys (26.65 s) at the new migration head. The latter's
disposable database was cleaned up by the owned runner. Logs: `/tmp/app-be-009-doctest.log`
and `/tmp/app-be-009-flow-test.log`. These checks do not bypass or convert the failed
security gate into a pass.
