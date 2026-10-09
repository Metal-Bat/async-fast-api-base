# APP-BE-004 — Idempotent system catalogs

Backlog: APP-BE-004
Date: 2026-10-08
Area: users/step catalog

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete thirteen-stage `mise run check` passed after D01 additive migration approval, D07 exact SDK exceptions and explicit approval of the ten exact non-secret baseline entries. The baseline update preserved all scanner rules and existing entries.

Observed commands, original failures, required service counts, tested source hash and private report are linked in [through-014-verification.md](../delivery/through-014-verification.md) and [through-014-gate.json](../delivery/through-014-gate.json). No required-profile test was skipped. This closes the backend task; later producers, frontend/browser acceptance and deployment retain their own task boundaries.

## Preparation history

The following original sections preserve earlier failures and pending-approval observations. Their PARTIAL/BLOCKED statements describe preparation and are superseded by the observed completion above.

## Summary

Added a bounded PostgreSQL permission reconciler with transaction serialization, safe BaseDTO summaries and six explicitly optional least-privilege roles. Existing grants/revocations and published step versions remain operator-owned/immutable. Added a supported check/reconcile command and versioned C01 inventory.

## Why

Complete the authorized backlog through dependency wave three by extending existing owners and retaining observed failures as completion blockers.

## What Changed

src/apps/users/application/permission_catalog.py; src/apps/users/domain/catalog.py; scripts/reconcile_system_catalog.py; tests/apps/users/test_permission_catalog.py; tests/integration/test_application_seed.py

## Architecture

Existing persistence, query, cache, template and task owners remain authoritative. No new applied schema, execution authority or production effect was introduced. New JSON models inherit BaseDTO; canonical names remain snake_case.

## Compatibility

Implementation is prepared without new schema. Task completion remains blocked on APP-BE-003 and the strict gate. No role was assigned or reconciler run against shared project data.

## Validation

The common evidence is recorded in docs/delivery/wave-three-verification.md. Native failure probes, focused regressions, all historical quality stages and disposable PostgreSQL tests were executed. Expected probes are assertions, not application readiness evidence. Required migration drift remains a failing assertion. No masked SDK warning is classified as absent.

Observed final checks: historical gate 720 default passes/130 opt-in skips, one doctest/four PostgreSQL workflow passes and hooks; strict gate five SDK failures; foundation profile 15 passes/one comment-drift failure, no skips. Logs and exact source hashes are linked in the common verification record.

Result: PARTIAL. This record documents prepared work and observed limits, not DONE/strict readiness.

## Backlog Impact

APP-BE-004 remains open with the specific blocker above. Dependent tasks are not silently promoted. Historical completed task records remain unchanged.

## References

Commit: baseline 995829eebd9483ac6b589c1648fc799c650ad464 plus current uncommitted changes.

Pull Request: None

Contracts/scenarios: C01; A01/A02

Additional notes: docs/delivery/system-catalogs.md; docs/delivery/seed-manifest.json
