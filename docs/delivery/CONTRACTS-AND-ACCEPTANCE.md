# Shared contract and acceptance ledger

Version: 1.0.0 · This is a proposed implementation design, not proof of existing endpoints. Both repository packs carry the same ledger. Apply all changes through the owning backend module and existing frontend adapters. If an equivalent already exists, reuse it and freeze its exact name rather than introducing a duplicate endpoint.

## Contract freeze procedure

APP-BE-001 and APP-FE-001 enumerate current OpenAPI and UI coverage. Each contract below is finalized by its producer task, with generated request/response/error examples. Field names below describe required semantics; proposed field bounds are initial safety defaults to be measured, not production scale commitments. The producer validates them with the consumer before integration. Python nested DTOs and envelopes use BaseDTO; JSON field names are snake_case. Existing pagination, errors, headers and success envelopes remain unchanged. Newly proposed error reason codes are distinct from existing numeric public error codes: map them through the existing error catalog instead of inventing numeric codes here.

Published definitions and active case pins remain immutable. Every mutation documents its actual concurrency token, transaction, replay scope and after-write refs. New GETs must not mutate state. New command replays may only repeat the frozen original payload with its operation-specific key.

## C01 — Bootstrap, seeds and capabilities

Producer APP-BE-004/005; consumers APP-FE-001/011/037. Provide a code-owned manifest of stable semantic keys, versions, dependency keys, content hashes, permission requirements and seed ownership. Reuse registered step handlers, permission definitions and templates. Three profiles: system, installation and explicit demo. Migration/bootstrap data cannot contain a default production password, active provider secret or paid connection marked verified without evidence.

Expose only an authenticated, authorized, non-secret summary through readiness (C06), not raw installation internals. Re-running a profile must be idempotent and preserve operator-owned changes. New versions append rather than mutate published seeds. Empty/disabled groups never receive invented members. Provide dry-run and check-only modes and a scoped summary of created/unchanged/conflicting records.

## C02 — Personal profile and preferences

Producer APP-BE-007; consumer APP-FE-008. Candidate paths: GET/PATCH `/api/v1/me/preferences` and existing self-profile endpoints if available; otherwise freeze an additive self-profile route. Ownership is server-derived from authenticated actor, never a trusted body user_id. Suggested typed preference groups: appearance (theme_mode light/dark/system, approved theme_key, density), locale (en/fa, IANA timezone, supported calendar/numbering), workspace (landing_key, bounded page_size), notification preferences (only configurable categories/channels). Unsupported keys and unknown enum values fail validation.

PATCH distinguishes missing from explicit null and preserves unrelated groups. Include current ref_id in responses and an expected preference ref on mutations using the repository convention; 409 preserves client inputs. Keep profile/contact changes separate from account-security actions and authority-bearing identity attributes. No is_superuser, role assignments, verification flags, password or tokens in preferences. No arbitrary CSS or HTML.

## C03 — Authorized pickers and durable resource links

Producer APP-BE-008; consumers APP-FE-006/009/012/014/027. Prefer existing `/select` operations; normalize their varying envelopes at an adapter, not by replacing all endpoints. Display labels are not keys. Show root name, version, kind and safe availability where allowed; permission/client/dependency checks filter before pagination and count.

For durable favorites/notifications use a stable opaque `link_key` or equivalent existing locator separate from revision-sensitive ref_id. The server stores canonical identity internally, delegates authorization to each domain and resolves a fresh `resource_ref_id` plus allowlisted `route_key`. Candidate POST `/api/v1/resource-links/resolve` with `link_key`; never accept an arbitrary URL or model/table name. Only authorized creators can mint links, and possession grants no access. Bind kind/version intent; a definition pin resolves the same definition version with its current reference, not a newer definition.

A deleted/forbidden/unknown target returns the existing non-disclosing public outcome. Angular uses `/open/{link_key}` only after the route contract is registered and re-resolves after login. No decrypting ref_id, browser-fabricated privilege, stored stale version token or unsafe return URL.

## C04 — Saved views and favorites

Producer APP-BE-009; consumer APP-FE-009. Candidate roots `/api/v1/me/saved-views` and `/api/v1/me/favorites`; mirror actual search/select/detail/update conventions after freeze. Saved view: name (1–120 chars), resource_kind, schema_version, validated query (existing filters/sort_orders), allowlisted column_keys, page_size and optional is_default. Do not save page offsets, raw responses, tokens, unsaved form payloads or arbitrary SQL. Treat free-text filters as private user data, excluded from logs.

Favorite stores resource_kind + canonical target server-side, returns current label/link metadata only after authorization. Enforce unique (actor, kind, target), bounded item count (initial 100 per kind) and deterministic ordering. One default view per actor/scope by atomic update. User filter cannot override soft-delete/authorization base predicates. Deleted/revoked targets are absent from normal favorites; a private management view may offer a generic “unavailable item” removal entry without leaking its title. Sharing/team views are later scope.

## C05 — Small multilingual help catalog and seen state

Producer APP-BE-010 for state; APP-FE-010 for content. Frontend code owns a manifest: help_key, content_revision, route_key, audience/capability hints, order, title/body message keys and explicit en/fa text. No CMS, tour engine, runtime arbitrary HTML or dynamic executable content. Include Help list, contextual inline hint and open/review actions. A list row is not marked seen merely because it was fetched.

Backend stores only actor + help_key + revision + locale + first_viewed_at + last_viewed_at + dismissed_at (bounded timestamps assigned server-side); unique actor/key/revision/locale. Candidate GET `/api/v1/me/help-state`, POST `/api/v1/me/help-state/seen`, POST `/api/v1/me/help-state/dismiss`, POST `/api/v1/me/help-state/reset`. Allowed keys/revisions come from release-manifest metadata, not a second hand-maintained translation catalog. Reset is self-only, explicit and idempotent; does not clear app preferences or business data. New content revision can be unseen without deleting prior history. No tracking time-on-page, form values or unnecessary analytics.

## C06 — Setup/readiness and dependency repair

Producers APP-BE-011/012; consumer APP-FE-011. Candidate GET `/api/v1/setup/readiness` (installation-authorized) and a definition-scoped authoring readiness read consistent with existing workflow/form tools. Return checks with stable key, category, status (ready/blocked/unknown/not_applicable), message_code, safe parameters, checked_at and optional repair route_key/target. These statuses describe the checklist only.

Separate installation readiness from definition publishability, requester eligibility, worker liveness and provider credential verification. A successful HTTP health probe is not a executed worker probe. A secret resolving is not a live provider test. Routine reads are bounded and side-effect-free; active tests are explicit commands with audit and no paid call by default. Repair guidance links to the owning screen; it never auto-grants a role, creates secrets or publishes a dependency.

## C07 — Notification map, unified inbox and deep links

Producer APP-BE-013/014; consumer APP-FE-012. Maintain a code-owned map, versioned alongside tests. Required columns: map_key, actual source event/command, audience resolver, template key/version, allowed variables, channels, mandatory/optional policy, dedupe identity, timing, cancellation rule, resource target, permission check, retention and test ID. `MAP-*` rows below are proposed logical mappings, not existing process event names.

| Map | Trigger meaning | Recipient | Destination | Dedupe / validity |
|---|---|---|---|---|
| MAP-01 | Request submission committed | Requester | Request detail | request + submission occurrence; no duplicate on submit replay |
| MAP-02 | Human work becomes available | Currently eligible candidates, bounded fan-out | Inbox/work item | work item + availability generation + recipient; recheck access |
| MAP-03 | Claim or assignment changes | Previous/new affected claimant where appropriate | Work item | assignment event + recipient; suppress obsolete open-work reminder |
| MAP-04 | Returned for correction | Actual correction recipient | Correction view | correction round + recipient; not just original task id |
| MAP-05 | Human decision committed | Requester and explicit next participants | Request/decision timeline | decision event + recipient; approved is not delivery-complete |
| MAP-06 | Workflow reaches configured final outcome | Requester | Case outcome | actual terminal occurrence/outcome, not inferred approval |
| MAP-07 | External operation fails or is uncertain | Authorized operators, safe requester notice if configured | Incident/operation result | logical operation + failure episode; rate bounded |
| MAP-08 | External business effect confirmed | Authorized case audience | Receipt/outcome | stable provider receipt/logical operation; separate from queued |
| MAP-09 | Report becomes ready or fails | Report owner | My Reports/detail | report generation + state; do not expose file URL to outsiders |
| MAP-10 | Calendar reminder due | Event owner/permitted participant | Calendar event | event revision + reminder occurrence + recipient; edits cancel old work |
| MAP-11 | Work deadline/reminder due | Currently responsible users/escalation if configured | Work item | actual due-time revision + reminder key; no fabricated SLA |
| MAP-12 | AI read-only tool approval required | Eligible human approval claimant/candidate | Dedicated approval panel | approval instance + recipient; never business approval |
| MAP-13 | Support failure recorded/escalated | Support-authorized actor/group | Failure detail | episode + threshold; no recursive notification-failure storm |
| MAP-14 | Account/session security event | Affected user through existing security flow | Account sessions | security event; no token/credential content |

Keep notifications in the existing notifications domain and delivery infrastructure. Current NotificationDTO/mapper requires request/process refs [B18/B19]; non-case reminders cannot be inserted as fake business requests. Prefer an additive unified inbox projection with discriminated case/calendar/report/support targets, while preserving legacy case-only routes/DTOs for old clients. Candidate new `/api/v1/notifications/inbox/search`, detail and read operations over the same domain storage. If the implementation can safely extend the existing shape without breakage, document the exact alternative and paired-client rollout first. Do not create a second notification worker/engine.

Link ownership/authorization is rechecked at delivery and open. Read is explicit; fetching a notification does not approve a task. Localize mapped templates without changing event keys. The normal inbox is not a provider-debug log. Start with in-app plus one real supported notification channel; SMS, push, marketing campaigns and preference overrides of required approval are excluded.

## C08 — Recorded supportable failures

Producer APP-BE-015; consumer APP-FE-013. Classify expected business validation/conflicts separately from technical incidents. Reuse process/task failures and OTel correlation; add a small support projection/record only where necessary. Suggested record: public opaque support_ref, category, stable safe error_code, severity, first_seen_at, last_seen_at, occurrence_count, affected authorized resource locator, request/trace correlation, release pair, operation identity and state (open/acknowledged/resolved) with audited transitions. These are incident states, not process states.

Record using a transaction independent of a rolled-back business transaction. Bound/deduplicate repeated occurrences. Expected 400/403/409/422 cases are not all incidents. Client intake, if needed, accepts only allowlisted screen_key/build/error_code/request_id with strict size/rate limits; no arbitrary messages/stack/HTML/payload. Records omit secret, prompts, attachments and business field values. Admin search/detail requires a dedicated reviewed authority; self support reference never grants global incident access.

When persistence is down, fall back to sanitized operational logging/metrics and expose a correlation id where safe; never claim durable incident storage succeeded. Do not roll back a successful business commit because support recording failed. Notification failure recording cannot recursively generate infinite alerts. Use outbox/incident dedupe boundaries.

## C09 — Workflow-aware calendar

Producer APP-BE-016/017; consumer APP-FE-014. Scope: personal events plus authorized workflow-derived due items, agenda/month/week views, explicit one-off reminders. Team event ownership uses existing groups and explicit checks, not an invented tenant. Recurrence, invitation RSVP, working-day calendars and external sync are separately gated later increments.

Candidate POST `/api/v1/calendar/events/search`, CRUD by ref, and self/team scopes based on actual policy. Range queries use half-open [start,end) and initial maximum 93-day window with page size ≤100; overlap is event_start < range_end AND event_end > range_start. All-day events use dates and exclusive end date, not midnight UTC pretending to be a timed event. Timed events store UTC instants plus a validated IANA presentation timezone. Clarify DST ambiguous/nonexistent local times rather than guessing.

Workflow-derived due events are projections of actual domain due data, not duplicate mutable deadlines. A calendar drag cannot change work-item state/deadline without a supported authorized domain command. Source edits/cancellation invalidate reminders in the same transactional/outbox scheme; reminders recheck current state on execution. Gregorian canonical wire dates stay intact. Persian UI is required; Jalali conversion/input is an explicit separate contract decision D03, not implied by locale.

## C10 — Chart/analytics query contracts

Producer APP-BE-018; consumer APP-FE-015. Implement a small approved metric catalog within reporting/appropriate existing owner. Candidate POST `/api/v1/analytics/query`. Request: metric_key, approved dimensions, bounded date range/granularity/timezone and allowlisted filters. Response: metric key/version, unit, generated_at/as_of, buckets/series, empty-state meaning, and an authorized drill-down query descriptor. No chart-library options, arbitrary SQL, unrestricted entity names or arbitrary joins.

Initial metrics: submitted requests by time; active requests by actual state; my available/claimed work; overdue work when deadline exists; time from submission to terminal completion with explicit population; correction frequency; failed/unknown integrations; confirmed business outcomes only when a configured outcome mapping exists. Unknown/unavailable is not zero. Do not sum money across currencies or assume “process finished” means “approved”. Apply authorization/deletion semantics consistently to detail and aggregate. Historical audit metrics may intentionally include deleted entities only under a named authorized historical metric, never in ordinary operational charts.

## C11 — Authoring schemas, node inspectors and form controls

Producer APP-BE-019/020; consumers APP-FE-016–026. Prefer existing designer metadata, step catalog, selectors, field inventory, expression completion and runtime-preview tools. Supply versioned metadata for a registered handler: type/version, labels/help, configuration schema, typed input/output ports, supported outcomes, conditional properties, selector roles, read-only/sensitive properties, validation diagnostics and safe samples. No backend HTML or component imports. Actual executable semantics remain server-owned.

Required form primitive coverage at inspected baseline: vertical, horizontal, grid, text, textarea, integer, number, date, datetime, boolean, choice, calculated, display, user, group, repeater, table, media, attachment_collection, action [F10]. All rendered UI must preserve canonical null/missing/false/0/empty/exact-number semantics. Unsupported constructs are explicit compatibility errors, not a fallback raw JSON input in a normal task. General expression text may be authored in a constrained expression editor; never evaluate it as JavaScript.

Control transitions and data bindings have distinct identities. Mapping supports only authoritative available source data, typed targets and supported conversion rules. No copying unauthorized execution snapshots into synthetic preview. No lost hidden properties when a purpose-built editor modifies only its owned fields.

## C12 — Approval, integration effects and execution evidence

Producers APP-BE-021–025/028; consumers APP-FE-022/025/026/028–030. Required human approval cannot be satisfied by an AI output or by approval of a read-only tool call. Publication and execution enforce protected effects for the agreed pilot policy; corrections invalidate approval for changed relevant inputs. Validate all selectable normal/review routes, conditional/default edges, parallel paths and subprocess boundaries. No fabricated human completion payloads.

Registered service operation contracts include immutable version, typed input/output, connection restrictions, operation-specific idempotency, deadline, retry policy, receipt, reconciliation method and explicit compensation capability. Existing connection.status remains a diagnostic operation. The first demo business connector is a code-owned HTTP sandbox order operation with an actual separate service/receipt; a named vendor sandbox is a distinct evidence gate (D02).

The execution-principal policy currently derives authority from publisher [B14]. Before adding durable service identities, decide and test offboarding/revocation semantics (D04); never silently elevate to superuser or change active pins. Ambiguous provider outcomes stay unknown/reconcile-first. Redelivery cannot blindly repeat non-idempotent effects. Preserve existing process enums; map external operation state explicitly rather than optimistic “success”. AI budgets distinguish quote limits, reserved/unknown spend and actual usage. A live evaluation needs explicit provider/credential/cost approval and representative labeled en/fa cases, not only fake outputs.

## C13 — Templates, return to default, and demo reset

Producer APP-BE-026/029; consumers APP-FE-027/037. A default is a named immutable baseline, not “whatever the latest code happens to create”. Template manifest: template_key/version/hash, canonical form/workflow definitions, stable node keys, symbolic dependency keys and allowed installation bindings; secrets/users/client grants are not embedded. Existing root/version lifecycle and library helpers remain authoritative.

Candidate workflow-default preview/restore commands follow existing `/workflow-versions/{ref_id}/...` naming only after contract freeze. Preview resolves exact template, current target/workspace refs and authorized dependency bindings, reports diff and blockers, and issues a bounded expiring plan token/hash. Apply uses the same frozen plan and command_key. Any target, workspace, template or binding change invalidates the plan. Two modes: replace an existing DRAFT after confirmation, or create a successor DRAFT from the baseline. PUBLISHED/RETIRED may only produce a new DRAFT; active cases never change. Do not auto-publish or retarget request types. Layout-only reset and discard-unsaved-local-edits are separate operations.

An unassociated custom workflow has no default: offer explicit template selection/new draft, not silent inference. Repeat restoration replays the same command without creating extra drafts. Restore a multi-definition template transactionally when bounded; otherwise use a staged import with no partially exposed publishable state and a documented repair journal.

Demo reset is a separate CLI/harness operation, unavailable in ordinary production navigation. Verify disposable environment identity, a unique demo run marker and an allowlist of owned DB/bucket/queue resources; refuse unknown/shared/production targets. Stop producers, drain/cancel owned work safely, reconcile effects in the sandbox and rebuild only the isolated demo environment. Never use the repository's unrestricted volume-deleting reset task. Reset credentials are regenerated safely and never printed into public artifacts.

## C14 — Paired verification and performance profile

Producers APP-BE-027/028/031/032; consumers APP-FE-034–038. A release-pair manifest identifies both SHAs, dirty-tree digest when applicable, lock hashes, OpenAPI hash, runtime dialects, migrations, template versions and client release. Generate and compare full relevant schemas/security/error behavior; matching operation IDs alone is insufficient.

Provisional demo acceptance profile (D05, calibrate without silently widening): desktop authoring at 1440×900 and 1024×768, mobile requester/reviewer at 390px width, en/fa and light/dark, latest supported installed Chromium and Firefox versions recorded. Browser/device matrix is a product signoff, not a historical test claim. Runtime fixtures: 16/64/256 scalar fields, realistic nested rows and attachments; graph fixtures: 25/100/250 nodes with mixed bindings. Record node/edge/depth/item limits and refuse over-limit work safely.

Measure p50/p95 interactions over repeated warm and cold runs, request latency, network bytes, heap trend, subscriptions, DOM teardown, polling and transfer memory on named hardware. Candidate goals for discussion: ordinary editing feedback ≤100 ms p95, canvas drag frames near 16.7 ms p95 on the agreed reference device, definition open ≤2 s p95 excluding documented network setup. These are proposed budgets, not evidence; D05 can set realistic values with reasons. Preserve existing stricter build budgets until an explicit reviewed change. No arbitrary perf assertion on an unqualified host.

## Acceptance scenario map

Both backlogs use these scenario IDs. Tests must assert actual state and data, not only HTTP 200 or visible success toast.

| Scenario | Required outcome |
|---|---|
| A01 | Clean disposable bootstrap; repeat run has no duplicates or unauthorized grants. |
| A02 | Ordinary role navigation matches API denial; deleted objects absent before paging/count/export. |
| A03 | Two users' profile/preferences/views/favorites/help state remain isolated across logout/login. |
| A04 | Help content en/fa, explicit seen/dismiss/reset, content revision and offline-safe local display. |
| A05 | Saved view preserves validated applied query; revoked/deleted favorite cannot leak or mutate target. |
| A06 | Readiness distinguishes absent/blocked/unknown; repair routes return to context without implicit mutation. |
| A07 | Notification map covers recipient, locale, dedupe, cancellation, read, deep link, and revoked access. |
| A08 | Calendar half-open range, all-day, timezone/DST, source edit/cancel and reminder replay. |
| A09 | Metric fixture totals and drill-down match; unknown data not zero; unauthorized counts do not leak. |
| A10 | All twenty supported form kinds have typed visual editors and shared-runtime conformance. |
| A11 | Node/binding/condition/human/subprocess editing round-trips without JSON or dropped hidden properties. |
| A12 | Save WIP, reopen, invalid promotion, valid promotion, publish, and stale competing editor recovery. |
| A13 | Default restore draft/new draft, changed plan rejection and repeat key; active case pins unchanged. |
| A14 | Eligible requester creates draft with private file, saves, submits twice with same key and gets one case. |
| A15 | Competing claims, filtered edits, required comments, rejection and return/correction are correct. |
| A16 | Protected operation cannot run from AI next/review routes without valid human approval; correction invalidates relevant prior approval. |
| A17 | Parallel branches and pinned subprocesses finish as configured; no guessed branch recovery. |
| A18 | Separate HTTP sandbox operation yields receipt; timeout after accepted effect reconciles without duplicate. |
| A19 | Notification/report/private bytes work through actual worker/storage and same-origin boundary. |
| A20 | Failure survives business rollback where possible; private diagnostic fields absent; sink outage does not recurse. |
| A21 | Worker/broker/scheduler interruption, expired ownership, bounded retry, recovery and restore are actually exercised. |
| A22 | Session expiry/refresh rotation, two tabs, in-flight logout and uncertain mutations remain safe. |
| A23 | Required desktop/mobile/keyboard/screen-reader/RTL contexts and bounded performance profile are recorded. |
| A24 | Both exact check gates pass zero warnings; generated contracts, positive and negative gate probes retained. |
| A25 | Demo reset twice restores known template defaults and scenarios without touching non-demo resources. |
| A26 | Actual owner acceptance distinguishes deterministic demo, live vendor integration and live AI evaluation. |

## Evidence references

Repository snapshots reviewed on 2026-10-08. These sources establish baseline behavior, not current deployment or new test passes. Re-read changed files before implementation.

- **[B01]** [AGENTS.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/AGENTS.md) — Existing graphify, BaseDTO, snake_case, Swagger and entity-format rules.
- **[B02]** [BACKLOG.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/BACKLOG.md) — Existing IDs, DB-001 single initial revision, historical checks and REPO-004 rebuild limitation.
- **[B03]** [.mise.toml](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/.mise.toml) — Actual check sequence; reset removes Compose volumes and is not a safe demo reset.
- **[B04]** [pyproject.toml](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/pyproject.toml) — Python/dependency constraints and two narrow SDK warning filters.
- **[B05]** [uv.lock](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/uv.lock) — Current dependency lock. Latest commit changes FastAPI to 0.143.0 and pycparser to 3.1; enumerate other packages during intake.
- **[B06]** [src/core/base_repository.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/core/base_repository.py) — Shared list/count/get/delete behavior; list/count do not themselves add deleted_at filtering.
- **[B07]** [src/utils/pagination.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/utils/pagination.py) — Shared query allowlists, pagination and optional base criteria.
- **[B08]** [scripts/seed_frontend_browser.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/scripts/seed_frontend_browser.py) — Disposable browser seed imports a test fixture; reuse scenario knowledge, not this as production bootstrap.
- **[B09]** [src/apps/workflows/application/workspace.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/workflows/application/workspace.py) — Independent WIP revision, explicit promotion and checksum guard.
- **[B10]** [src/apps/workflows/application/validation.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/workflows/application/validation.py) — Existing graph invariants, typed bindings, reachability, split/join and bounded-loop validation.
- **[B11]** [src/apps/workflows/application/service.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/workflows/application/service.py) — Publication/dependency checks, grants and AI handoff checks; extend existing owner.
- **[B12]** [src/apps/step_types/application/automation.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/step_types/application/automation.py) — Built-in service operation catalog inspected contains connection.status.
- **[B13]** [src/apps/integrations/application/providers.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/integrations/application/providers.py) — Status HEAD adapter, endpoint restrictions and AI secret-resolution verification.
- **[B14]** [src/apps/processes/application/automation.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/processes/application/automation.py) — Durable dispatch and publisher-derived execution actor.
- **[B15]** [docs/architecture/ai-governance.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/docs/architecture/ai-governance.md) — AI budgets, tool approval, stricter human-approval limitation and evaluation limits; dependency prose is historical.
- **[B16]** [docs/roadmap/full-workflow.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/docs/roadmap/full-workflow.md) — Reference journey and boundaries of combined versus separate scenario coverage.
- **[B17]** [docs/operations/bpms-safeguards.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/docs/operations/bpms-safeguards.md) — Recovery/retention/restore semantics; migration numbers in historical text must not override current head.
- **[B18]** [src/apps/notifications/domain/dto.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/notifications/domain/dto.py) — Existing notification DTO requires request/process context.
- **[B19]** [src/apps/notifications/presentation/routes.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/notifications/presentation/routes.py) — Existing search/detail/read operations and context-dependent mapper; report delegates to search.
- **[B20]** [src/apps/notifications/application/templates.py](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/src/apps/notifications/application/templates.py) — Code-owned versioned templates, initially workflow.notice, with en/fa text.
- **[B21]** [docs/api/form-localization.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/docs/api/form-localization.md) — Gregorian-only implemented calendar profile; Persian digits are not Jalali conversion.
- **[B22]** [README.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/README.md) — Setup, local success gate and disposable integration warnings.
- **[B23]** [.agents/skills/smart-backlog/SKILL.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/.agents/skills/smart-backlog/SKILL.md) — Preserve IDs, inspect baseline and avoid duplicate work.
- **[B24]** [.agents/skills/change-journal/SKILL.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/.agents/skills/change-journal/SKILL.md) — Change-record format and backlog relationships.
- **[F01]** [AGENTS.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/AGENTS.md) — Existing graphify rules.
- **[F02]** [docs/BACKLOG.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/docs/BACKLOG.md) — Stable Steps 1–38 and existing ARC/API/AUTH/UI/FORM/STUDIO/REQ/TASK/PROC/OPS/ADMIN/QA IDs.
- **[F03]** [mise.toml](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/mise.toml) — Actual frontend check commands; full browser/backend suites are separate at baseline.
- **[F04]** [package.json](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/package.json) — Pinned Angular 21.2.25, PrimeNG 21.1.10, Foblex 19.3.0, and available test scripts.
- **[F05]** [docs/UI-LIBRARIES.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/docs/UI-LIBRARIES.md) — Mixed-library baseline, shared theme, in-memory preferences and adapter boundary.
- **[F06]** [docs/STUDIO.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/docs/STUDIO.md) — Existing catalogs, previews, WIP/promote/publish and historical verification.
- **[F07]** [src/app/features/studio/presentation/workflow-board/workflow-board.html](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/src/app/features/studio/presentation/workflow-board/workflow-board.html) — Existing visual board and JSON-based configuration/graph inspectors.
- **[F08]** [src/app/features/studio/presentation/form-builder/form-builder.html](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/src/app/features/studio/presentation/form-builder/form-builder.html) — Current palette/outline and JSON inspectors.
- **[F09]** [src/app/features/studio/infrastructure/workflow-canvas/workflow-canvas.ts](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/src/app/features/studio/infrastructure/workflow-canvas/workflow-canvas.ts) — Actual Foblex implementation: pan/zoom, placement, keyboard movement and read-only behavior.
- **[F10]** [src/app/features/studio/domain/form-authoring.ts](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/src/app/features/studio/domain/form-authoring.ts) — Twenty code-owned primitive kinds and bounded outline operations.
- **[F11]** [scripts/check-platform-contract.mjs](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/scripts/check-platform-contract.mjs) — Checks checked-in evidence, hashes, IDs and refs; not a live backend compatibility proof.
- **[F12]** [docs/ADMINISTRATION.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/docs/ADMINISTRATION.md) — Existing administration and generic nested-configuration limitations.
- **[F13]** [docs/RELEASE-READINESS.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/docs/RELEASE-READINESS.md) — Local evidence, manual accessibility/heap/staging and external signoff limits.
- **[F14]** [docs/SESSION-BOUNDARY.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/docs/SESSION-BOUNDARY.md) — Accepted same-origin server-held token design; single-process session-store limitations.
- **[F15]** [server/session-boundary.mjs](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/server/session-boundary.mjs) — Refresh/replay safety, timeout, response buffering and legacy session wire names.
- **[F16]** [server/main.mjs](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/server/main.mjs) — Incoming body limit and buffering, loopback listener and static serving integration.
- **[F17]** [README.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/README.md) — Historical completion/next-step text conflicts; reconcile against code and task evidence.

### Official technical guidance

Consulted 2026-10-08; live documentation can describe versions newer than the locked project. No automatic framework/library upgrade is authorized.

- **[O01]** [Angular style guidance: feature organization, cohesive components and readable templates; verify APIs against pinned v21.](https://angular.dev/style-guide)
- **[O02]** [Typed reactive forms and null/disabled-value semantics; no blanket conversion of the runtime renderer.](https://angular.dev/guide/forms/typed-forms)
- **[O03]** [Lifecycle-aware subscription cleanup.](https://angular.dev/ecosystem/rxjs-interop/take-until-destroyed)
- **[O04]** [Official design-token approach. Live docs redirect to newer-version site: do not import newer-only APIs into pinned v21.](https://primeng.org/theming/styled)
- **[O05]** [Interaction reference for visual mapping; not an instruction to copy n8n code or execution semantics.](https://docs.n8n.io/data/data-mapping/data-mapping-ui/)
- **[O06]** [Warnings-as-errors and explicit assertion of expected warning cases.](https://docs.pytest.org/en/stable/how-to/capture-warnings.html)
- **[O07]** [Native lint warning thresholds, including max-warnings; verify builder forwarding in installed version.](https://eslint.org/docs/latest/use/command-line-interface)
- **[O08]** [Mise task behavior; the repository task configuration remains the command authority.](https://mise.jdx.dev/tasks/)
- **[O09]** [Locked dependency synchronization and lock freshness.](https://docs.astral.sh/uv/concepts/projects/sync/)
