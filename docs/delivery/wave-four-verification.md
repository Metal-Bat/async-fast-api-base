# Wave-four verification evidence

Candidate: backend baseline `995829eebd9483ac6b589c1648fc799c650ad464` plus
uncommitted work; full generated contracts are hashed in `wave-four/manifest.json`.
Current status: **IMPLEMENTED, final gate blocked**. No deployment, browser acceptance
or FULL_DEMO_READY claim is made.

## Approved decisions and remaining gate

Owner replies on 2026-10-08 approved additive migrations (D01), preserving both applied
revisions and the five workspace comment repairs, and the two exact Cohere/Google SDK
deprecations (D07). Approval is recorded in `approved-decisions.json`. A future passing
gate must therefore say VERIFIED_WITH_EXCEPTION, not warning-free readiness.

The first full `mise run check` failed at security after passing lock, formatting,
lint, docstrings and typing, with Bandit reporting no issues. detect-secrets flags
seven public revision identifiers and one synthetic local storage username. Automatic
approval review rejected changing `.secrets.baseline` without specific authorization.
The exact file/type/hash proposal is `secret-baseline-review.json`; approval remains
pending and the baseline is unchanged. No scanner, warning scope or threshold is weakened.

## Observed commands

Commands used `UV_CACHE_DIR=/tmp/app-be-uv-cache`; integration commands also used
`PYTHONPATH=src` and `.envs/.backend`. Logs contain private diagnostic context and stay
outside committed artifacts. Safe summaries are retained here.

| Command | Observed outcome |
| --- | --- |
| `FLOW_TEST_PROFILE=delivery-wave-four uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 18 passed, no skips, 53.86 s; demo services, groups, profiles, concurrent settings, avatars, help, durable links, metrics and ordinary-user HTTP contracts |
| `FLOW_TEST_PROFILE=delivery-foundation uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 16 passed, no skips, 39.46 s; old-head upgrade/data preservation, single-chain/fresh schema drift, history/guards, catalogs/live queries and original HTTP flow |
| `FLOW_TEST_PROFILE=delivery-transfers uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 3 passed, no skips, 21.69 s; real owned report worker and storage, maximum upload/report transport through actual Node boundary, oversized requests and owned assets |
| `FLOW_TEST_PROFILE=delivery-wave-four PYTEST_ADDOPTS='-k metrics_match -s' uv run --env-file .envs/.backend python scripts/run_flow_test.py` | 1 passed, 17 intentionally deselected, 11.23 s; EXPLAIN ANALYZE controlled metric fixture used Index Scan, actual rows 4, 2 shared hits, 0.042 ms execution; no production timing claim |
| `uv run pre-commit run --all-files` | Passed configured hooks; XML hook had no applicable files; covers tracked files only |
| `pre-commit run --files` with the exact `git ls-files -co --exclude-standard` inventory | Passed hooks across tracked and newly added files; no staging/commit |
| `mise run test` with native warnings-as-errors and the two exact approved SDK filters | Final corrected suite: 772 passed, 146 separately reported opt-in integration skips, 42.27 s |
| `uv run pytest -q tests/test_main.py tests/docs/test_frontend_docs.py tests/delivery/test_wave_four_exports.py` | 12 passed, 5.58 s; route/tag inventory, regenerated response references, localized artifact integrity/security/header contracts |
| `mise run doctest` with the exact approved warning policy | 1 passed, 0.66 s |
| `mise run flow-test` with the exact approved warning policy | 4 passed, no skips, 26.56 s; original disposable purchase/HTTP journey |
| `uv run ruff check . --fix`, `uv run ruff format .`, `uv run ty check` | Passed after targeted fixes; final full gate still required |
| `uv run pytest -q tests/delivery/test_authoring_metadata.py tests/delivery/test_transfer_bounds.py tests/utils/test_s3.py tests/apps/designer/test_designer_catalog.py` | 18 passed, 5.64 s |

Every integration profile creates a uniquely named owned `bpms_flow_` database and
removes it afterward. Transfer fixtures additionally create/remove only their own
local storage/cache containers, bucket, queue, Celery worker and Node/Uvicorn processes.
No shared database downgrade, stamp, volume deletion or migration rewrite was used.

## Failure history

Earlier focused tests caught and corrected stale form publication refs, unpublished
built-in step discovery, initial help typing, resource-kind alias validation,
avatar and preference concurrency handling, system Node version incompatibility,
readiness paths, missing owned-service imports and decode/archive preflight bounds.
Demo operator-added versions initially failed the intended conflict test; version-count
guards now refuse that changed installation. The new HTTP test initially used the
proposed `/requests/search`; it now verifies the actual `/business-requests/search`.

The first broad candidate default suite reported 767 passed, 146 opt-in skips and
three failures: response references and the route/tag inventory required the new
endpoint contracts. These failures are being corrected and must pass in the final
candidate. Default opt-in exclusions are never reported as integrated passes; mandatory
wave-four/foundation/transfer suites run independently without skips.

The corrected default suite passes as recorded above. A final gate attempt exposed
an unsorted export import; the correction passes Ruff and all-file hooks. The subsequent
`mise run check` report at `/tmp/app-be-check-1h176kye/report.json` passes lock,
formatting, lint, docstrings, typing and Bandit, then fails on the unchanged eight
secret findings. Test/doctest/flow/hook stages did not run in that failed gate invocation;
the separately executed results above must not be attributed to it.

## Evidence boundaries

The report transport maximum fixture is a labeled synthetic artifact. Actual encrypted
report generation runs through the real worker separately. Dropped-stream closure is
tested at S3 context ownership and the paired response boundary. Download counters
represent authorized starts, not successful completion. Legacy report SHA-metadata
absence is documented rather than retroactively claimed verified.

No actual frontend help catalog exists at the reviewed peer snapshot. The supplied
metadata example is synthetic; absent metadata returns safe compatibility status.
Browser/device/performance profile D05, hosted rebuilt-image tests, full connected
business operation, live providers and user acceptance belong to later tasks.

The required AST-only `graphify update .` succeeded after its initial sandbox-denied
rebuild: 14,750 nodes, 34,106 edges and 798 communities. Both applied migrations were
compared against git HEAD again and remain byte-identical. Backlog copies are
synchronized; all seven wave-four records link prepared implementation and observed
evidence, with BLOCKED status until the full gate can pass.
