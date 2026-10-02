# DOCS-002 — Execute the documented HTTP workflow

Backlog: DOCS-002
Date: 2026-10-02
Area: documentation/testing

## Summary

Validated the documented requester/reviewer sequence through real HTTP routing, authentication
and PostgreSQL. The standard disposable flow runner now includes that regression alongside the
existing complex purchase service journey. Corrected the setup instructions needed to reproduce it.

## Why

DOCS-001 validated synthetic contracts and a service journey but explicitly lacked full HTTP
login-to-completion evidence. The user asked to check the steps and establish that the process
works. Passing schema validation alone cannot establish grants, data handoff or session behavior.

## What Changed

- Added `tests/integration/test_frontend_journey.py`. Provisioning uses application services and
  ORM against a fresh migrated database. User operations go through the real ASGI app and its
  middleware/routes with real ordinary-user passwords, roles and bearer sessions; there are no
  authentication dependency overrides.
- Verify login, missing permission, request ownership, draft save, invalid submit, stale-save
  conflict, submit replay, available work, unauthorized claim, claim replay, task view, invalid
  completion, completion replay, changed-payload rejection and final request completion.
  Closed-task views expose no actions. Refresh rotates tokens; reuse revokes the family; logout
  prevents the revoked session from accessing the profile. Assert documented HTTP and error codes.
- Extended `scripts/run_flow_test.py` to execute both journeys after fresh Alembic migration,
  retaining local-host restriction and unconditional disposable database cleanup.
- Clarified that `requests.start` must exist before assigning a role containing it, field-policy
  scopes use `/properties/amount`, and the example's human task needs explicit data handoff via
  `inherit_previous: true`. Without handoff an unbound human form opens empty.
- Updated frontend and testing guides with exact setup, expected two-pass result, verification
  boundaries and a deployment/browser/reader acceptance checklist.

## Architecture

No application architecture change. Added integration coverage at the documented HTTP boundary.

## Compatibility

No runtime routes, DTOs, authorization rules, schema, migrations or dependencies changed.
`mise run flow-test` now runs two tests and takes longer. Tests require local PostgreSQL and
remain opt-in outside the flow runner. HTTPX ASGI transport does not enter application lifespan;
S3 startup and external services are outside this regression's scope.

## Validation

Commands executed:

- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync python -` — loaded test environment defaults,
  selected the temporary PostgreSQL container's local port and synthetic credentials, and executed
  `scripts/run_flow_test.py` via `runpy.run_path(..., run_name="__main__")`. Fresh migration and both
  workflows passed: **2 passed in 12.48s**. The database was dropped and container removed.
  Initial iterations exposed test setup assumptions (absent permission and empty task data) and
  confirmed protected-session rejection uses 2001, while refresh rejection uses 2004.
- `rtk proxy timeout 120s uv --cache-dir /tmp/uv-cache run --no-sync pytest -q`
  — **628 passed, 114 skipped**, seven dependency deprecation warnings. Opt-in infrastructure
  tests are skipped here; the two journeys were separately executed above.
- `rtk proxy tsc --strict --noEmit --target ES2022 --module ES2022 --lib ES2022,DOM docs/examples/frontend-client.ts` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache lock --check --offline` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync ruff check .` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync ruff format --check .` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync ty check` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync ruff check src/utils --select D101,D102,D103,D104` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync pytest -q tests/conftest.py src/utils --doctest-modules` — one passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync bandit -r src -q` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync python scripts/check_secrets.py` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync pre-commit run --all-files` — applicable hooks passed on tracked files. Ruff and pytest also cover the untracked test.

- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync pre-commit run --files scripts/run_flow_test.py tests/integration/test_frontend_journey.py BACKLOG.md` — passed, including the new untracked files.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync pytest -q tests/docs` — six passed after final documentation edits.
- `rtk proxy graphify update .` — AST graph refreshed outside sandbox after its multiprocessing
  restriction blocked the first attempt.

Result: PASS for the defined automated workflow validation. No browser application, deployed
network/lifespan, competing-claim race, external delivery/storage/telemetry, or reader usability
was exercised by this HTTP regression. The deployment checklist keeps those separate; this is
not a claim that the entire production environment has been certified.

## Backlog Impact

All unfinished tasks reviewed; no conflicting work or changed dependencies found. DOCS-001's
HTTP evidence gap is covered; its historical result remains unchanged. Browser and reader
acceptance remain separate manual work.

Enabled: None

Blocked: None

Superseded: DOCS-001's absence of HTTP journey evidence for the current repository.

Conflicts: None

## References

Commit: None

Pull Request: None

Additional notes: [Frontend walkthrough](../guides/frontend-journey.md),
[workflow validation and deployment checklist](../testing/full-workflow-regression.md).
