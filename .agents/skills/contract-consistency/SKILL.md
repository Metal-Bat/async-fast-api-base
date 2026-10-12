---
name: contract-consistency
description: Review and implement cross-layer entity, DTO, Swagger, generated-client and UI consistency work. Use for CONS tasks and APP changes affecting public contracts, canonical values or shared design patterns; supplements existing repository skills.
---

# Contract consistency

## Required preparation

Read root AGENTS.md, BACKLOG.md, current decision records and the task. Then read `docs/delivery/consistency-2026-10-09/SOFTWARE-DESIGN-CONTRACT.md`, and `REPAIR-REGISTER.md`. Use existing smart-backlog/change-journal and Swagger/CRUD/select skills where present. Use graphify first when its local graph exists; refresh after code changes. Never claim unavailable tools ran.

## Evidence before change

Inspect the actual entity, DTO, application logic, route/enrichment, generated contract, frontend adapter, screen and tests involved. Establish the exact source pair and actual lock versions. Classify reuse/extend/verify/new/conflict. Search existing APP and earlier assistant tasks for overlap. Existing behavior is not missing because a stale peer document says so. No new table or service exists merely because this skill mentions it.

## One meaning, different representations

Keep private entity storage, public DTOs and frontend view models distinct. Use explicit mappings with canonical types, units, null/default semantics, permissions, current refs and lifecycle. Do not expose entity fields for visual symmetry, rename deployed endpoints or make every table generic CRUD. Public fixed JSON models follow BaseDTO/snake_case; dynamic documents retain their own bounded dialects and machine values.

## Repair workflow

1. Identify the smallest authoritative existing owner and a concrete failing case.
2. Define behavior/compatibility, then add a failing focused regression.
3. Implement through existing application/adapter seams, preserving transactions and invariants.
4. Update effective Swagger/metadata/examples and the single producer handoff when contracts change.
5. Update purpose-built UI and state/locale tests; no mandatory raw JSON or copied refs for normal work.
6. Verify positive, invalid, unauthorized, stale, duplicate, uncertain and recovery cases as relevant.
7. Run complete final `mise run check` on unchanged source, required DB/worker/HTTP/browser checks, and source-identity comparison.
8. Write actual change/evidence records, update only the correct task authority and hand off the exact peer artifacts.

## Guardrails

No blanket suppression, skipped required scenario, weakened threshold, masked exit status, fake receipt or mock-to-live promotion. Current D07 exact SDK exceptions are labeled, not widened or called exception-free. DB-002's migration policy requires a safe actual upgrade path; never stamp/reset shared data. Preserve AI human-approval requirements and operation-specific idempotency; do not replay uncertain external actions. No unapproved framework/paid-library replacement or architectural rewrite.

## Completion

A successful new consistency check does not complete its original APP feature. Record designed/implemented/local/integrated/demo/deployed/user acceptance separately. Unknowns and genuine blockers must be named. Package lint and local probe evidence cannot stand in for repository execution.
