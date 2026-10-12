# Rich workflow scenarios and private assistant contracts

Date: 2026-10-09. This specification supports the unfinished assistant tasks in root BACKLOG.md; implementation and current producer contracts remain authoritative.

**Status:** proposed implementation specification. The current basic bootstrap exists; the rich profile commands, conversational contracts and action handlers below do not yet exist. Do not claim execution or product completion from this document. Preserve all current machine contracts until an additive or explicitly reviewed compatibility change is implemented.

## 1. Product scope and boundaries

Deliver a repeatable catalog of useful workflows, plus one private conversation for its starter and an assistant. The assistant can answer within approved context, request missing details, propose an eligible draft or human task, and propose an approved immediate or scheduled background operation. Every write requires deliberate confirmation and current server permission; required business approvals remain separate.

A private conversation is not a public chat room, a multiparty messaging system, a general code runner, or permission to expose task-administration APIs. Multiuser conversation membership, presence, typing indicators and collaboration are later scope. Polling with bounded requests is sufficient initially; streaming is optional only after the session/proxy cancellation and replay contract is defined.

Three independent identities must remain distinct:
- The conversation/message/turn: owns dialogue order and context.
- The business request/process/work item: owns business data, human work and pinned execution.
- The scheduled action/task execution: owns durable future dispatch and actual execution evidence.

Creating a task NOW with a future due date does not schedule its creation or execute a background job at that date. The UI must ask or explain which operation is being proposed.

## 2. Scenario registry — extend the existing demo owner

The current `scripts/bootstrap_application.py`, `requests/application/demo*.py`, FormService, WorkflowService, RequestService, existing private uploads and worker infrastructure remain the implementation foundation. Introduce a small code-owned scenario registry in that owner; do not build an independent engine or fill raw execution tables directly.

### Proposed C17 registry entry

Each scenario entry has a stable semantic key and version; localized title/description; intended personas; referenced form/graph/layout documents; typed sample inputs; symbolic dependencies; declared handler/agent/provider requirements; safe expected branch/outcome assertions; allowed modes; and a canonical hash over ALL authored content. Stored credentials, arbitrary network addresses, live record IDs and opaque revision references are not part of the source template.

The dependency binding manifest resolves semantic keys into current authorized installed resources. Type/handler versions are pinned explicitly. A scenario must declare whether it is definition-only, local deterministic fixture, real local sandbox execution, or opt-in live provider execution. A seed command does not execute business effects merely because an integration is configured.

Keep an immutable published baseline plus an explicitly created editable DRAFT copy or successor for designer demonstrations. Do not silently publish a successor, change request-type routing, move active cases, or recreate operator-owned versions. Template upgrades are previewed and deliberate. Repeating the same installation+scenario+version converges or reports a precise conflict; no duplicate roots/cases or hidden overwrites.

### Initial scenario catalog

| Key/version (proposed) | User demonstration | Features and branches | Prerequisites / exclusions |
|---|---|---|---|
| `basic.purchase/1` | Current baseline request, review, correction or rejection | Existing four-node graph and current five case fixtures | Reuse current implementation; do not retrospectively rewrite its published graph. |
| `basic.service/1` | A second domain using the same platform | Existing title/reason form and human review/correction | Reuse current implementation. |
| `purchase.showcase/1` | Realistic purchase with multiple line items and decisions | Exact decimal quantities/prices; currency declared; justification; private attachments; conditional fields; normalization; AI recommendation; required human approval; correction/rejection; parallel finance/procurement child approvals; controlled order action; receipt; notification | AI, order execution and protected approval depend on APP-BE-021–025. Published runnable profile must fail readiness when a required capability is missing. |
| `service.triage/1` | Internal service request with routing and assignment | Category-based routing, available/claimed work, requester correction, supported event/timer wait, due calendar item/reminder, resolution and notification | Use only actual registered types/outcomes. Do not simulate timers by changing DB statuses or sleeping a worker. |
| `automation.scheduled-summary/1` | Create an authorized summary/report at a chosen time | Explicit wall time+zone preview, one-off scheduling, cancellation, worker restart, late-policy behavior, result and notification | Proposed owned action adapter; reuse DB scheduler/outbox/report owner. No arbitrary cron/task names in the ordinary-user UI. |
| `assistant.workspace/1` | Start a private assistant conversation | Answer help; clarify missing inputs; create eligible draft or self task after confirmation; schedule a summary; inspect receipts and failures | Proposed C15/C16 and APP-BE-033–038 / APP-FE-039–043. Not implemented by existing AI_DECISION alone. |
| `recovery.lab/1` | Show understandable, safe failure handling | Missing connection, permission revoked, expired plan, duplicate event, provider acknowledgment lost, bounded timer exhaustion, recorded support incident and authorized reconciliation | Separate isolated sandbox profile with failure injection. Never activate fault injection in normal/live resources. |

The catalog should exercise the 20 current runtime/layout primitives across meaningful forms without forcing every primitive into every workflow. Include at least one hidden reviewer-only field, a repeated-row correction and a private attachment. Keep layout positions, meaningful labels, distinct control/data connections, and inspector help complete so the initial demo is not an unreadable auto-laid-out graph.

### Purchase showcase execution specification

1. Eligible requester opens the published request type and receives pinned runtime documents. Required/default fields are canonical, not locale-dependent machine values.
2. Requester saves lines/attachments; server recomputes derived totals and retains hidden values. Zero, false, empty and missing/null remain distinct. Currency/rounding is explicitly configured; no assumed rial/toman conversion.
3. Submission uses the existing stable submit identity and current ref. An uncertain response is reconciled; it never creates a second case.
4. A trusted normalization step feeds an approved AI recommendation. Missing model configuration yields a genuine blocker or an explicitly selected human-only scenario variant, not a fake AI result.
5. Required human approval binds to the exact protected payload and version. AI normal/review paths cannot bypass it. Return/correction invalidates relevant approval. Rejection terminates according to declared outcomes.
6. Configured finance and procurement branches use existing split/join/subprocess semantics and pinned children. Their merge is tested under opposite completion orders; no branch is guessed during recovery.
7. The order operation runs only after matching approvals. A local sandbox persists a unique operation receipt independently of the application. Lost acknowledgment triggers reconciliation, not duplicate creation.
8. A unified notification links to the current authorized outcome. Dashboard counts, calendar/work lists and history agree with the case. A notification delivery failure is not retroactively labeled business rejection.
9. A new form/workflow version is published while a prior case remains active; both cases retain their exact intended pins.

### Rich command interface — proposed, not included as functioning aliases

Implement by extending the current bootstrap entry point and exposing thin mise tasks. Do not create a second installer. Suggested user-facing family:

```text
mise run demo:workflows --profile showcase-v1 --plan --manifest <private-path>
mise run demo:workflows --profile showcase-v1 --enable-demo --manifest <private-path>
mise run demo:verify --profile showcase-v1 --manifest <private-path>
mise run demo:reset --plan --manifest <private-path>
mise run demo:reset --apply-plan <private-plan-path> --confirm-installation <owned-id>
```

These future flags require parser/schema/test work. They are NOT flags currently accepted by the basic bootstrap. Keep `demo:seed`/`demo:check` from the additive snippet for current basic fixtures. New rich commands must name which requested scenarios are runnable, blocked or intentionally excluded, and exit unsuccessfully if a requested required scenario cannot be fulfilled. No silent subset success.

Planning should support a fresh installation without writing credentials or business data. Existing `--check` and `--dry-run` semantics must remain compatible; new rich planning may be a separate operation. Any created private manifest or plan file must be explicit in its documented side effects.

Verification must do more than count definitions: validate/publish through domain owners, inspect current pins/workspaces, exercise each declared path through HTTP/browser/worker boundaries, inspect receipts and notification targets, and retain a safe manifest. Run with explicit deterministic clock anchors; use an adjustable test clock, not long sleeps, for time-path unit tests.

### Reset versus restoration

- Unsaved editor reset discards local changes only, with confirmation.
- Layout reset changes DRAFT positions/viewport/routing only through the existing command.
- Default restoration previews a named immutable baseline and either replaces a DRAFT or creates a successor DRAFT. It never rewrites published definitions or in-flight pins.
- Demo-environment reset owns a distinct installation manifest and must inventory database rows, private object prefixes, pending schedules/messages and sandbox receipts. Refuse foreign resources, unknown provenance, live provider effects or active leased work. Cancel/drain owned work, reconcile effects, then remove only owned disposable state. Reset twice must be safe.

No general `--force`, shared database truncation or `docker compose down -v` is a valid implementation. Restore the demo to its default templates using the same seed owner after the approved scoped cleanup.

## 3. Private conversation architecture

### Recommended composition

Add a justified `src/apps/conversations` domain for dialogue persistence and action proposals. It owns messages/turn ordering, room access and proposal lifecycle, not a new workflow runtime. Reuse `apps.ai` for governed model calls, `apps.requests`/`work_items` for business tasks, `apps.tasks` for scheduling, and existing media/report/notification/support owners. Angular gets a feature with domain/application/adapters/presentation boundaries.

A conversation stays durable while each assistant turn is a bounded workflow/agent execution pinned to exact definitions. A confirmed long-running action creates/links its own process or scheduled-action record. Do not keep one Celery job sleeping for the lifetime of a chat, or force unlimited chat messages through an existing graph's finite max-visits loop.

### Proposed persistence model

Names below are domain design names, not an asserted current DB schema.

| Model | Required responsibilities and invariants |
|---|---|
| Conversation | Starter/owner, title, locale/timezone context, exact assistant/workflow version pins, state and optimistic revision. Default private; archive is not implicit cancellation of accepted jobs. |
| Message | Stable identity, conversation, sequence, sender kind, bounded text/structured display parts, client message key and created time. Unique conversation+client key; no client-selected assistant/system role. |
| Turn | Exact triggering message/revision, turn state, input context hash, allowed source links, agent/version/budget IDs, response message link, safe failure code. One active response writer per conversation or an explicitly documented queue. |
| ActionProposal | Exact operation/version, typed canonical payload, payload hash, origin turn, owner/authority scope, required approval policy, expiry, optimistic revision and terminal receipt link. |
| ActionReceipt | Durable confirmed command identity, proposal/payload hash, actor, created resource/schedule/process identity, actual outcome and safe support linkage. Atomic with local mutation/outbox; does not claim to reverse external effects. |
| OwnedScheduledAction | Owner, proposal/receipt, allowlisted operation/version, UTC execution instant plus reviewed timezone/wall time, late policy, generation, current state, backing schedule/task attempt links and result. No arbitrary Celery metadata from the model/browser. |

Messages and authorized business values belong only in protected conversation storage with a declared retention policy. Broker messages, routine logs, metrics and generic process events carry operational IDs and safe codes, not raw prompts or model history. Do not expose model hidden reasoning. Context citations/results are ordinary readable evidence, not private chain-of-thought.

### Proposal and turn rules

A user message may result in one of three typed assistant results: answer, clarification, or proposal. The server validates the complete output before displaying or acting. An answer may include authorized source links; a clarification cannot silently create a resource. V1 supports one consequential action per confirmation, avoiding hidden partial multi-action execution.

The server—not the model—selects the actor, permissions, client context, approved connections, task queue and execution identity. Quoted user files, help content, retrieved records and provider text are untrusted data, not instructions granting authority. Resource access is checked when constructing context and again before relevant actions. The workflow publisher must not become an implicit privileged substitute for the conversation starter.

On duplicate message key with identical content, return the existing turn; different content with that key conflicts. Two tabs must not interleave inconsistent dialogue state or double-reserve a model call. A lost model response is not free usage and cannot be replayed blindly. Bound input characters, message history, attachment access, calls/tool calls, total tokens, elapsed time and spend through existing AI governance.

Pydantic AI history/deferred-tool capabilities are reusable implementation tools, not the database/authorization system. Verify exact APIs against locked 2.54.0; do not upgrade the stack merely to match current online examples. Existing read-only tool approvals remain unchanged.

## 4. Proposed C15 — Conversation and action proposal API

All new JSON request/response/envelope/page DTOs inherit BaseDTO and serialize snake_case. Use existing success/page/error envelopes, public error conventions, `Accept-Language`, current opaque refs and private/no-store behavior. The following are CANDIDATE endpoint shapes; reconcile against current routes and freeze in OpenAPI before frontend generation. They do not exist at review time.

| Candidate operation | Intent | Key contract rules |
|---|---|---|
| `POST /api/v1/conversations` | Create own private conversation | Exact eligible assistant/workflow pin, locale/timezone; stable create key; no arbitrary system prompt/provider/owner override. |
| `POST /api/v1/conversations/search` | Search own active conversations | Server actor/live filtering before count/paging; archive visibility explicit. |
| `GET /api/v1/conversations/{ref_id}` | Current detail and pins | Authorized current references, available actions and safe status; no secrets. |
| `POST /api/v1/conversations/{ref_id}/messages/search` | Bounded ordered history | Existing page conventions, deterministic sequence, stable message identities; no unbounded history fetch. |
| `POST /api/v1/conversations/{ref_id}/messages` | Submit one user message | `message_key`, expected revision, bounded content; atomic turn/outbox creation; identical replay recognized safely. |
| `POST /api/v1/conversations/{ref_id}/turns/{turn_ref_id}/cancel` | Request cancellation of owned active turn | Exact current target; no false guarantee after dispatch; cancellation state distinct from completed result. |
| `GET /api/v1/conversations/{ref_id}/proposals/{proposal_ref_id}` | Read reviewable intent | Typed summary, canonical payload/hash, expiry, permissions and policy requirements. |
| `POST /api/v1/conversations/{ref_id}/proposals/{proposal_ref_id}/confirm` | Confirm frozen current intent | Exact proposal revision/hash, unchanged command key/payload, actor recheck; return existing receipt on committed replay. |
| `POST /api/v1/conversations/{ref_id}/proposals/{proposal_ref_id}/dismiss` | Decline proposal | Explicit terminal state, no resource creation; archived/deleted origin policy explicit. |

Resource editing should produce a revised proposal or invoke its actual domain form, not let a client patch the confirmed payload after approval. Expired, superseded or revoked proposals fail closed. A free-text 'yes' may cause a request for explicit confirmation, but must not become a bypass of the frozen approval card.

### V1 approved action set — proposed semantic keys

| Key | Result | Permission boundary |
|---|---|---|
| `self_task.create/1` | A business request using an approved single-human-task workflow; returned work item belongs to the eligible starter. | Current request eligibility and self-task permission; no direct detached WorkItem insert, arbitrary assignee or global admin grant. |
| `service_request.draft/1` | An eligible typed service-request DRAFT with proposed fields. | Existing request-type/client eligibility and canonical validation. Submission/approval remains a separate domain action. |
| `request_summary.generate/1` | Authorized bounded summary/report of explicitly selected owned/readable data. | Existing data/report permissions and approved output destination; no arbitrary query/columns/provider URL. |
| `request_summary.schedule/1` | Owned one-off request-summary action at the reviewed instant. | Same data/action policy, plus current scheduling capability; authority rechecked when it fires. |

Question answering uses approved help and currently readable records. It is not a tool for discovering other users' private data. Add new action kinds only with contracts, UI, permissions, execution policy and acceptance tests.

### Confirmation example — presentation, not a current response DTO

User: “Create a task for me to review the purchase specification tomorrow.”

Assistant first distinguishes missing information: task creation now with tomorrow's due date, or creation tomorrow? It then displays a typed card with title, assignee 'You', description, due time/date, source workflow/version, creation semantics and any required follow-on approval. Confirm creates one real request/work item and returns a fresh authorized link. Dismiss creates nothing.

User: “Generate a summary tomorrow at 9 in Baku.”

For a message received on October 9, 2026, a reviewed example resolves to October 10, 2026 09:00 Asia/Baku, UTC 05:00. That is an illustrative time conversion, not a job created by this review. The preview displays selected data, output, timezone, exact date, late policy, and cancel controls. A schedule receipt means SCHEDULED, not EXECUTED or SUCCESS.

## 5. Proposed C16 — Owned delayed actions

Reuse the existing database scheduler and clocked one-off PeriodicTaskEntity. Stage due delivery through the existing outbox and registered worker policy. Do not place far-future jobs into a worker's memory using a long ETA/countdown or `sleep`. Celery documents limitations of distant-future ETA/countdown scheduling; the existing durable database path is already available.

The action adapter should live in the existing task/application owner, called by the conversation application service after authorization. Extract only necessary orchestration from current routes; do not call privileged HTTP handlers with a fabricated admin. Existing administrative schedule APIs remain admin-only.

### Candidate operations

| Candidate operation | Behavior |
|---|---|
| `POST /api/v1/me/scheduled-actions/search` | Only the actor's permitted actions, with status/date filters and bounded paging. |
| `GET /api/v1/me/scheduled-actions/{ref_id}` | Exact intended time, current state, linked result/receipt and available cancel/reschedule actions. |
| `POST /api/v1/me/scheduled-actions/{ref_id}/cancel` | Current-ref + command-key cancellation; generation fences old queued deliveries; response distinguishes cancelled-before-start from cancellation too late. |
| `POST /api/v1/me/scheduled-actions/{ref_id}/reschedule` | Current-ref + command-key + explicit aware time/zone; only before an irrevocable running/finished state; disable old occurrence and create the new one atomically. |

Creation normally occurs through a confirmed action proposal; a standalone ordinary-user creation endpoint needs the same typed policy, not raw task_name/args/kwargs. Candidate routes are not present yet.

### Time and execution policy

- Accept an aware timestamp, IANA timezone and reviewed local intent. Reject missing timezone when the wording is ambiguous. English/Farsi language does not imply calendar, timezone or currency.
- Reject nonexistent DST wall times; require an explicit fold/offset where a time occurs twice. Preserve all-day dates separately from instants.
- Do not invent Jalali support: the current profile is Gregorian. A Persian-calendar enhancement is a separate contract and control task.
- Validate future time, maximum allowed horizon and expiry. Initial horizons/late thresholds must be named configuration with product-approved values; do not hardcode a service promise in a UI label.
- Store a deliberate late policy for each allowed operation: skip when outside grace, or run once within grace. A scheduler cannot promise exact real-time execution. Show due time, actual start and finish, and lateness honestly.
- Commit confirmed action, receipt, schedule and initial event in one database transaction. Use unique operation/occurrence identities; worker attempts and queue message IDs are not new business intents.
- Recheck owner active status, resource access, exact operation/version and connection policy before network or data access. Revocation or deletion before execution yields a safe denied/cancelled outcome, not a superuser fallback.
- At dispatch, acquire/fence the action generation and appropriate execution lease. Cancellation racing with a queued message prevents pre-start work; a started external effect requires its operation-specific cancellation/reconciliation policy.
- Retry-safe work may be retried with the same logical action identity. Unknown external or model dispatch must be reconciled; never count it as success or zero cost.
- Reconcile final result with conversation, process/work item, notification and report links. A deleted/archived conversation does not silently cancel an accepted background action; show this rule and offer separate explicit cancellation.
- Existing schedule update DTO lacks clocked_at. Implement a specific reschedule use case with invariants; do not send unsupported fields to the old route.

### Existing administrator worker probe — available now

The current backend has `system.ping`, and authenticated task administrators can create a one-off schedule using the existing `POST /api/v1/tasks/schedules` contract. A schematic body is:

```json
{
  "name": "demo-worker-probe-UNIQUE",
  "task_name": "system.ping",
  "schedule_type": "clocked",
  "clocked_at": "REPLACE_WITH_A_FUTURE_AWARE_UTC_TIMESTAMP",
  "one_off": true,
  "enabled": true,
  "args": [],
  "kwargs": {}
}
```

This example deliberately contains a placeholder and must not be submitted unchanged. It demonstrates existing administrator capability, not ordinary chat-user scheduling, a new API, or proof that a job ran. Confirm the actual execution through the existing execution catalog and worker result, not total_run_count alone. Never assign admin.tasks.manage to all chat users to make the example work.

## 6. Frontend conversation experience

Navigation: a permission-aware Conversations entry and a list-first page. Open a private room with readable title, source workflow/agent version information, current status and relevant help. Keep the existing session boundary; no browser tokens or new provider secrets.

The room has a keyboard-accessible message log, composer, pending-turn status, bounded load-older behavior, safe source links, and a side panel for active proposals/created items/scheduled actions. Render text safely; model Markdown cannot execute HTML or scripts. Do not display raw prompt/tool history, JSON arguments or provider errors as ordinary UI.

Proposal cards show domain controls and a fixed review summary. Descriptions and timezone help are localized, while operation keys and canonical values remain unchanged. Confirmation is disabled while stale, expired, unauthorized, busy or awaiting a required review. A payload edit invalidates the previous review. In-flight retries are never automatic for unsafe commands.

Render states explicitly: empty, loading, sending, queued, assistant responding, waiting for details, awaiting confirmation, cancelled, completed, failed, uncertain and permission revoked. Only use wire states actually introduced by the contract; the list is a presentation specification, not existing enum values. Preserve unsent text across recoverable errors in memory; do not persist sensitive drafts to browser storage by default.

The schedule panel differentiates due task, future dispatch, queued work, actual running task and final receipt. Show timezone and actual execution times. Cancel/reschedule require exact current intent and stale-write handling. Deep links resolve current authorized refs, not stored stale refs.

## 7. Notification and support map extensions

Append to the existing map with a new map/schema version after reconciling current IDs; do not renumber MAP-01–MAP-14. Proposed additional semantic triggers:

| Trigger | Recipient | Link / dedup boundary | Rule |
|---|---|---|---|
| `conversation.proposal_ready` | Conversation owner only | Proposal identity + revision | In-app by default; no secrets or raw action payload in email/push. |
| `conversation.action_finished` | Authorized action owner | Logical action receipt, once per terminal outcome | Separate known success, denied/failed and uncertain presentation. |
| `scheduled_action.changed` | Action owner | Confirmed create/cancel/reschedule command | Exactly one notice per committed command; old generation notices never authorize action. |
| `scheduled_action.failed_or_missed` | Owner; eligible operator only when required | Occurrence + failure episode | Use existing support coalescing/rate limits; notification failure cannot recursively create an alert storm. |

Normal assistant answers do not need one global notification per token/message. Technical incidents are recorded through existing support services. The UI displays persistence receipts honestly. A support UUID is correlation, not access authority.

## 8. Acceptance additions A27–A46

Append these to the existing A01–A26 matrix; do not replace earlier scenarios. Each needs ordinary-user HTTP/browser proof where relevant, plus DB/worker assertions. Pure parser/unit tests alone do not establish completion.

| ID | Required scenario and evidence |
|---|---|
| A27 | Same owned scenario install repeated twice: no duplicate roots/cases; complete definition hash/pins remain unchanged; altered operator draft is preserved or conflicts explicitly. |
| A28 | Requested rich profile with missing handler/agent/connection: plan shows localized actionable blockers; apply does not label an incomplete subset successful or dispatch paid/external work. |
| A29 | Open editable copy, alter mappings/layout, restore from baseline with preview/confirm; competing editor causes 409; published version and live case pins are unchanged. |
| A30 | Run all declared purchase branches including correction/reject and parallel completion orders; actual receipt/notification/calendar/dashboard states agree. |
| A31 | Two users cannot read, enumerate, resolve, mutate or receive messages/notifications from each other's private conversations. |
| A32 | Duplicate identical message key returns one turn/response and one budget reservation; different message payload with same key conflicts. |
| A33 | Two tabs submit concurrently; bounded ordered handling or explicit conflict, no crossed context, double action or late-result actor contamination. |
| A34 | Help answer with missing model configuration and provider failure: blocked/explicit fallback behavior, no fake AI completion; prompt-injection fixture cannot obtain another resource or call a forbidden tool. |
| A35 | Self-task proposal is editable before review; confirm creates one real eligible request/HUMAN_TASK; dismiss creates none; arbitrary assignee/client/task_name cannot escalate authority. |
| A36 | Change action payload, source permission, workflow version or proposal revision after preview; old confirmation is rejected and no side effect occurs. |
| A37 | Lose confirmation HTTP response after commit; authorized reconciliation returns the same action/receipt with fresh refs, not another task. |
| A38 | Schedule a known operation for an exact reviewed wall time/timezone; reject ambiguous/past/gap time and test DST fold, language and Gregorian/instant round trips. |
| A39 | Restart scheduler/worker before due time; committed schedule survives, executes once per logical occurrence and records actual start/finish. |
| A40 | Cancel/reschedule before dispatch and after enqueue; old generations cannot run. Cancellation after execution begins reports its actual limit, not false cancellation. |
| A41 | Revoke owner/resource/connection permission before execution; scheduled work is denied/cancelled safely and notification reveals no private data. |
| A42 | Duplicate delivery, broker outage and late recovery: unchanged occurrence identity, configured late policy and inspectable failure/support state. |
| A43 | Unknown provider/model acknowledgment: hold/receipt remains unknown, no automatic duplicate effect or zero-cost accounting; operator reconciliation is authorized. |
| A44 | Real private conversation UI, proposals and schedule cards in English/Farsi RTL; keyboard/screen reader/focus/error paths and no ordinary JSON/opaque-ID entry. |
| A45 | Guarded demo reset twice affects only owned disposable resources, refuses foreign/live effects/active leases, and reseeding returns documented defaults. |
| A46 | Final committed backend/frontend pair passes mandatory checks and real scenario matrix with status honoring D07; migrated new-state restore and source/contract identity are recorded. |

## 9. Decisions requiring explicit recording, not invented approval

- Freeze the protected procurement operation mapping and execution-principal policy already pending in C12/D04; independent private help/UI work should not wait for this.
- Record the initial private owner+assistant model and v1 allowlisted actions; do not assume multiparty chat or arbitrary creation.
- Choose the concrete live/sandbox model and provider account, approved context/retention and paid-call limits. Deterministic fixtures must be labeled synthetic.
- Resolve how new conversation/scheduling tables upgrade existing databases under the current two-file migration policy. Never stamp or reset shared data to bypass the decision.
- Select run-time horizon, late policy, retention and supported timezone/calendar behavior. Use current user preferences where available and confirm consequential ambiguity.

All proposed work remains bounded by existing architecture and permissions. The required result is a working, inspectable application journey, not merely a collection of new routes or a chat-looking frontend.
