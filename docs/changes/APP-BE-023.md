# APP-BE-023 — Connect a real isolated HTTPS order sandbox through the worker

Backlog: APP-BE-023
Date: 2026-10-10
Area: integrations / processes / owned test services

## Summary

current browser-triggered ordinary-human approval -> actual worker/HTTPS order -> persisted recipient receipt -> readonly acknowledgment passed in en/fa, including post-commit lost approval reply recovery. Local sandbox remains separate from a named vendor.

## Why

connection.status was a diagnostic rather than an external business effect, and queued work could not be treated as completion.

## What Changed

The sandbox persists idempotent create/cancel receipts in owned SQLite and survives restart. The adapter sends one bounded HTTPS request, validates identity/hash/schema/size, prevents redirects and redacts network errors. The worker commits its stable operation fence before HTTP, closes database sessions during transport and records validated result through the existing idempotent callback. Tests provision private runtime credentials and CA, never production endpoints.

Principal locations: `scripts/order_sandbox.py; scripts/transfer_services.py; src/apps/integrations/application/orders.py; src/apps/processes/application/orders.py; tests/integration/test_required_human_approval.py`. Shared Swagger descriptions, DTO reference pages and
the sole current producer manifest are regenerated; en/fa preserves machine identifiers.
See the [exact public/operational handoff](../delivery/PROTECTED-OPERATIONS-HANDOFF.md).

## Architecture

### Before

Existing outbox/worker and diagnostic provider already operated.

### After

An explicitly labeled separate sandbox and typed adapter reuse the same dispatch owner and durable attempts.

### Reason

Preserve existing transaction, authorization, history and worker ownership while making
approval and provider evidence explicit. No parallel engine, scheduler, action executor,
notification store or permission system.

## Compatibility

Existing envelopes, BaseDTO snake_case, public error values, handler versions, published
pins and task names remain. Only registered sandbox operation versions and five additive
routes are introduced. Creation is normal-only and cancellation compensation-only.
DB-002 remains exactly two revisions and 103 tables; no migrations, dependencies,
lockfile, environment file, mise configuration or shared data were changed by this work.
The administrator-owned endpoint/secret and optional CA use existing settings. The
separate sandbox is explicitly disposable/local, not a production or vendor service.
No frontend code was modified; browser and named-provider evidence remain separate.

## Validation

Commands executed:

- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run ty check` — passed after fixing new test truthiness warnings without suppression.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run pytest -q tests/apps/step_types/test_operation_contract.py tests/apps/workflows/test_protected_effects.py tests/apps/processes/test_protected_dispatch.py tests/apps/processes/test_order_compensation.py tests/apps/integrations/test_execution_pins.py tests/scripts/test_order_sandbox.py tests/delivery/test_supervised_ai_profile.py` — 49 passed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache FLOW_TEST_PROFILE=protected-operations uv run --env-file .envs/.backend python scripts/run_flow_test.py` — expanded owned profile 21 passed, including before-HTTP uncertainty, false-compensation denial and rejecting invented receipts after real approval.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run security` — passed, no Bandit issues and no secrets findings; policy/baseline unchanged.

- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check` — exit 0; all 15 stages passed, 943 default tests, one doctest and 109 required service-profile passes (4/18/29/37/9/12). Required service skips: zero. The 198 default opt-in exclusions are listed individually in the verification artifact. Pre-commit passed; its XML hook had no applicable files.

Result: PARTIAL. Backend acceptance passed as VERIFIED_WITH_EXCEPTION; the explicit browser-triggered/inspectable-receipt criterion remains BLOCKED.

Frozen-gate start/end source SHA-256:
`30cfbd89fa4427cc05cf6ec40bbc7b1b04e0cb07bcd11d7692eafd74eed74472`.
The full source identity matched before any closure edits. See
[structured verification](../delivery/protected-operations-verification.json) for exact
tools, approvals, test names, owned service/database identities, retained failures and
peer limitations. Subsequent journal/backlog/handoff closure edits are documentation only;
runtime, tests and producer artifacts remain identical to the gate.

Documentation-only closure verification:
`rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run pytest -q tests/docs`
passed all 18 tests; pre-commit against the eleven closure files and the unchanged
security scan passed. Link checks and normalized backlog-mirror comparison passed.
Source comparison permits only these closure documents after the frozen gate.

The first full gate (`app-be-check-jc5uxl5a`) stopped at default tests: 941 passed,
197 documented opt-in integration exclusions, one failed test due to 18 unclosed
SQLite connections from the new sandbox. Its first seven stages passed. The sandbox
now explicitly closes every connection; a new regression reproduced the leak before
the fix. Later mandatory stages were NOT_RUN in that failed gate. No ResourceWarning
filter was added, and the failed report remains separate from final evidence.
Exact two D07 SDK exceptions stay VERIFIED_WITH_EXCEPTION. No new suppression or required
skip was added. No paid/vendor call or fixture result is promoted to browser acceptance.

Implementation-stage failures retained: initial fixture/import issues; missing lookup;
TLS CA diagnostic verification; cancellation acknowledgment fault and recovery audit-key
collision; missing receipt erroneously retaining DISPATCHING; type/Bandit assertions and
fixed test values detected by security checks. They were addressed with code/tests or
runtime-generated fixture credentials, never expanded scanner rules or baseline entries.
A second gate (`app-be-check-ebrje8cg`) passed 943 default tests (197 documented
opt-in exclusions), one doctest and the 4/18/29 workflow/foundation/wave-four profiles,
then failed delivery-transfer-test with 33 passed and one notification reconnect failure.
Required later stages were NOT_RUN. The reconnect assertion now reports the actual
HTTP status before parsing SSE; no transport/auth limits or test retry were relaxed.
Review separately reproduced generic resume accepting an invented provider receipt after
real human approval (19 passed, two red-profile failures including a pending lost-reply
dispatch). The protected create wait now completes only through the verified worker
or receipt lookup; existing unprotected resume is preserved.
The following run passed 20 cases but again left that lost-reply dispatch PREPARED.
Its test now runs successive real outbox batches, matching scheduled dispatch, rather
than assuming one batch publishes all prior isolation work. The unchanged receipt
assertion and timeout then passed in the 21-case owned-service profile.
The focused notification-push profile subsequently passed all three real API/worker
cases, including reconnect. No cause is asserted for the earlier reconnect failure;
the full combined profile remains required. Existing PostgreSQL AI budget-exhaustion
and concurrent-reservation regressions are also included in that mandatory profile.

The restricted security scan also failed on multiprocessing socket permissions; the
unchanged command was rerun with authorized local execution.

## Backlog Impact

Enabled:

- APP-BE-024, APP-BE-028 backend prerequisites; APP-FE-025/026/030/037 browser receipt journey

Blocked:

- APP-BE-023 browser-triggered/inspectable-receipt acceptance; actual paired frontend journey remains unverified.
- D02 live named provider/model/data/cost acceptance. Deterministic AI and owned sandbox are explicitly labeled.

Superseded:

- APP-BE-021 historical pending-policy note: exact owner acceptance on 2026-10-10 supersedes it, preserving history.

Conflicts:

- None. D04 accepted ordinary-publisher authority and DB-002/D07 decisions are preserved.

Unfinished APP and assistant tasks were reviewed. Backend prerequisites can be used where
implemented, but none of those separate tasks is completed by this change.

## References

Commit: None

Pull Request: None

Additional notes: backlog,
[accepted policy](../delivery/protected-effect-policy.md),
[decisions](../delivery/approved-decisions.json),
[handoff and limitations](../delivery/PROTECTED-OPERATIONS-HANDOFF.md).


## Historical summary before current closeout

The backend now sends an actual approved order via the existing outbox and Celery worker to a separate authenticated TLS sandbox, records a durable typed receipt and exposes authorized inspection. The explicit browser-triggered workflow criterion remains unverified.


## Current closeout — 2026-10-11

current browser-triggered ordinary-human approval -> actual worker/HTTPS order -> persisted recipient receipt -> readonly acknowledgment passed in en/fa, including post-commit lost approval reply recovery. Local sandbox remains separate from a named vendor.

Validation result: PASS within this task’s scoped local/integrated acceptance; VERIFIED_WITH_EXCEPTION under exact D07.

Commands executed: `mise run check` (backend, all sixteen stages), `mise run check` (final frozen frontend), `mise exec -- npm run ci:gates` (actual matching frontend). Backend start/end source identity matches; 983 default tests, one doctest and 132 mandatory service cases pass with zero mandatory skips. The 221 default opt-in exclusions remain listed. Frontend: 545 unit tests; all twelve commands pass with zero tool diagnostics and unchanged source. The repaired peer additionally passes all four actual en/fa approval/receipt and lost-reply cases.

The strict failed full-gate attempt, SQLite connection regression/fix and passing strict restore rerun remain in [final verification](../delivery/main-tasks-final-verification.json). The runtime image context still matches tested source. Evidence/backlog documents were updated after the stable gate; application, contracts, tests, migrations, dependencies and runtime configuration were unchanged afterward.

Backlog impact: this scope is DONE; enables subsequent dependent tasks. APP-BE-031/032 remain blocked. Commit/PR: None. Existing decisions and historical failed/partial results are preserved.
