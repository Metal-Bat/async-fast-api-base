# APP-BE-005.2 — Usable workflow primitives and local inserts

Backlog: APP-BE-005.2
Date: 2026-10-17
Area: step_types/extensions, scripts/demo, workflow and form libraries, Compose

## Summary

The default local seed inserts five executable workflow control families, sixteen
published reusable workflow examples, eight reusable data types and three input
components. Each example/type/component carries a purpose and valid sample.
`mise run demo-seed` is a local Python insert command. The Compose seed service and
its dedicated Docker development target are removed.

## Why

The former default populated thousands of business cases while its reusable library
mostly contained contact, address and budget objects. It did not supply the requested
math, comparisons, boolean operations and if/else controls. A separate seed container
also made an ordinary local insert need an unnecessary image/service workflow.

## What Changed

- `src/apps/step_types/extensions/primitives.py` registers ARITHMETIC, NUMBER_COMPARE,
  BOOLEAN_LOGIC, IF_ELSE and SELECT_VALUE through the existing trusted registry.
  Strict typed ports validate inputs and outputs; arithmetic rejects nonfinite values
  and zero divisors. It uses ordinary JSON numbers, not exact money arithmetic.
- AND/OR combine two booleans; NOT inverts the left operand. IF_ELSE returns explicit
  true/false outcomes. SELECT_VALUE chooses one supplied JSON value, including null,
  without branching. Existing process execution and attempt handling remain the owner.
- `scripts/demo/workflow_library.py` provides five arithmetic examples, six numeric
  comparisons, AND/OR/NOT, if/else routing and value selection. Each is a published
  subprocess with explicit typed ports and sample inputs. Both if/else finishes connect.
  Only one published version is created per new reusable definition.
- The eight data types describe text, integers, numbers, booleans, dates, timestamps,
  bounded number lists and labeled numeric records. Three form components enter numeric
  operands, boolean operands or conditional labels. Samples validate against their schemas.
- The default script installs only this library and missing ordinary installation
  accounts through existing services. Existing installation identity and private
  credentials are reused. The script adds missing records but refuses changed,
  deleted, disabled or retired definitions instead of replacing published pins.
- `--with-demo-cases` explicitly enables the former large business dataset in addition
  to the library. No service is started by the local seed command. Database hostname
  `postgres` maps to the existing host port; optional full-demo dependencies must have
  host-reachable endpoint configuration.
- English/Persian/Arabic primitive names/help, the seed inventory and current guides
  document the new library. Existing API envelopes, operation IDs and schema routes
  are unchanged; handler config schemas are discovered through current dynamic metadata.
- Regenerated all three current producer inspector slices and their manifest. Migration
  unit/integration tests now assert the exact frozen baseline plus the exact five local
  extension families, and prove startup reconciliation leaves the new versions DRAFT.

## Architecture

### Before

A Compose development image ran the rich business seed. Deployed step examples exposed
application lookups but not reusable computation/control primitives.

### After

A local one-shot command calls existing account, step, workflow and library owners.
Pure trusted step classes execute through the existing engine; reusable workflows
are regular published subprocess definitions. The optional business seed retains its
existing service-owned lifecycle transitions.

### Reason

Provide real workflow construction tools and explicit small inserts without a parallel
executor, duplicate table model or separate running seed service.

## Compatibility

No applied migration, database schema, dependency, route or envelope changes. Dynamic
handler/inspector metadata gains the five new families through existing contracts.
Existing business seeds and operator records remain intact; new definitions use an
installation-bound `wf.<installation>.` namespace. Existing persisted step fingerprints
are not changed. Existing APIs/workers must load the new source before using new steps;
restart long-running worker processes after updating. Source-only runtime deployments
must include these files in their normal application image.

The deliberate CLI change is the small default. Use `mise run demo-seed --
--with-demo-cases` for the larger dataset. No Docker seed build is needed.

## Validation

Commands executed:

- Focused primitive tests first failed with unregistered handlers; all 17 then passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run pytest -q tests/scripts/test_demo_seed.py tests/scripts/test_workflow_library_seed.py tests/apps/step_types/test_workflow_primitives.py`
  — 27 passed before the additional default-mode regression. The initial sandbox CLI
  attempt failed writing the uv cache; the elevated rerun passed.
- `rtk proxy mise run workflow-library-test` — passed against an owned migrated
  PostgreSQL database, then passed again on final source (9.56 seconds). It publishes
  all definitions, executes every workflow and both if/else branches, verifies repeat
  inserts and refuses an operator-disabled type. Its disposable database was removed.
- `rtk proxy docker compose config --services` — confirms there is no seed service.
- Ruff format/lint and `ty check` — passed on final code.
- `rtk proxy uv --cache-dir /tmp/uv-cache run pytest -q tests/migrations/versions/test_step_type_seed.py tests/docs/test_consistency_contracts.py`
  — 14 passed after regenerating metadata and correcting frozen-baseline coverage.
- `rtk proxy mise run delivery-foundation-test` — all 18 passed after updating its
  explicit baseline/reconciliation assertions; disposable database removed.
- Actual `python -m scripts.demo_seed --state-directory ...` was exercised twice
  through the owned flow runner and `/tmp/test_workflow_seed_cli.py`. Both local CLI
  calls returned the expected 5/16/8/3 counts and the private account export contained
  exactly three accounts. The owned database was removed; no seed container was used.
- `rtk proxy mise run precommit-check` — passed; hooks also ran explicitly on all five
  new source/test files so untracked files were included.
- `rtk proxy graphify update .` — AST refresh passed (16,001 nodes, 39,476 edges).
- `rtk proxy mise run check` — first run `/tmp/app-be-check-tphbk7ed` failed on stale
  inspector artifacts and the old all-extensions-in-baseline assertion; both fixed.
  Second run `/tmp/app-be-check-83yhveq4` passed 1,021 tests but failed the analogous
  integration baseline assertion and its subsequent connection-cleanup cascade;
  that assertion was fixed and the focused foundation profile passed all 18 tests.
  Final run evidence is in `/tmp/app-be-check-xc2_zbzj`; main suite passed 1,021 tests
  with 226 documented opt-in integration exclusions. Formatter, lint, types, security,
  doctest, four workflow scenarios, all 18 foundation tests and all 31 wave-four tests
  passed. The transfer profile passed 58 tests and failed only
  `test_owned_swagger_browser`: the configured executable
  `/tmp/cons-be-browser/chrome-headless-shell-linux64/chrome-headless-shell` is absent.
  The full gate exited 1 without weakening the browser requirement or warning policy.
- `rtk proxy mise run delivery-through-020-test` — nine passed separately after the
  full gate stopped; owned database removed.
- `rtk proxy mise run delivery-completion-test` — twelve passed separately; owned
  database removed.
- `rtk proxy mise run delivery-restore-test` — two passed separately against owned
  storage/worker/database resources; disposable resources removed.
- Final source comparison saved in `/tmp/workflow-seed-source-comparison.json`: only
  `BACKLOG.md`, this record and the seed guide changed after the final gate started.
  Python source, tests, configuration and producer metadata stayed identical. Checkout HEAD remains
  `4a5ec27f9f14eba7ad7fd7bbfa5280a7ed77d272`; the earlier scheduler repair was already
  present in the working tree when this seed task began.

Result: PARTIAL. Task-specific database/CLI acceptance and all available independent
stages passed; the complete gate remains blocked by the required browser executable.
No shared library/dataset insert, browser, hosted or user acceptance has been claimed.

The running development API's auto-reload created intermediate DRAFT snapshots during
implementation. A guarded local repair checked that exactly the five version-one
drafts were unused and their schemas, metadata and fingerprints exactly matched this
task's earlier definitions, saved their originals to
`/tmp/workflow-primitive-intermediate-drafts.json` (0600), then refreshed them through
`StepTypeService.revise_version`. Published versions were not changed or created.
API restart was attempted afterward; startup remains unavailable because its existing
S3 container is stopped. Cache and broker are also stopped; the local seed CLI was
verified independently of those dependencies. These external services were not started
by the default seed command.

## Backlog Impact

All unfinished tasks reviewed; the earlier scheduler repair remains separate. Existing
APP-BE-038 still depends on actual conversation/action implementation and connected
acceptance. This library does not implement or complete those features.

Enabled: None

Blocked: None

Superseded: None

Conflicts: None

## References

Commit: None

Pull Request: None

Additional notes: `docs/guides/demo-seed.md` lists every inserted item's purpose.

## Current-source verification closure — 2026-10-26

Status: DONE for this bounded task. Verification: VERIFIED_WITH_EXCEPTION under
the existing two exact D07 SDK exceptions; never strict exception-free or demo ready.

The owner requested cross-repository backlog selection and execution. The current
complete backend gate exits 0 and passes all sixteen stages. The exact invocation,
including browser/cache environment, is retained in the peer evidence commands.json:
1,032 default tests, one doctest and 142 mandatory service cases, zero mandatory
skips and emitted diagnostics. The 233 documented default opt-in exclusions are
reported separately. The current-source comparison finds no changed maintained
files between gate start and completion. The original failed/partial evidence
above remains historical and is not removed.

The focused scheduler/Celery and seed/primitive invocation retained in commands.json
passes all 51 tests. The installed
browser is explicitly selected through the existing setting; no test, diagnostic
threshold or timeout is weakened. `rtk proxy mise run workflow-library-test`
separately passes its actual publication/execution/both-branches/rerun-preservation
scenario on an owned migrated database, which is removed afterward.

The current pair separately passes all 44 actual workflow/browser scenarios with
exact live OpenAPI agreement, unchanged functional sources and no browser/service
diagnostics. Existing local infrastructure and API startup are restored, and
health/readiness return 200. The development database remains at 0003_arabic;
rolling out 0004_binding_source_schema is a separate reviewed backup/upgrade action
under APP-BE-031/032. No shared reset, stamp or deployed migration is performed.

Evidence is retained in the peer frontend's artifacts/roadmap-2026-10-26/: the
backend-check-first native report/logs, backend-first-source-comparison.json,
backend-focused.log, workflow-library.log and paired-workflows/manifest.json.
The final documentation-qualified complete gate and actual native result belong
to backend-check-final/ and completion.json there. Missing or failed final evidence
must be reported; this section does not preclaim that later run.

The unfinished-only backlog removes this completed task while preserving its
stable ID and original implementation/history here. APP-BE-031/032 and the
remaining Agent, Calendar, notification, mapper and assistant owners retain their
existing prerequisites and acceptance boundaries. No new feature task is allocated.
Hosted, deployed, manual and user acceptance remain separate.
