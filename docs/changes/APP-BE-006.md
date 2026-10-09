# APP-BE-006 — Live collection query policy

Backlog: APP-BE-006
Date: 2026-10-08
Area: query/cache

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete thirteen-stage `mise run check` passed after D01 additive migration approval, D07 exact SDK exceptions and explicit approval of the ten exact non-secret baseline entries. The baseline update preserved all scanner rules and existing entries.

Observed commands, original failures, required service counts, tested source hash and private report are linked in [through-014-verification.md](../delivery/through-014-verification.md) and [through-014-gate.json](../delivery/through-014-gate.json). No required-profile test was skipped. This closes the backend task; later producers, frontend/browser acceptance and deployment retain their own task boundaries.

## Preparation history

The following original sections preserve earlier failures and pending-approval observations. Their PARTIAL/BLOCKED statements describe preparation and are superseded by the observed completion above.

## Summary

Applied deleted_at IS NULL at normal repository/pagination seams to both items and counts; protected admin selectors retain their deliberate lifecycle override. Added live-parent checks to form/workflow authoring child searches and a new user cache page identity. Historical/audit/pinned direct resolution remains explicit.

## Why

Complete the authorized backlog through dependency wave three by extending existing owners and retaining observed failures as completion blockers.

## What Changed

src/utils/pagination.py; src/core/base_repository.py; src/apps/users/application/service.py; src/apps/work_groups/presentation/routes.py; src/apps/forms/presentation/routes.py; src/apps/workflows/presentation/routes.py; tests/utils/test_live_query_policy.py; tests/utils/test_live_child_queries.py; tests/core/test_base_repository.py; tests/integration/test_live_query_policy.py

## Architecture

Existing persistence, query, cache, template and task owners remain authoritative. No new applied schema, execution authority or production effect was introduced. New JSON models inherit BaseDTO; canonical names remain snake_case.

## Compatibility

Blocked on APP-BE-002. Six PostgreSQL cases include restored counts and user/group selector results. End-to-end Dragonfly/PostgreSQL deletion/restore cache acceptance passed against owned resources; direct ordinary-user restore denial is included in the seed profile. No unrestricted deleted-object flag or global ORM filter was added.

## Validation

The common evidence is recorded in docs/delivery/wave-three-verification.md. Native failure probes, focused regressions, all historical quality stages and disposable PostgreSQL tests were executed. Expected probes are assertions, not application readiness evidence. Required migration drift remains a failing assertion. No masked SDK warning is classified as absent.

Observed final checks: historical gate 720 default passes/130 opt-in skips, one doctest/four PostgreSQL workflow passes and hooks; strict gate five SDK failures; foundation profile 15 passes/one comment-drift failure, no skips. Logs and exact source hashes are linked in the common verification record.

Result: PARTIAL. This record documents prepared work and observed limits, not DONE/strict readiness.

## Backlog Impact

APP-BE-006 remains open with the specific blocker above. Dependent tasks are not silently promoted. Historical completed task records remain unchanged.

## References

Commit: baseline 995829eebd9483ac6b589c1648fc799c650ad464 plus current uncommitted changes.

Pull Request: None

Contracts/scenarios: A02/A05/A09; current search/select envelopes

Additional notes: docs/delivery/live-query-matrix.md
