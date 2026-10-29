# APP-BE-019.UX01 — Agent authoring contracts and declared output projection

Backlog: APP-BE-019.UX01
Date: 2026-10-19
Area: processes/application

## Summary

The producer now supplies use-authorized saved connection names, exact workflow-bound
input/choice context, authorized saved-report catalog/preview and governed published
Agent evaluation submission. The existing process resolver also applies a STEP_OUTPUT
binding's source_path to its selected output port; whole-port bindings keep their behavior.
The dated 2026-10-27 continuation below documents the producer routes and their limits.
Earlier runtime-only checkpoint evidence is retained explicitly as history.

## Why

Validation projected nested paths but execution supplied the entire object. The
frontend handoff identified the mismatch; four of five regression cases reproduced
it before the repair.

## What Changed

- ProcessService._step_output reuses the existing JSON Pointer resolver.
- Five regressions cover whole objects, indexed decimal strings, false, null,
  escaped keys and absent-field failure, with unchanged snapshots.

## Architecture

No architecture change.

## Compatibility

The 2026-10-19 runtime-only delta left fixed DTOs, routes, JSON names, storage and migrations unchanged. The subsequent Agent continuation below adds five routes and required connection_name metadata; its matching frozen consumer intake is required.
No applied revision or published payload is rewritten. Deployment must use the
matching frontend mapper and repaired runtime; existing source_path now follows its
declared validation meaning. Required human approval and effect payloads are unchanged.

## Validation

Focused regression: five passed. Ruff lint passed; initial formatting and type
checks found test-only issues, subsequently repaired. Full gate and actual paired
publication/execution remain pending. The frontend continuation retains native
results and exact source identities in artifacts/user-timezone and its completion
receipt; an absent or partial receipt is incomplete. D07 retains exactly its two
recorded SDK exceptions; no strict exception-free readiness is claimed.

Result: PARTIAL until all required evidence is present.

## Backlog Impact

APP-BE-019.UX01 already identifies the frontend Agent authoring handoff. This
record documents only the related nested-output runtime delta; it does not rename,
replace or close the four existing Agent contract requirements. The task remains
open after a passing runtime gate until that original scope is reconciled.

Enabled: APP-FE-023 nested prior-output selection, pending paired acceptance.

Blocked: Broader mapper and Agent producer contracts, team selection and reserved
operation notification targets remain separate owning gaps. All other unfinished
backend tasks were reviewed; this resolver repair does not satisfy their acceptance.

Superseded: None.

Conflicts: None.

## References

Commit: None.

Pull Request: None.

Additional notes: frontend docs/changes/APP-FE-023-DATA-MAPPING.md and the current
APP-FE-023-PEER-HANDOFF.md continuation.

## 2026-10-27 Agent producer continuation

The four retained producer gaps now have implementations through existing owners.
Model metadata projects a use-authorized saved `connection_name`; secret handles
and provider credentials are never projected. Exact workflow context checks the
readable immutable version, AI step and pinned Agent before returning declared
schema and a bounded author/constant sample preview. Decision preview uses the
same data-policy preparation as runtime, including redaction/classification.

Five actor-private POST operations under `/api/v1/ai-agents/{ref_id}` provide
`decision-preview`, `workflow-context`, `retrieval-sources/search`,
`retrieval-preview` and `evaluations`. All require owned current Agent refs and
workflows.manage; evaluations additionally require requests.start. Actual responses
and enriched Swagger declare private/no-store. Fixed DTOs inherit BaseDTO and use
snake_case, strict request shapes, bounded samples and stable error envelopes.

Retrieval catalogs filter before paging using owned, live, unexpired reports,
registered version-exact opted-in sources, current permissions and pinned policy.
Preview describes the bounded existing `lookup_saved_report/1` contract; it returns
no rows and still requires the runtime human tool approval. It does not execute tools.

The evaluation contract requires a PUBLISHED Agent and an eligible owned saved
request whose immutable workflow pins it. It delegates ordinary RequestService.submit
with the unchanged submit_key, authenticated client and existing budget/approval path.
The response is actual governed submission/process identity, not a provider verdict.
Draft Agents get local validation/preview. This technical boundary avoids creating an
unrestricted provider-test executor or inferring approval for paid live calls.

Focused evidence: 19 seed/Agent unit and actual-router authorization tests pass;
four disposable database/process scenarios pass, including use-only connection
grants/revocation, foreign/stale refs, retrieval ownership/paging, exact workflow
context, evaluation replay and ordinary execution with the existing synthetic model.
The redaction regression first reproduced an incorrect preview and now passes.
These are real application/DB paths with a test model, not live provider acceptance.
The frontend consumes the saved connection name through its existing actor-fenced
adapter; focused Angular acceptance passes. New authoring operations beyond metadata
still need purposeful UI consumers under APP-FE-025/030. A generated transport alone
does not complete those frontend features.

Current producer export and unchanged-source full gates are pending final freeze.
Failed/partial attempts remain in the seed-processes evidence; D07's exact two
accepted exceptions remain VERIFIED_WITH_EXCEPTION. This continuation supersedes
the earlier claim that all four producer implementations are absent, but does not
close the task or claim full Agent UI/demo readiness before final evidence.


## Current validation and bounded completion candidate — 2026-10-27

The sixteen-stage `mise run check` completed with native exit 0 and
VERIFIED_WITH_EXCEPTION under the unchanged D07 policy: 1,039 default tests,
234 documented opt-in exclusions, one doctest and 146 mandatory service scenarios;
zero required skips or emitted diagnostics. Only delivery documentation changed
while that preliminary gate ran. The final documentation-qualified full run and
exact source comparison govern completion in the frontend checkout's
`artifacts/seed-processes-2026-10-27/completion.json`. Missing or failed final evidence
keeps this candidate incomplete. Actual paired paths/schema/browser acceptance also
passes with no service diagnostics; synthetic model tests do not establish paid/live
provider or user acceptance.

This bounded producer/runtime scope enables APP-FE-023/025/030. Their purposeful
new UI consumers remain open; publication, approval, provider configuration and paid
execution are still governed by existing owners. APP-BE-019's separate composition
and redacted-sample contracts remain open. No parent, deployment or demo gate closes.
The earlier open/partial checkpoint paragraphs are historical, not a second task owner.
