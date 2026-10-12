# Engineering Backlog

Only unfinished work belongs here. Completed plans and duplicate delivery backlogs were
removed on 2026-10-11 at the owner's request. Consult Git history for committed records.
Do not reuse previously assigned IDs or add completed work back as open tasks. Existing implementation satisfies completed
prerequisites referenced below.

Current behavior is documented in [the documentation home](docs/Home.md),
demo seed guide (`docs/guides/demo-seed.md`), operational handoff (`docs/delivery/DEMO-OPERATIONS-HANDOFF.md`)
and [approved decisions](docs/delivery/approved-decisions.json). Current contract artifacts
remain in `docs/delivery/consistency-2026-10-09/contracts/`.

The eight tasks below remain blocked by their recorded dependencies or external acceptance;
this cleanup does not mark them complete. Assistant C15–C17/A27–A46 contracts are in
the workflow and assistant specification (`docs/delivery/follow-up-2026-10-09/WORKFLOW-SCENARIOS-AND-CONTRACTS.md`).

## APP-BE-031 — Automate paired contracts, hosted checks and rebuilt image verification


Priority: P0
Status: BLOCKED
Verification: IMPLEMENTED
Area: backend / M5
Depends-On: APP-BE-002, APP-BE-028
Related: REPO-004; frontend ARC-04/API-01/QA-07
Decisions: None
Owner: Codex
Estimate: 2–4 person-days; confidence low-to-medium before intake
Change-Record: docs/changes/APP-BE-031.md

### Goal

Certify a concrete backend/frontend pair and actual application image instead of trusting stale checked-in API snapshots or local dependency fixes.

### Context

The local implementations, complete backend/frontend gates and real-service/browser
verification have passed. APP-BE-031 remains blocked on an actual hosted run and
reviewed immutable pair publication. APP-BE-032 retains hosted, deployed, named-provider,
live-AI and product-owner acceptance boundaries. Local checks do not establish those
outcomes. Existing D07 exceptions remain unchanged.

### Implementation sequence

1. Implement/extend backend hosted checks using pinned toolchain and disposable services. Run the same mise run check, upload sanitized diagnostics and prove warning/failure negative gates.
2. Build the runtime image from locked dependencies with the existing production install policy. Run startup/lifespan/health and a real instrumented query against the image; do not substitute the developer venv.
3. Coordinate peer SHA selection and generate actual OpenAPI from the candidate backend. Diff relevant paths, schemas, security, errors, nullable/required/defaults and binary headers; regenerate frontend contracts reproducibly.
4. Publish release-pair manifest with SHAs, hashes, dialects, migrations, seeded defaults and client release. Keep credentials and environment-specific refs out of artifacts.
5. Run the connected scenario with the candidate pair and document rolling/forward-repair constraints; a workflow file without a hosted run is implemented but not hosted-verified.

### Acceptance criteria

- A deliberately incompatible backend DTO change fails the paired check even if operation IDs are unchanged.
- The built image actually runs the tested dependency correction and API contract; clean startup has no unexpected warnings.
- Hosted logs/artifacts identify exact pair and scope; pending/unavailable hosted runs remain unverified.

### Verification and required evidence

Actual hosted backend and paired jobs, image startup and A24 negative probes; A18/A19 on the pair. mise run check locally and in CI. APP-FE-037 owns browser-specific assertions, avoiding duplicate harness development.

### Data, compatibility, rollout and peer handoff

C14 → APP-FE-001/005/037/038. Hosted permissions and infrastructure may block evidence; record rather than claiming a pass.

## APP-BE-032 — Close backend demo acceptance, restore and support handoff

Priority: P0
Status: BLOCKED
Verification: IMPLEMENTED
Area: backend / M5
Depends-On: APP-BE-029, APP-BE-030, APP-BE-031
Related: Existing QA-03–07 cross-project release scope; safeguards/restore
Decisions: None
Owner: Codex
Estimate: 3–5 person-days; confidence low-to-medium before intake
Change-Record: docs/changes/APP-BE-032.md

### Goal

Publish a truthful backend capability ledger and demonstrate the operational behavior needed for the requested application, without confusing demo readiness with production certification.

### Context

The local implementations, complete backend/frontend gates and real-service/browser
verification have passed. APP-BE-031 remains blocked on an actual hosted run and
reviewed immutable pair publication. APP-BE-032 retains hosted, deployed, named-provider,
live-AI and product-owner acceptance boundaries. Local checks do not establish those
outcomes. Existing D07 exceptions remain unchanged.

### Implementation sequence

1. Verify all APP-BE task criteria and C/A contract rows, current permission seeds, deletion policy, templates, maps and help metadata. Resolve untested critical branches before declaring scope complete.
2. Run final mise run check from the candidate tree with zero warnings and no skipped required acceptance. Run actual broker/worker/storage/scheduler, migrations and backup/restore in isolated resources; include new tables and template references.
3. Exercise service outage and safe recovery, credential/config restoration, failure logging fallback and reconciliation of external effects. Do not resume dispatch after restore until the sandbox/provider effect state is reconciled.
4. Create operator/startup/reset/runbook and support handoff with known limits, seed/default versions, exact pair, role accounts provisioned privately and named owner roles TBD until assigned.
5. Record DEMO_READY only after paired frontend evidence is attached. Live-vendor/live-AI and user acceptance remain separately signed gates; do not upgrade them from a local simulated pass.

### Acceptance criteria

- All mandatory scenario IDs have actual evidence or the capability is explicitly not accepted; no paper-only closure.
- A restored isolated environment preserves pins/private objects and new personal/notification/calendar/support records under current access rules.
- The final report states what is implemented, verified, demo-ready, deployed and user-accepted separately.

### Verification and required evidence

Full check, real-service suite, disposable restore and paired demonstration. A01–A26. APP-FE-038 supplies browser/user acceptance evidence but is not a precondition to backend-only checks (avoid circular task dependency).

### Data, compatibility, rollout and peer handoff

Product owner signoff is required for USER_ACCEPTED. No RPO/RTO, tenancy, compliance or production throughput guarantee is inferred.

## APP-BE-033 — Define private conversation and proposal contracts with durable ownership

Priority: P1
Status: BLOCKED until current-pair intake and conversation schema upgrade mechanism are recorded
Area: conversations/domain, application, data, presentation
Depends-On: APP-BE-001, APP-BE-003, APP-BE-008
Related: APP-BE-007/010/015, APP-FE-039/040, C15
Change-Record: None
Owner: Backend role — TBD
Provisional effort: 4–7 person-days; low-to-medium confidence, not agent runtime.

### Goal and scope

Private starter+assistant room, bounded ordered user/assistant messages, durable turns, typed action proposals and safe read APIs. No multiparty membership, general workflow editing through chat, arbitrary tool calls or silent job execution.

### Implementation steps

1. Record the exact actor, client, agent/workflow pins, privacy/retention and archive semantics; confirm which existing resource resolver kinds need extension.
2. Implement constrained BaseDTO request/response models, canonical enums and typed content/proposal unions. Separate raw persisted protected text from safe event/correlation projections.
3. Add unique keys for conversation+client message and proposal confirmation identity. Lock or atomically sequence room turns; choose bounded ordered queuing or conflict-on-concurrent-turn and document it.
4. Implement user-only message ingestion and read/search with live/ownership criteria before count/paging; the browser cannot choose another owner or system/assistant role.
5. Stage a turn reference through existing task infrastructure in the same transaction; do not call the model in the route transaction.
6. Export en/fa OpenAPI and documented examples/errors; add current contracts to the paired manifest and permission catalog without auto-granting privileges.

### Acceptance and verification

A31–A33: foreign user enumeration/read/mutation fails; identical message replay has one turn; altered replay conflicts; concurrent tabs cannot corrupt ordering; archived rows disappear from ordinary lists; payload/log bounds and actor cleanup demonstrated. Tests include real PostgreSQL transaction races and HTTP authorization. `mise run check` plus new required non-skipping conversation profile; preserve exact current warning label. Record migration/restore support and rollback/forward repair.

### Frontend handoff

Exact C15 schema/hash, current permission keys, sample ordinary actor fixtures, state/available-action matrix, pagination behavior, safe error codes and immutable version information. Never hand off proposed examples as live test captures.

## APP-BE-034 — Execute bounded assistant turns through governed AI and the existing workflow engine

Priority: P1
Status: BLOCKED by APP-BE-033 and approved model/data configuration
Area: conversations/application, ai/application, step_types, processes
Depends-On: APP-BE-033
Related: APP-BE-019/021/022, APP-FE-039/042, C15
Change-Record: None
Owner: Backend/AI role — TBD
Provisional effort: 5–9 person-days; low confidence.

### Goal and scope

For one persisted turn, produce a validated answer, clarification or action proposal using only permitted context. Reuse AI budget/reservation/provider owners and bounded workflow execution; do not turn the existing AI_DECISION handler into an incompatible freeform chat contract.

### Implementation steps

1. Register a new versioned assistant-turn handler/profile only after checking the locked SDK's actual typed-output/history APIs. Retain old published handler behavior.
2. Build a bounded context projection from explicitly approved help and currently readable resources. Pin source identities/hashes and record minimal metadata; no implicit publisher/superuser access.
3. Reserve one logical model budget before dispatch, bind message/turn identity and typed output schema; duplicates cannot authorize a second model request.
4. Validate result type and source references. Invalid or unsafe output cannot reach an action dispatcher. Clarifications persist no business object.
5. Persist protected response/history and safe failure state separately from generic process logs. Cancellation/late callbacks cannot resurrect a cancelled turn or update a different actor/turn.
6. Add explicit manual/no-provider fallback and synthetic test mode labeling. Live provider tests are opt-in and budgeted; no secret resolution from workstation auth state.

### Policy dependency

Use the existing approved AI runtime and the evaluation/reservation rules owned by APP-BE-025. Completing an answer-only or self-task intent profile does not require a procurement operation. A live model/data/price policy is still a real prerequisite; synthetic construction tests cannot replace it.

### Acceptance and verification

A32–A34/A43: bounded history, adversarial retrieved text, timeout, unknown usage, duplicate delivery, revocation and cancellation. Approved answers use real accessible sources; proposals have no side effects. Pure fake-adapter evaluation is labeled deterministic; one approved live evaluation is separate from application contract correctness. Required worker/DB profile and full gate; no paid retry on uncertainty.

### Handoff

Result union, structured citations, turn states, polling/cancellation behavior, feature readiness and meaningful local fixtures. Do not return hidden chain-of-thought or unrestricted tool history.

## APP-BE-035 — Confirm a proposal and create one real self task or eligible draft

Priority: P1
Status: BLOCKED by C15 plus approved action/principal policy
Area: conversations/application, requests/application, work_items
Depends-On: APP-BE-033, APP-BE-034
Related: APP-BE-005/028, APP-FE-040, C15
Change-Record: None
Owner: Backend role — TBD
Provisional effort: 3–6 person-days; low-to-medium confidence.

### Goal and scope

A confirmed typed proposal creates exactly one permitted business request/self HUMAN_TASK or an eligible draft, with a durable receipt. It cannot assign arbitrary people, bypass required review, publish a workflow or execute generic code.

### Implementation steps

1. Implement an allowlisted application action registry mapping semantic operation/version to typed payload, current permissions, validator, executor and result projector. No browser/model Celery task names or handler imports.
2. Bind proposal expiry, revision, canonical payload hash and version pins. Use server-derived actor/client and exact source resources.
3. Implement confirmation with atomic lock/unique receipt and operation-specific idempotency; identical committed replay resolves the same result with fresh refs and rechecks authority.
4. Use RequestService and the normal process/HUMAN_TASK path for self tasks. For starter-specific assignments, use supported interface binding or add a tested explicit starter policy; never seed all users' tasks to the one fixed demo requester.
5. Preserve differences between create-now/due-later, draft creation and submission. Changed proposal fields require a new reviewed revision.
6. Emit the mapped notification and safe audit evidence transactionally. UI result is a real created resource, not a prose claim that creation succeeded.

### Policy dependency

Freeze the narrow self-task/draft authority as part of C15 using the same operation-policy owner as APP-BE-022. Do not require the unrelated procurement sandbox to exist before a safe self-task can be developed. Any protected procurement effect additionally requires completed APP-BE-021/022 and its exact approval evidence.

### Acceptance and verification

A35–A37: confirm/dismiss, double click, lost response, stale proposal, revoked resources, tampered actor/assignee, required independent approval and hidden fields. Inspect resulting request/process/work item and receipt in real PostgreSQL/HTTP tests. Run full gate plus the new required profile. No detached work-item rows, admin grant or duplicate effect.

### Handoff

Purpose-built form fields, preview summary, available actions, exact confirm body/errors and created-resource locator contract. A generic JSON textarea is not an acceptable frontend completion.

## APP-BE-036 — Schedule, cancel and reschedule owned approved actions durably

Priority: P1
Status: BLOCKED by confirmed action contract and schema/time policy
Area: tasks/application, conversations/application, calendar integration
Depends-On: APP-BE-033, APP-BE-035, APP-BE-017
Related: APP-BE-024/027, APP-FE-041, C16
Change-Record: None
Owner: Backend role — TBD
Provisional effort: 5–9 person-days; low confidence.

### Goal and scope

An ordinary user schedules only an allowed operation on their permitted data, at an exact reviewed instant, without task-admin permission. Persistent clocked schedules/outbox handle delay; no long-lived sleep/ETA queue.

### Implementation steps

1. Create an owned scheduled-action aggregate/receipt with operation/version, exact payload/resource pins, aware UTC instant, original IANA timezone/local intent, late policy, generation and execution links.
2. Validate ambiguity, past times, DST gaps/folds, horizon/expiry and operation-specific grace. State the accepted late policy rather than promise exact-clock execution.
3. Stage through existing PeriodicTaskEntity/database scheduler and fixed registered task mapping. Extract application orchestration from current admin routes only as needed; admin HTTP routes remain unchanged in authority.
4. Implement current-ref/command-key cancel and reschedule before irreversible start. Disable old occurrence and increment/fence generation in the same transaction. Do not invent clocked_at in the old update DTO.
5. At worker dispatch recheck owner/access/operation/connection pins and generation; duplicate deliveries resolve one business intent; retry/unknown-effect treatment is inherited from the operation.
6. Expose owner-only search/detail and current status/actual timings/result. Project safe events into calendar/inbox without duplicating scheduling or silently altering work-item due dates.

### Acceptance and verification

A38–A42: DST/time conversion, cancellation races, task queued before cancellation, reschedule with stale revision, stopped worker/scheduler, actual configured broker outage, delayed dispatch, duplicate delivery and revocation. Use deterministic time tests plus an owned actual clocked worker run. Require no skips in this service profile; full gate and receipt evidence. Human task due-date checks remain separate.

### Handoff

Exact C16 DTOs/current refs/statuses, time-display examples, late-policy labels, allowed cancel/reschedule states, scheduling permission keys and retry-safe operation matrix.

## APP-BE-037 — Produce an authorized summary/report and record action outcomes

Priority: P1
Status: BLOCKED by owned action dispatch
Area: reporting/application, tasks, conversations, notifications/support
Depends-On: APP-BE-035, APP-BE-036, APP-BE-014, APP-BE-015, APP-BE-027
Related: APP-FE-040/041, C15/C16
Change-Record: None
Owner: Backend role — TBD
Provisional effort: 4–7 person-days; low confidence.

### Goal and scope

A concrete immediate/scheduled allowed operation generates a private bounded report or summary and returns an actual receipt/link. This supplies a useful background action rather than only system.ping.

### Implementation steps

1. Choose an existing code-owned report definition and permitted data projection; pin it into the proposed summary operation. Do not introduce arbitrary SQL, columns, external URLs or raw templates.
2. Run through the existing reporting queue/output owner with limits and cancellation. Check resource visibility at execution and download, not only at schedule creation.
3. Commit final result/receipt and mapped event atomically where possible; object-storage effects use existing cleanup/reconciliation semantics.
4. Append conversation/schedule notification mappings with stable identities, current recipient authority and no private report contents in external messages.
5. Record failed/unknown operation through existing support episode rules, avoiding recursive reporting when the sink/delivery fails.
6. Provide explicit difference between queued, running, ready, denied, failed, missed and unknown through the actual new DTOs.

### Acceptance and verification

A39–A43: real private artifact/structured summary, duplicate dispatch, expired/revoked report source, bounded size, failed storage, late acknowledgment and truthful persistence receipt. Scheduler/worker success must link to the actual result, not only a count. Full gate and required real reporting/storage profile; no paid summarization implied unless explicitly configured.

## APP-BE-038 — Seed and verify the private assistant plus connected showcase

Priority: P1
Status: BLOCKED until new conversation/action implementations exist
Area: requests/demo, delivery/testing, operations documentation
Depends-On: APP-BE-005, APP-BE-028, APP-BE-029, APP-BE-031, APP-BE-034, APP-BE-035, APP-BE-036, APP-BE-037
Related: APP-FE-037/043, C17
Change-Record: None
Owner: Backend/QA roles — TBD
Provisional effort: 4–7 person-days; low confidence; excludes earlier existing-task closure.

### Goal and scope

The rich profile installs the actual private assistant workflow and sample task/scheduled-summary paths; an owned paired rehearsal proves them. No chat-looking placeholder, direct fake execution rows or paid call during seeding.

### Implementation steps

1. Register assistant.workspace/1 and scheduled-summary scenarios with complete schemas, labels, graph/layout/version pins, personas and prerequisite checks.
2. Seed deterministic definition/sample context only; use real user commands for acceptance. Synthetic AI and real approved AI must be visibly distinct modes.
3. Execute A27–A46 with committed pair, ordinary actors and real scheduler/worker/storage/sandbox. Test both expected and denied/fault paths.
4. Extend owned reset inventory to conversations/actions/schedules/receipts and preserve non-demo resources. Archive does not imply job cancellation.
5. Restore isolated data/object/credential/configuration backup and demonstrate original pins/current access before dispatch resumes.
6. Capture safe scenario output, gate labels/exceptions, source/contract hashes, manual browser limitations and owner acceptance separately.

### Acceptance and verification

A44–A46 and all prerequisite scenarios. A new person follows the documented mise plan/seed/verify sequence, builds an editable workflow, starts a private conversation, confirms a self task, schedules a summary, observes a real receipt, and repeats the owned demo safely. Full backend/frontend gates and actual browser evidence are mandatory. No DEMO_READY until the whole requested profile succeeds.
