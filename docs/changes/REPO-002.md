# REPO-002 — Restore the quality gate after dependency updates

Backlog: REPO-002
Date: 2026-10-08
Area: repository/dependencies

## Summary

Restore compatibility with the installed uv dependency set while preserving the existing
quality gates and application behavior. The requested delivery also includes the previously
uncommitted frontend runtime and studio workspace changes.

## Why

`mise run check` stopped on 203 type diagnostics after dependency upgrades. Once those were
resolved, the secret scanner identified seven unreviewed fixture/schema values, and doctest
collection exposed a missing async database dependency. SQLAlchemy 2.1 no longer installs
greenlet by default, so the application could not import its async session infrastructure.

## What Changed

- Declare `sqlalchemy[asyncio]` in `pyproject.toml`; uv resolves greenlet in `uv.lock` so a
  synchronized environment includes the dependency required by the existing async code.
- Make 197 optional truth tests explicit with `bool(...)`. Preserve the existing treatment
  of null, empty strings/collections, false, and zero rather than changing presence semantics.
- Use variadic SQLAlchemy Select typing for multi-column report queries and Generator return
  annotations for context managers. Use an explicit SQL literal in the logging regression.
- Keep the deliberately invalid plugin configuration test and use the current checker's
  specific diagnostic suppression for that intentionally invalid assignment.
- Add seven individually reviewed secret-scan fingerprints: two Alembic revision identifiers,
  synthetic hidden-field values and connection references, and a randomized-password prefix.
  No scanner rules or test gates are disabled.

## Architecture

No architecture change from the gate repairs. Existing async session, query, and context-manager
boundaries remain intact.

## Compatibility

Run `uv sync --locked` to install the async extra. The quality-gate fixes introduce no new
API or database behavior. The accompanying pre-existing feature work includes the additive
`c24f913ab601` workspace migration after `b13a0c7d2e44`; deployment must apply the current
Alembic head. That migration is distinct from the dependency compatibility repair.

## Validation

Commands executed:

- `rtk proxy mise run check` — final combined run passed: lock consistency, Ruff format/lint,
  utility docstrings, Ty, Bandit, detect-secrets, one doctest, 664 default tests, four disposable
  PostgreSQL workflow tests, and all applicable all-file pre-commit hooks.
- `rtk proxy mise run flow-test` — four passed on the standalone retry; temporary database removed.
- `rtk proxy mise run precommit-check` — all applicable hooks passed.
- `rtk proxy uv pip check --cache-dir /tmp/uv-dependency-refresh-cache` — 208 installed packages
  compatible.
- `rtk proxy graphify update .` — refreshed the AST graph successfully.
- `rtk proxy .venv/bin/cz check --commit-msg-file /tmp/platform-commit-message.txt` — accepted.
- `rtk proxy git diff --cached --check` — passed.

Result: PASS for the requested local quality gate. The default suite skips 119 opt-in service
tests; live provider, worker/storage and browser acceptance were not run. Seven third-party SDK
deprecation warnings remain. The SQL logging regression and existing import collection verified
the compatibility repairs without changing test expectations.

PostgreSQL initially was not running. It was started using `docker compose up -d postgres`.
An administrator shutdown interrupted the first database run; its retry and the final combined
gate passed. The runner removed each disposable workflow database. Local PostgreSQL remains running.

## Backlog Impact

All existing tasks were reviewed and were already DONE. REPO-001's exact-fingerprint secret
baseline policy is preserved. The historical DB-001 consolidation remains the initial schema;
the accompanying workspace migration extends it.

Enabled: None

Blocked: None

Superseded: None

Conflicts: None

## References

Commit: None

Pull Request: None

Additional notes:

- [Frontend runtime contracts](../api/platform-runtime.md)
- [Operations runtime contracts](../api/operations-runtime.md)
- [SQLAlchemy async dependency installation](https://docs.sqlalchemy.org/en/21/faq/installation.html)
