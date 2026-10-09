# APP-BE-026 — Exact workflow baseline restoration

Backlog: APP-BE-026
Date: 2026-10-09
Area: workflows / authoring / PostgreSQL

## Summary

Added a read-only expiring restoration preview, atomic reviewed apply with durable
command replay, and a separate layout reset. Published/retired content and active
cases keep their pins; a successor remains an editable unpublished draft.

## Why

Existing template creation recorded immutable source provenance, but authors lacked
an explicit reviewed command for returning a workflow to its associated default.
Definition restoration must respect independent workspace revisions and avoid
resetting execution data, principals, forms or request-type routing.

## What Changed

- `apps/workflows/application/defaults.py` resolves immutable provenance and
  symbolic dependency bindings through existing publication validation, then
  freezes actor, target, workspace, source/checksum, bindings and graph hash in
  a ten-minute signed plan. Invalid dependencies or graphs exceeding the existing
  workspace structural/256-KiB bound return blockers without a token.
- The version router exposes POST `default-preview`, `default-apply`, and
  `layout-reset`. DTOs inherit BaseDTO with snake_case and bounded command fields.
  New operation summaries/descriptions are localized in en/fa and private no-store.
- Apply locks current actor/root before receipt lookup and revalidates live
  permissions. Unique actor/target/command receipts make concurrent retries return
  one draft; changed intent conflicts. Source retirement resolves recorded
  provenance only after immutable content validation. Explicit source selection
  remains subject to current references.
- Existing graph/workspace/history owners perform transactional updates. A failed
  dependency or workspace write exposes no partial successor or replay receipt.
  Published forms/subprocesses remain references, never overwritten dependencies.
- `k026_workflow_restore` adds the command receipt table after calendar events.
  Original applied revisions remain byte-identical. No dependency was added.
- `delivery-completion-test` is an additional required strict gate stage covering
  restoration plus existing workspace and library regressions.

## Architecture

### Before

Template provenance, version publication and workspace promotion already existed.

### After

A workflows application service coordinates those existing owners and a narrow
receipt entity. It does not introduce another template store or effect dispatcher.

### Reason

Preserve lifecycle, validation, authorization and transaction behavior while making
restoration intent concrete, bounded and replayable.

## Compatibility

All existing APIs remain. Three authenticated member actions and nested DTOs are
additive. Existing public errors and JSON envelopes are preserved. New receipts
retain only identities and token hashes with the workflow; there is no generic purge
endpoint. Restore never auto-publishes or changes request-type routing or running
case/form/subprocess pins. Existing published source retirement is permitted only
as immutable baseline content, with current explicit references or checked provenance.

## Validation

Commands executed:

- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run pytest -q tests/apps/designer/test_workflow_defaults_contract.py` — 3 passed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache FLOW_TEST_PROFILE=delivery-completion uv run --env-file .envs/.backend python scripts/run_flow_test.py` — final focused profile: 12 passed, no skips, owned database removed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run ty check` — passed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run ruff check .` — passed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run pybabel compile -d src/locales` — passed.
- `rtk proxy graphify update .` — AST refresh passed after local multiprocessing authorization.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check` — final fifteen-stage gate passed: 808 default passes / 173 documented opt-in exclusions, one doctest, 76 required service-profile passes with no required skips; all quality/hooks passed. Earlier reference drift, PO end-of-file hook changes and the large-template failing-before-fix probe are preserved in the completion ledger.

Result: PASS — VERIFIED_WITH_EXCEPTION under exactly the two owner-approved SDK
deprecations. This is backend authoring verification; it is not warning-free
readiness, complete demo/browser acceptance or delivery of the remaining APP tasks.
Observed evidence and remaining delivery scope: `docs/delivery/completion-verification.md`.

## Backlog Impact

Enabled:

- APP-BE-028/029: this prerequisite is satisfied; their other dependencies remain open.

Blocked:

- APP-BE-021/022 exact pilot protected-operation mapping pending owner decision.

Superseded:

- None.

Conflicts:

- None. D01 additive migrations and D07 exact SDK exceptions remain accepted.

All unfinished APP tasks and dependency relationships were reviewed; dependent
capabilities and browser acceptance are not inferred from this authoring API.

## References

Commit: None (uncommitted changes).

Pull Request: None.

Additional notes: `docs/delivery/workflow-defaults.md`; generated response reference
`docs/reference/responses/workflow-versions.md`; localized schemas `docs/delivery/wave-four/`.

Final sanitized evidence: `docs/delivery/completion-gate.json`. The original migration
bytes and final tested code/configuration/fixture digest were checked before task closure.
