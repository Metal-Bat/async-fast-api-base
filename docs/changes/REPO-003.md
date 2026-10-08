# REPO-003 — Make local workflow checks self-starting and scope SDK notices

Backlog: REPO-003
Date: 2026-10-08
Area: repository/testing

## Summary

The workflow runner probes local PostgreSQL and starts the configured Compose service when
the default local port is unavailable. Pytest filters only two known upstream SDK deprecations.

## Why

REPO-002's manual PostgreSQL startup did not make subsequent quality-gate runs self-contained.
A stopped service still caused a raw connection-refused traceback. The installed Cohere and
Google GenAI SDKs also use deprecated Python APIs; targeted uv resolution found no newer
compatible releases in this environment.

## What Changed

- Probe an authenticated local connection before creating a disposable database. For port
  5432 only, start `docker compose up -d postgres` if the connection is unavailable, then make
  at most 15 readiness attempts. Compose has a 60-second timeout; connection attempts have
  two-second timeouts and one-second pauses. Blocking Compose work runs in a worker thread.
- Preserve the local-host restriction, leave working servers alone, and do not start Compose
  for authentication errors. Custom ports require manual startup; `FLOW_TEST_AUTOSTART=0`
  disables automatic startup on the default port too.
- Return safe setup guidance instead of raw exception text. Preserve migration/test exit codes,
  attempt disposable-database cleanup after failures, and report its name if cleanup fails.
  Cleanup failure cannot turn a failed test into a success.
- Add exact pytest message/category/module filters for Cohere's coroutine check and Google
  GenAI's private union alias. Do not modify site-packages, patch Python globals, or hide
  application and unrelated SDK warnings. Regression tests verify the filter boundaries.

## Architecture

No application architecture change. Infrastructure startup is limited to the local test runner;
production startup and provider execution retain their existing behavior.

## Compatibility

No package versions, API contracts, or database schema changed. Docker Compose and matching
`.envs/.backend` and `.envs/.postgres` credentials are needed for automatic service startup.
The configured application database is not migrated or deleted. A service started by the
runner remains running. SDK deprecations are contained in pytest output, not fixed upstream;
remove the exact filters when compatible SDK fixes arrive. They do not guarantee support for
future Python versions that remove these APIs.

## Validation

Eight runner regressions failed before implementation.

Commands executed:

- `rtk proxy uv lock --upgrade-package cohere --upgrade-package google-genai` — resolved without
  changing the installed versions or lockfile.
- `rtk proxy uv run pytest -q tests/scripts/test_run_flow_test.py tests/utils/test_warning_policy.py tests/apps/ai/test_providers.py`
  — 56 passed with no warnings.
- `rtk proxy mise run check` — passed: 681 default tests, 119 opt-in skips, one doctest, four
  PostgreSQL workflow tests, and all applicable static/security/all-file hook checks. No warning
  summary. The real run started the stopped Compose service and removed its disposable database
  after migrating to the current head and passing the workflow tests.
- `rtk proxy uv run pre-commit run --files scripts/run_flow_test.py tests/scripts/test_run_flow_test.py tests/utils/test_warning_policy.py pyproject.toml`
  — all applicable hooks passed, including the new untracked tests.
- `rtk proxy graphify update .` — AST graph refreshed.
- `rtk proxy git diff --check` — passed.

Result: PASS for the local quality gate. Live provider calls, other opt-in infrastructure suites,
and browser acceptance were not run. The automatically started PostgreSQL service remains running.

## Backlog Impact

All other tasks were reviewed and are DONE. This extends REPO-002's local gate repair.

Enabled: None

Blocked: None

Superseded: None

Conflicts: None

## References

Commit: None

Pull Request: None

Additional notes:

- [Workflow regression setup](../testing/full-workflow-regression.md)
- [Dependency warning policy](../operations/dependencies.md)
- [Google GenAI upstream warning](https://github.com/googleapis/python-genai/issues/1640)
