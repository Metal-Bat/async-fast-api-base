# APP-BE-013 — Notification event map and compatibility design

Backlog: APP-BE-013
Date: 2026-10-08
Area: notification design

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete thirteen-stage `mise run check` passed after D01 additive migration approval, D07 exact SDK exceptions and explicit approval of the ten exact non-secret baseline entries. The baseline update preserved all scanner rules and existing entries.

Observed commands, original failures, required service counts, tested source hash and private report are linked in [through-014-verification.md](../delivery/through-014-verification.md) and [through-014-gate.json](../delivery/through-014-gate.json). No required-profile test was skipped. This closes the backend task; later producers, frontend/browser acceptance and deployment retain their own task boundaries.

## Preparation history

The following original sections preserve earlier failures and pending-approval observations. Their PARTIAL/BLOCKED statements describe preparation and are superseded by the observed completion above.

## Summary

Specified MAP-01–MAP-14 with current command/event ownership, explicit missing producers, bilingual bounded templates, recipients, channels, dedupe, cancellation, retention and non-case targets. Added a fixture per row and an additive inbox/outbox compatibility design. Existing case-only DTO/registry remains unchanged.

## Why

Complete the authorized backlog through dependency wave three by extending existing owners and retaining observed failures as completion blockers.

## What Changed

docs/delivery/notification-map.json; docs/delivery/notification-design.md; tests/fixtures/delivery/notification-events.json; tests/delivery/test_notification_map.py

## Architecture

Existing persistence, query, cache, template and task owners remain authoritative. No new applied schema, execution authority or production effect was introduced. New JSON models inherit BaseDTO; canonical names remain snake_case.

## Compatibility

Design checks pass locally. Delivery/templates are DESIGNED_ONLY; actual workers/SMTP/inbox belong to APP-BE-014. Task stays open while the mandated strict final gate is red.

## Validation

The common evidence is recorded in docs/delivery/wave-three-verification.md. Native failure probes, focused regressions, all historical quality stages and disposable PostgreSQL tests were executed. Expected probes are assertions, not application readiness evidence. Required migration drift remains a failing assertion. No masked SDK warning is classified as absent.

Observed final checks: historical gate 720 default passes/130 opt-in skips, one doctest/four PostgreSQL workflow passes and hooks; strict gate five SDK failures; foundation profile 15 passes/one comment-drift failure, no skips. Logs and exact source hashes are linked in the common verification record.

Result: PARTIAL. This record documents prepared work and observed limits, not DONE/strict readiness.

## Backlog Impact

APP-BE-013 remains open with the specific blocker above. Dependent tasks are not silently promoted. Historical completed task records remain unchanged.

## References

Commit: baseline 995829eebd9483ac6b589c1648fc799c650ad464 plus current uncommitted changes.

Pull Request: None

Contracts/scenarios: C07; A07; APP-BE-014/APP-FE-012

Additional notes: docs/delivery/notification-design.md

## Through-014 reconciliation

The map now identifies actual APP-BE-014 report/AI command hooks and implemented existing
process/account delivery, plus the five explicitly blocked later producers. Channel
verification uses the existing HTTPS email gateway provider with real local TLS receipts;
no downstream SMTP claim is made. Templates are code-owned and synchronized to the manifest.
See unified-notifications-handoff.md and through-014-verification.md for current evidence;
the historical observations above are preserved. Formal closure remains blocked by the
separate ten-entry baseline approval and final gate.
