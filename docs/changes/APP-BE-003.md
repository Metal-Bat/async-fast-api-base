# APP-BE-003 — Safe migration verification

Backlog: APP-BE-003
Date: 2026-10-08
Area: migrations

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete thirteen-stage `mise run check` passed after D01 additive migration approval, D07 exact SDK exceptions and explicit approval of the ten exact non-secret baseline entries. The baseline update preserved all scanner rules and existing entries.

Observed commands, original failures, required service counts, tested source hash and private report are linked in [through-014-verification.md](../delivery/through-014-verification.md) and [through-014-gate.json](../delivery/through-014-gate.json). No required-profile test was skipped. This closes the backend task; later producers, frontend/browser acceptance and deployment retain their own task boundaries.

## Preparation history

The following original sections preserve earlier failures and pending-approval observations. Their PARTIAL/BLOCKED statements describe preparation and are superseded by the observed completion above.

## Summary

Preserved both applied revisions; added exact disposable ownership guards, empty round trip and a populated initial-to-current-head fixture checking request/form pins, checksums, media metadata and history triggers. Captured schema-drift failure rather than stamping or suppressing it.

## Why

Complete the authorized backlog through dependency wave three by extending existing owners and retaining observed failures as completion blockers.

## What Changed

scripts/run_flow_test.py; tests/scripts/test_run_flow_test.py; tests/integration/test_migrations.py; tests/delivery/test_migration_safety.py

## Architecture

Existing persistence, query, cache, template and task owners remain authoritative. No new applied schema, execution authority or production effect was introduced. New JSON models inherit BaseDTO; canonical names remain snake_case.

## Compatibility

CONFLICT: explicit migration policy approval remains pending. Alembic check reports five missing WORKFLOW_WORKSPACE column comments. Minimal additive repair is proposed and unapplied.

## Validation

The common evidence is recorded in docs/delivery/wave-three-verification.md. Native failure probes, focused regressions, all historical quality stages and disposable PostgreSQL tests were executed. Expected probes are assertions, not application readiness evidence. Required migration drift remains a failing assertion. No masked SDK warning is classified as absent.

Observed final checks: historical gate 720 default passes/130 opt-in skips, one doctest/four PostgreSQL workflow passes and hooks; strict gate five SDK failures; foundation profile 15 passes/one comment-drift failure, no skips. Logs and exact source hashes are linked in the common verification record.

Result: PARTIAL. This record documents prepared work and observed limits, not DONE/strict readiness.

## Backlog Impact

APP-BE-003 remains open with the specific blocker above. Dependent tasks are not silently promoted. Historical completed task records remain unchanged.

## References

Commit: baseline 995829eebd9483ac6b589c1648fc799c650ad464 plus current uncommitted changes.

Pull Request: None

Contracts/scenarios: D01; A01/A02

Additional notes: docs/delivery/migration-verification.md; docs/delivery/DECISIONS.md

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
