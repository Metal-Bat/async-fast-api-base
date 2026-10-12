# Protected operations handoff — APP-BE-021–025

Status: backend acceptance VERIFIED_WITH_EXCEPTION. APP-BE-021/022/024/025 are DONE;
APP-BE-023 is implemented but BLOCKED on actual browser acceptance. Live vendor/model
acceptance has not been established.

The owner accepted `purchase-human-approval/1` and D04 on 2026-10-10. See the
[exact policy](protected-effect-policy.md) and [decision record](approved-decisions.json).
The ordinary published workflow identity, work-item/form owners, persisted attempts,
process events, compensation records and committed task outbox remain authoritative.
No new notification store, workflow engine, permission system or database table exists.

## Frozen backend contract

All routes below are additive and use the existing authenticated bearer session,
BaseDTO/snake_case wire format, ordinary JSON envelopes and stable public errors.
No endpoint accepts a caller-selected execution principal. Shared correlation/date and
language headers retain their existing Swagger documentation.

| Method/path | Authorization | Result and side effect |
| --- | --- | --- |
| GET `/api/v1/step-types/operations` | Active session, `workflows.manage` | `SuccessResponse.data`: bounded registered catalog; no effect or secrets. Static route precedes `/{ref_id}`. |
| POST `/api/v1/processes/{ref_id}/orders/search` | Active session, `requests.start`, request participant view | `PageResponse.result`: latest attempt per logical order; actual receipt when confirmed. Outsiders receive 404. |
| POST `/api/v1/processes/{ref_id}/ai-evidence/search` | Same participant authorization | Latest AI attempts, exact agent/model pin, allowed field names, typed recommendation and existing budget; no model call. |
| POST `/api/v1/processes/{ref_id}/orders/reconcile` | Active session, `processes.recover`, active superuser | Original-identity receipt GET; never another create. Current process/execution refs required for a fresh command. |
| POST `/api/v1/processes/{ref_id}/orders/reconcile-cancellation` | Same recovery authorization | Requeues an existing uncertain cancellation for worker receipt GET through the existing outbox; never resends cancellation. RUNNING is queued, not successful. |

Search body: `{"page":1,"size":20}`; page starts at 1 and size is bounded to 100.
Fresh reconciliation body:

```json
{
  "step_execution_ref_id": "<current opaque execution reference>",
  "command_key": "incident-lookup-1",
  "reason": "INC-001"
}
```

`command_key` is 1–128 characters. `reason` is an ASCII incident/ticket code of
1–64 characters (`A-Za-z0-9._:-` after an initial alphanumeric), never private text.
A replay with the same actor, process, original refs and intent returns current evidence;
changed intent conflicts. A failed/missing lookup requires a fresh lookup command and
current refs; it never grants permission to repeat an effect.

Actual Swagger/OpenAPI documents these routes, nested schemas, errors, pagination,
examples and English/Farsi descriptions. The
[current producer manifest](consistency-2026-10-09/contracts/manifest.json)
remains the sole current contract authority; historical wave-four artifacts are preserved.
Generated response reference pages are in `docs/reference/responses/`.

HTTP errors retain the existing JSON error envelope: 401 invalid/revoked/expired session;
403 missing permission or non-superuser recovery; 404 wrong/unauthorized process or
execution; 409 stale ref, changed command intent, ineligible state or changed execution
pin; 422 invalid input; order lookup additionally returns 503 for unavailable transport.
Connection grant denial follows the existing forbidden policy; no new error suppression
or permission alias is introduced.

## Approval and execution

The catalog has `connection.status` (diagnostic), `sandbox.order.create/1` (normal
execution) and `sandbox.order.cancel/1` (compensation only). Cancel input is derived from the persisted original order receipt, never an authored
replacement receipt. Typed create input has
`item_code` (ASCII identifier, 1–64 characters), integer `quantity` (1–1000), and optional
`note` (at most 512 characters). Extra fields are forbidden. These are explicitly
sandbox values, with no currency, production inventory or purchase authorization.

Every selectable route to create must cross the declared HUMAN_TASK complete/approve
edge. Normal, review, reject, return, conditional/default and parallel bypasses fail
publication. This initial profile rejects subprocess/interface composition and
compensation-only creation rather than inventing approval propagation.

The source must be one unchanged whole `submission` output bound to the effect's scalar
`payload` input. Staging and dispatch require the latest completed human visit on the same
token, actual claimed reviewer COMPLETE/approve action, submitted form, workflow/checksum,
policy and identical raw submission hash. A changed input or action cannot reuse approval.
Read-only AI tool approval and AI confidence are never human business approval.
Generic process resume also rejects a protected create wait after real approval: a
caller cannot invent a receipt or settle queued work. Only verified worker/lookup
completion owns that result; unprotected resume contracts are retained.

Publication diagnostics retain stable machine codes and a JSON pointer to the affected
operation. Node inspectors can use these English/Farsi explanations without changing
the wire codes:

| Code | English | Farsi |
| --- | --- | --- |
| `protected_effect.operation.invalid` | Create must be a normal service task. | ایجاد سفارش باید وظیفهٔ سرویس عادی باشد. |
| `protected_effect.subprocess.unsupported` | Protected child execution cannot inherit approval from its parent. Unprotected child reviews may precede a separate root approval. | اجرای محافظت‌شدهٔ زیرفرایند نمی‌تواند تأیید والد را به ارث ببرد. بررسی زیرفرایند بدون اثر محافظت‌شده می‌تواند پیش از تأیید مستقل والد انجام شود. |
| `protected_effect.approval.binding_required` | Bind the complete human submission directly to the order payload. | ارسال کامل فرم انسانی را مستقیم به ورودی سفارش متصل کنید. |
| `protected_effect.approval.action_required` | Declare a complete approve action with full validation. | اقدام تکمیل با نتیجهٔ تأیید و اعتبارسنجی کامل تعریف کنید. |
| `protected_effect.approval.bypass` | Every route to the order must pass the required human approval. | همهٔ مسیرهای سفارش باید از تأیید انسانی لازم عبور کنند. |

Staging the approval, attempt and outbox is one caller transaction: rollback exposes none.
Workers recheck active ordinary publisher, current `workflows.manage`, authorized grant,
exact connection ref/version/secret version, live-verified state and registered provider.
Offboarding, role/grant revocation and rotation fail closed. No admin identity or latest
connection is substituted. Metadata, configured connection, resolvable secret,
verified connection and actual executable current pin are distinct facts; catalog GET
is evidence only of the first. AI verification is secret resolution, not a paid model test.

## Dispatch, uncertainty and reversal

Create uses UUIDv5 of the execution ID and operation version. The canonical typed payload
hash includes default `note`; the raw human submission hash is recorded separately for
exact approval equality. `PREPARED` means staged, `DISPATCHING` is committed before HTTP,
`UNKNOWN` means a possible effect without confirmed acknowledgment, and `CONFIRMED`
contains a schema-valid receipt. Public projection exposes identities/state/receipt/hash,
not payloads, credentials or private URLs.

Network transport performs one HTTPS request, no redirects, no environment proxy and no
implicit SDK retry. Certificate validation remains enabled, optionally using the existing
administrator-configured CA. Network deadline is 10 seconds total and receipt size is
bounded to 8192 bytes. No database session or transaction spans network calls. Secret/TLS
preflight failure is known before HTTP; only that create path may return to PREPARED.
Timeouts, invalid/oversized replies and lost acknowledgments remain unknown.

Receipt contains `operation_id`, durable `receipt_id`, `state` CREATED/CANCELLED and
`payload_hash`. Duplicate dispatch cannot send another create once DISPATCHING, UNKNOWN
or CONFIRMED exists. Operator lookup is immediate for UNKNOWN and allowed for abandoned
DISPATCHING after 20 seconds. Missing receipt remains UNKNOWN, including a crash after
local fence but before HTTP. It never proves no effect or releases a blind retry.

Explicit process cancellation/compensation uses the existing requester-control policy
and reverse-order compensation records. The registered cancel family derives its own
stable UUIDv5 from the record. It persists dispatch intent, then requires an actual
cancellation receipt with separate reversal identity, original order identity and matching
payload hash before completing the record/process. Repeated or crashed reversal dispatch
can only GET the original cancellation receipt. Recent EXECUTING duplicate deliveries
return duplicate_in_flight; after an incident an operator explicitly requests recovery.
Recovery audit intent and queued dispatch use distinct command keys. Revoked publisher or
connection pins still block recovery; credentials are never replaced.

Unknown orders cannot be declared compensated. Confirmed orders without a registered
reversal require manual intervention. A late receipt after process cancellation is
retained but does not silently advance the cancelled process or invent compensation.
Failure before a cancellation HTTP request is also conservatively lookup-only after its
persisted dispatch fence. An unavailable/missing reversal receipt is not success.

Public process timeline events include operation.dispatch_started, operation.outcome_unknown,
operation.confirmed, operation.reconciliation_started, operation.reconciled,
compensation.dispatch_started, compensation.reconciliation_requested and
compensation.receipt_confirmed, plus existing lifecycle events.
The original create receipt is historical confirmation evidence; after reversal,
inspect its separate cancellation receipt and process timeline for cancellation status. Payloads use an explicit
small allowlist; no raw business input, exception, secret or private URL is copied.

## Owned sandbox and operational limits

`scripts/order_sandbox.py` runs a separate loopback TLS HTTP server and durable owned
SQLite receipts. It is an explicit test/demo service, not a named vendor or production
integration. It shares the disposable provisioning CA/secret mechanism, not the API's
order storage. Runtime credentials are generated and encrypted privately. SQLite order
and cancellation receipts survive a service restart; changed-payload idempotency replay
returns conflict.

Faults are controlled only by the owned local `order-sandbox-fault` file: reject_before_effect,
lose_reply (after provider commit), delay_reply. There is no HTTP fault endpoint. Normal
checks create and remove only their disposable databases, service directories, queues,
workers and sandbox receipts. They do not reset shared/project data or run a production seed.
Deployment of a persistent demo sandbox and its approved admin endpoint/secret is a
separate operator step. The application/worker require the same admin endpoint mapping;
changing that mapping must be coordinated with pinned cases rather than treated as
permission to silently reroute old execution.

## Supervised AI evidence and evaluation

The existing typed agent, one-request decision adapter, task-wide budget reservation,
unknown-usage holds, encrypted read-only tool approval and Jev evaluation CLI are reused.
No second AI framework or persisted AI store was added. AI evidence returns field names,
recommendation, exact historical agent/model and budget; raw inputs, prompts, checkpoints
and response traces remain private. Missing pinned metadata is marked unavailable, never
replaced by a newer agent. Human outcomes remain in authorized work-item/process history.

The six labeled English/Farsi cases in
`tests/fixtures/delivery/supervised-ai-en-fa.json` run through the existing decision adapter
with a scripted FunctionModel: normal/review and untrusted-text cases. They prove schema,
disclosure/tool boundaries and the human approval graph fence. They do not prove prompt
injection resistance of a live model, business accuracy or calibrated confidence. High
confidence never grants protected execution authority.

Ordinary HUMAN_TASK waiting after a settled recommendation is separate from AI compute.
The existing read-only AI tool-approval wait shares the pinned task elapsed deadline from
budget creation; denied/expired approval and process cancellation prevent the model call.
This implementation does not invent a second human-wait policy or extend model authority.
Unknown provider usage retains its reservation and cannot be made free by retry.

Live Jev evaluation remains BLOCKED by D02: named provider, model/price and permitted test
data/cost approvals are absent. The existing opt-in CLI validates a published agent and
current connection, permitted labeled inputs and suite quote cap. It is not invoked by
ordinary checks. Its quote is not a billing ceiling; partial unknown usage, durable
process reservations and aggregate latency/invalid-output reporting need a reviewed live
acceptance run before a live-evaluation claim. No paid model call was made.

## Verification and peer handoff

Observed before final gate: 71 focused approval/pin/sandbox/bilingual/OpenAPI/inventory regressions
passed; the expanded owned protected-operations profile passed 21 real-service cases,
including actual authenticated HTTP outsider/non-superuser denial and before-HTTP uncertainty
without false compensation, plus invented-receipt denial after real approval. The lost-reply
case runs successive real outbox batches rather than assuming one batch drains prior work.
The full fifteen-stage `mise run check` then passed: 943 default tests, one doctest,
109 required service-profile passes (4/18/29/37/9/12), zero required service skips.
The 198 default opt-in exclusions remain separately listed. Start/end source identity
matched; no new diagnostics or suppressions were accepted. See
[structured verification](protected-operations-verification.json) and the owning
APP-BE-021–025 journals. Subsequent closure edits are documentation only.
Failed early
fixtures, missing recovery, TLS verification, audit-key collision and security findings
remain recorded as implementation-stage evidence; none is relabeled a passing final gate.

Frontend consumers APP-FE-022/025/026/030/032/037 must use the catalog and authorized
projections, preserve current refs and command intent, show queued/unknown distinctly,
and retain manual recovery/approval. No frontend code was modified. APP-BE-023's explicit
browser-triggered workflow/inspectable-receipt criterion still requires the actual paired
browser journey; backend/worker tests cannot establish it. This handoff does not claim
browser, deployed, vendor-certified or full demo readiness. The two exact D07 SDK exceptions
remain VERIFIED_WITH_EXCEPTION; no new warning/scanner suppression is authorized.

A read-only check of the current frontend at `95f88dce6f1a48da87294929041378c174e6b39c`
found its existing generic SERVICE_TASK operation configuration, but no consumers of
`sandbox.order`, `orders/search` or `ai-evidence` under the feature/core source directories.
This is selected-source evidence, not a browser test or a claim about every possible UI
path. Actual receipt/recovery/AI consumer integration and the browser journey remain
separate peer work. No frontend source was modified.
