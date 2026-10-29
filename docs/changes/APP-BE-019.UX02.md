# APP-BE-019.UX02 — Durable declarations and legacy Transform repair

Backlog: APP-BE-019.UX02
Date: 2026-10-25
Area: workflow binding persistence, workflows/application, step_types/application

## Summary

REQUEST/CONTEXT source schemas survive executable save, promotion, publication and
reload. Legacy Transform v1 validates and executes through the existing bounded
engine while retaining its registered generic port/configuration metadata.

## Why

Executable reconstruction discarded accepted declarations, so promotion/publication
rejected declared request expressions. Two validators required different schemas
for the same v1 binding, and the runtime registry rejected v1 execution entirely.

## What Changed

- Forward revision `0004_binding_source_schema` adds nullable JSONB declarations
  only for REQUEST/CONTEXT bindings. Existing rows remain SQL null; there is no
  workspace inference, backfill, reset or rewrite of applied revisions.
- Explicit persistence/reconstruction retains the existing public declaration.
  It is an authoring type contract, never request data or authorization.
- Registry-verified legacy identities receive effective conversion schemas during
  validation. Canonical graph metadata/checksum inputs retain generic v1 ports.
- Registered v1 conversions use TransformSpec/TransformEngine. Invalid conversions
  and incompatible sources still fail. V2 and published pins retain their contracts.
- Clarify GraphBinding.source_schema documentation and refresh the authoritative
  producer. Three-language paths/operations/security are unchanged; the public
  schema diff changes only that description. Handler fingerprints remain unchanged.
- Extend the required existing delivery-completion profile with actual persistence,
  HTTP authorization/conflict, promotion/publication and zero-valued runtime tests.
  Migration tests verify legacy checksum preservation and data-loss rollback refusal.

## Architecture

### Before

Mutable authoring documents and executable rows represented different source
contracts; generic metadata conflicted with configured conversion types.

### After

Executable bindings own their declarations. Trusted effective types refine
validation while canonical snapshots and existing engine ownership remain intact.

### Reason

Repair the two concrete APP-FE-024 findings without a parallel engine, replacing
immutable type versions or using workspace metadata as runtime authority.

## Compatibility

Apply the normal forward migration before deploying the changed application.
The two baseline revisions and Arabic revision remain unchanged. Rehearse on an
owned/restored copy; no shared database, stamp or reset is performed. Old bindings
retain null and their checksum meaning. Draft authors can deliberately promote
declarations. Partial downgrade refuses to discard declarations; full teardown
remains for guarded disposable databases. Wire names, operation IDs, envelopes,
permissions and current-reference semantics remain unchanged.

## Validation

Observed focused results: 27 existing/registry checks, six new legacy checks, five
actual disposable PostgreSQL/HTTP scenarios and the dedicated migration
preservation/refusal scenario pass. Touched Ruff and full types pass cleanly.

Final results are not preclaimed. The actual paired workflow browser journey,
complete backend/frontend `mise run check`, native exits, source comparisons and
retained failures are governed by the frontend receipt
`artifacts/remaining-2026-10-25/completion.json`. Missing/partial/failed evidence
is incomplete. Exact D07 exceptions retain VERIFIED_WITH_EXCEPTION, never strict
exception-free/demo readiness. Default opt-in exclusions are separate from the
required non-skipping service scenarios.

Retained failures include the initial expected red assertions, pool cleanup after
red failures, corrected new-test type diagnostics and export invocations missing
the documented import roots/synthetic settings. No environment file or diagnostic
threshold changes. Existing user modifications are preserved.

## Backlog Impact

APP-BE-019.UX02 records this bounded repair under existing APP-BE-019/APP-FE-024.
Unbound request completion, object assembly, samples, Agent/Calendar/notification
gaps and broader hosted/deployed/manual/user acceptance remain separately owned.


The first complete gate retains 1,030 unit passes and two failures: the new column
comment needed the established uppercase metadata convention, and the generated
response reference needed regeneration after the documented schema change. Both
are corrected through the owning source/generator; no assertion or threshold is
relaxed. The new forward revision is still unreleased and has only been applied
to subsequently removed disposable databases. All three applied historical
revision files remain unchanged. Current service/browser evidence must qualify
the corrected source; the initial 44-scenario run retains its original hash.


The second complete gate passes 1,032 default tests, the doctest and 54 required
flow/foundation/wave-four cases. Its transfer profile retains 58 passes and one
failed Persian claim race (200/503 instead of 200/409). Safe PostgreSQL metadata
identifies a notification fanout USER/PROCESS_INSTANCE deadlock. The separately
owned APP-BE-028.UX01 repair reproduces it with a controlled real-database overlap;
its initial regression fails before the scoped lock fix and three focused cases
then pass. The full gate and paired receipt must qualify that corrected source.


## Scoped backend completion — 2026-10-25

The bounded backend repair is DONE under VERIFIED_WITH_EXCEPTION (the exact two
D07 SDK exceptions). The complete backend mise run check passes all sixteen
stages: 1,032 default tests, one doctest and 142 mandatory service cases; zero
mandatory skips and emitted diagnostics. The 233 documented default opt-in
exclusions remain listed separately. Start/end maintained-source identity is
unchanged and matches the native report's file inventory.

The corrected source pair separately passes all 44 actual browser/service
scenarios, exact live API agreement and zero browser/service diagnostics. Producer
contracts and immutable pins retain their recorded boundaries. The controlled
notification overlap additionally verifies both persisted recipient notices.

Evidence: frontend artifacts/remaining-2026-10-25/backend-check-third/,
backend-third-source-comparison.json and paired-workflows-lock-final/. Failed
first/second gates and controlled deadlock red are retained. Final documentation
closure receives a fresh complete gate before final acceptance; its actual result
and the still-separate final frontend gate belong to completion.json. Missing,
partial or failing final evidence is incomplete. This is neither strict
exception-free/demo readiness nor hosted/deployed/manual/user acceptance.

The unfinished-only backend backlog removes this completed child, retaining its
stable ID and history here. Parent APP-BE-019/APP-FE-024 and other unresolved
feature/assistant/consistency owners retain their current status.
