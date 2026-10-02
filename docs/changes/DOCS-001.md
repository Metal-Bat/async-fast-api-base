# DOCS-001 — User and frontend documentation handoff

Backlog: DOCS-001
Date: 2026-10-02
Area: documentation

## Summary

Added an English task-based handbook and a framework-neutral frontend guide from login through
request completion. Connected existing references through audience navigation and standard
Markdown links. Examples now distinguish reviewed business values from uncovered schemas.

## Why

The repository had substantial technical reference material but no approachable user handbook or
single frontend implementation path. The response generator emitted fictitious lifecycle values,
navigation relied on Obsidian syntax, and historical BPMS guidance looked like current migration
instructions. The user requested all four gaps be filled, with English-only prose and neutral
TypeScript examples.

## What Changed

- `docs/guides/user-handbook.md` explains accounts, drafts, submission, claims, decisions,
  corrections, progress, troubleshooting and administrator prerequisites in ordinary language.
- `frontend-journey.md` and `frontend-contract.md` describe actual routes, access conditions,
  envelopes, current refs, idempotency, refresh rotation, failures and frontend states. Explicitly
  document administrator-only request-type browsing and absent process-ref discovery in the
  business-request DTO rather than implying unsupported endpoints exist.
- `docs/examples/frontend-client.ts` provides a checked browser-fetch client with in-memory
  tokens, serialized refresh, encoded refs and explicit action keys. It is an educational client,
  not a complete UI or production session-storage solution.
- `docs/examples/frontend-journey.json` contains 11 synthetic request/response cases and the
  small form contract. Domain validation produces the missing-field error example; route/schema
  checks verify every payload. The pre-existing five response scenarios also have DTO tests.
- The response-reference generator emits curated examples only, including their nested schemas.
  Schemas without an example say so. Regenerated all 37 reference pages; field tables remain.
- `docs/Home.md` routes users, frontend/backend developers, QA and operators to appropriate pages.
  Converted internal wiki links to ordinary relative Markdown. Marked BPMS-001 as historical,
  linked current migration guidance and distinguished proposed form-v2/roadmap material.
- Added maintenance instructions and six pytest checks for example contracts, form semantics,
  scenario DTOs, generated-reference drift, portable local links and fabricated-example prevention.

## Architecture

No application architecture change. Documentation generation has a pure rendering entry point
for drift checks. Runtime routes, DTOs, authorization, dependencies and database schema are unchanged.

## Compatibility

Documentation is English only. Examples target the current API; synthetic tokens/refs must be
replaced. Required nullable fields remain required. No change to English/Farsi runtime behavior.
Generated references intentionally omit unreviewed fabricated examples. Existing schema/field
description gaps remain visible in the coverage inventory; this work does not claim all 302
operations have full narrative documentation.

## Validation

Commands executed:

- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync pytest -q tests/docs`
  — six checks passed. The fabricated-status test failed before the generator change.
- `rtk proxy env PYTHONPATH=src:. uv --cache-dir /tmp/uv-cache run --no-sync python docs/tools/generate_response_dtos.py`
  — generated 37 pages; drift check passed.
- `rtk proxy tsc --strict --noEmit --target ES2022 --module ES2022 --lib ES2022,DOM docs/examples/frontend-client.ts`
  — passed.
- `rtk proxy timeout 120s uv --cache-dir /tmp/uv-cache run --no-sync pytest -q`
  — outside sandbox: 628 passed, 113 opt-in integration tests skipped, 7 dependency warnings.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync python -` — executed
  `scripts/run_flow_test.py` through runpy with synthetic settings against temporary local
  PostgreSQL. The runner migrated a fresh database, passed the purchase workflow integration
  test, and dropped its database. No project database was changed.
- `rtk proxy uv --cache-dir /tmp/uv-cache lock --check --offline` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync ruff check .` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync ruff format --check .` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync ruff check src/utils --select D101,D102,D103,D104` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync ty check` — passed after annotating `SelectOption[str]`.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync bandit -r src -q` — passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync python scripts/check_secrets.py`
  — passed outside sandbox; multiprocessing was blocked inside it.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync pytest -q tests/conftest.py src/utils --doctest-modules` — 1 passed.
- `rtk proxy uv --cache-dir /tmp/uv-cache run --no-sync pre-commit run --all-files` — applicable hooks passed.

Result: PARTIAL for live frontend/reader acceptance. Automated checks and the real service-level
purchase regression passed. No browser UI exists here to verify, no full HTTP login-to-completion
session was executed, and no external reader study was performed. Examples state these limits.
The local-link check validates file targets, not external URLs or every heading anchor.

## Backlog Impact

All tasks reviewed. DOCS-001 completes the four requested handoff gaps. DB-001's current lineage
replaces the historical migration instructions; OBS-001 is unaffected.

Enabled: None

Blocked: None

Superseded: Historical BPMS-001 migration instructions as current operational guidance.

Conflicts: None

## References

Commit: None

Pull Request: None

Additional notes: `docs/Home.md`, `tests/docs/test_frontend_docs.py` and
`docs/guides/documentation-maintenance.md` are the entry points for future updates.
