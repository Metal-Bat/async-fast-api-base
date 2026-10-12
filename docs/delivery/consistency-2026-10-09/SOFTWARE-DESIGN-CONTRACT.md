# Software design contract — one product, explicit boundaries

Version: 1.0.0. Date: 2026-10-09. Status: proposed consistency specification grounded in existing behavior. Apply through the named tasks; do not treat this file as proof of implementation or a blanket authorization to rewrite contracts.

Read with `REPAIR-REGISTER.md`, root `BACKLOG.md` and current recorded decisions. These rules extend existing architecture. They do not replace current identities, workflow semantics, APIs, queues, libraries or migration policy.

## SD-01 — What “the same design” means

One business concept must keep the same meaning, units, authorization, lifecycle and command semantics from database through API to screen. Classes and storage shapes are NOT required to be identical.

| Layer | Responsibility | Must not become |
| --- | --- | --- |
| Entity | Persist domain facts, foreign keys, constraints, ownership, revision and audit relationships. | A public response or UI configuration object. |
| Application service | Enforce authorization, invariants, transactions, transitions and owned side effects. | An HTTP client for its own domain or a dumping ground for all services. |
| Public DTO | Define exactly the accepted input or authorized output, with explicit nested meaning. | A dump of an ORM row, secrets, private snapshots or arbitrary extra fields. |
| OpenAPI / Swagger | Describe the actual implemented HTTP/DTO contract and guide consumers. | A second handwritten competing schema or a statement of planned capability. |
| Frontend transport adapter | Decode the actual envelope/types, preserve canonical values and references, and map to feature models. | A place to grant permission or invent missing server transitions. |
| Feature model / UI | Present meaning, interactions, permitted actions, states, localization and accessibility. | A generated CRUD console pretending every endpoint is a finished product feature. |

A persistence column can retain its existing UPPER_CASE name while its DTO field is snake_case. A TypeScript view model may use idiomatic internal naming through an explicit adapter. JSON/OpenAPI field keys stay canonical. Expose `ref_id`, not internal ID plus revision merely for convenience. A business fact omitted for authorization must not reappear in a label, issue, schema default, chart count or inspector.

## SD-02 — Ownership and terminology

Retain `src/apps/<owner>/{domain,application,data,presentation}`, `src/core` and `src/utils`; retain corresponding Angular domain/application/infrastructure/presentation boundaries. Exceptions already justified in repository code are inventoried before changing them.

The shared glossary distinguishes:

| Concept | Meaning / UI wording rule |
| --- | --- |
| Form definition / version | Authored structure / immutable published edition. |
| Workflow definition / version / editor workspace | Business process / executable pinned edition / incomplete visual editing state. |
| Request type / business request | Startable business service / one user's case. |
| Process instance / step attempt | Execution of a pinned workflow / one attempted execution; neither means business approval. |
| Work item | A human responsibility; UI can say “Task” only with context. |
| Background task / schedule / occurrence | Registered worker operation / future dispatch intent / one delivery identity. |
| AI recommendation / tool approval / business approval | Three different kinds of evidence; none is silently interchangeable. |
| Notification / delivery / support incident | User notice / channel attempt and receipt / operational problem episode. |
| Reference / durable resource link | Revision-bearing mutation token / persistent link resolved to current authorized reference. |

Translate display text, not machine keys or codes. A completed process is not automatically an approved request. A queued background action is not a completed external effect. Publish/version selection must not be described as merely “Save”.

## SD-03 — Entity design

For each persisted class, record owner, purpose, mutable/immutable/derived classification, base-class choice, key, revision policy, ownership, deletion/retention policy, constraints, important query paths, and history visibility. Extend `BaseEntity` where its semantics fit. Do not add soft deletion, update APIs or optimistic revisions indiscriminately to immutable events, join tables or receipts.

All new/edited SQLModel entity `Field(...)` calls are multiline, one argument per line, with trailing commas. Expand nested `Column(...)` and `ForeignKey(...)`; preserve types, nullable flags, names, defaults, server defaults, indexes, on-delete/on-update and history behavior. Do not disable formatting to manufacture the layout.

Descriptions explain meaning, ownership, units and lifecycle. Add stable English database comments where the owning convention requires them. Public display translations belong to API/form/UI catalogs, not mutable database column names. The metadata inventory identifies omissions and records genuinely unnecessary fields; do not change physical names or retrofit the entire schema as part of a styling task.

Use aware timestamps for instants and date-only types for all-day dates. Preserve decimal precision and explicit rounding/units. Avoid mutable shared defaults. Constraints and atomic statements enforce uniqueness/concurrency invariants, not an earlier Python check alone. ORM loading and indexing choices follow real access paths; do not add speculative indexes or global soft-delete hooks without evidence.

## SD-04 — Entity-to-DTO mapping

Public DTOs are purpose-specific: create, update/patch, action, detail, list/select, history and report. Share reusable field groups only where meaning and constraints really match. Do not force the response DTO to inherit every new write-time validator: older valid records must remain readable. The schedule DTO family is an explicit review target [E12].

Read mappers accept already authorized and appropriately loaded data. `from_attributes=True` is a convenience, not authorization; do not trigger blocking/lazy database work from response serialization. Fetch required relations deliberately. Routes call an application method, then return an approved DTO/envelope. Do not make routes access private service internals to assemble results.

For each exposed business field, the field matrix records: storage or computed source; type and units; input constraints; read/write visibility; missing/null/default behavior; list/detail projection; OpenAPI schema; UI control/presenter; localization key; and verification. A field without storage (for example available actions) explicitly names its application authority. A hidden storage field needs no public counterpart.

## SD-05 — BaseDTO and wire invariants

All public JSON models, including nested typed objects, responses, pages and envelopes, inherit `core.base_dto.BaseDTO` transitively. Inspect models reachable from actual registered route contracts, not only filenames ending in dto.py. Include generics, discriminated variants and computed output fields.

Canonical field names are snake_case, without serialization aliases or generators that change output. Validation-only aliases require a concrete compatibility record and canonical examples using snake_case. HTTP header names are exempt. Existing enum VALUES and dynamic business-document keys are not automatically renamed to snake_case.

The current BaseDTO guard checks normal field names and computed aliases but not computed field names or nested model inheritance [E02]. Extend checks without breaking legitimate opaque JSON documents, third-party provider adapters or class initialization order. User-defined form properties, localized catalogs, expression maps and allowlisted provider documents require their own bounded dialect contract; do not traverse them as though every dynamic key is a fixed DTO field.

Runtime serialization must agree with the serialization-mode schema. Custom serializers, RootModel-like types and bare dict/list response roots need explicit review. Do not silence validation or convert every object to Any to pass generation. Typed domain collections can remain lists/maps when their element/value contract is clear.

## SD-06 — Input, nulls, defaults and precision

For every mutation, define omission, explicit null, empty string, zero, false and empty collection independently. Preserve untouched data, including data the actor is not allowed to read. Use `model_fields_set` / exclude_unset semantics deliberately for patches. Do not submit disabled/hidden controls as cleared values.

For new fixed-schema command inputs, reject unknown fields unless a documented compatibility need overrides this. Assess backward compatibility before changing the default of every existing DTO. Bound strings, arrays, filters, sorts, recursion, graph sizes and fan-out using existing limits and measured need.

Defaults have a single owner. Current backend appearance defaults are blue/system/comfortable, whereas the frontend reset path selects blue/light [E05/E27–E29]. Persisted “Reset appearance” should use the backend group-reset semantics and apply the authoritative returned value; actor-cleanup's neutral visual state is a DIFFERENT operation. Existing light preferences stay light until the user changes/resets them. Do not silently overwrite all users.

The frontend must apply persisted density, timezone, numbering and supported workspace defaults when it claims they are saved and supported. Unsupported options are disabled with truthful explanations; English/Farsi and Gregorian support do not imply Jalali conversion. Do not change canonical monetary units based on locale.

## SD-07 — API families and compatibility exceptions

Preserve `/api/v1`, existing operation IDs and established resource conventions: POST create/search/report; GET detail/select; PUT resource update; DELETE by current ref; POST history and explicit domain actions. No automatic endpoint for every database table.

Two observed compatibility exceptions are GET/PATCH `/api/v1/me/preferences` and GET/PATCH `/api/v1/me/profile` [E06]. The generic CRUD skill's no-PATCH wording conflicts with them [E07]. Record and reconcile that exception; do NOT rename implemented endpoints to PUT or change merge behavior as a cosmetic correction. New general resource PATCH APIs are not automatically authorized by this exception.

Preserve existing static-path/member routing, plain bounded selector-items alternatives and binary routes. Distinguish list-like reports from generated private export jobs; their existing different protocols are not inconsistent simply because both are called reports. New broad changes require explicit compatibility and migration plans.

## SD-08 — Response and error families

Preserve the actual envelope owners [E09]: success payload under `data`, paginated payload under `result`, public failures with `success=false`, `request_id`, `error`, `code` and approved `data`. Do not normalize everything to one key by breaking clients. Decode each family explicitly in the existing adapter.

HTTP status and application error code are different concepts. Keep current stable code numbers and meaning; a prose instruction suggesting protocol numbers in envelopes must not silently rewrite the deployed error catalog. Record an exception/decision if the skill disagrees with implementation. Validation issue pointers are scoped to actor-visible fields.

Response bodies never contain raw exceptions, SQL, credentials or arbitrary provider bodies. A request ID is not proof that an incident persisted. Support persistence and a support reference must come from the actual returned receipt. Recording failure must not recursively create an infinite series of notification/support failures.

Binary/download streams remain binary with documented headers, MIME/type limits, filenames, cancellation and partial failure behavior. After streaming headers are sent, failure closes the stream; it cannot be converted into a successful JSON envelope. The UI preserves an uncertain mutation result instead of blindly replaying.

## SD-09 — Authorization, references, lists and history

Authorization is server-owned and rechecked at read, mutation and delayed dispatch as required. Pickers, available actions and menu visibility do not grant access. Keep users, roles, permissions, groups, clients and potential tenants distinct; tenancy is still not established.

Ordinary lists/search/select/count use current permitted live rows BEFORE paging. Caller filters cannot undo the base restriction. Related parent/child and cache paths must agree. History, immutable published dependencies, retained execution evidence and expressly authorized recycle/restore paths use their own documented policies; a global ORM filter can destroy required evidence.

Use fresh opaque `ref_id` after mutations. A stored favorite/notification link resolves a durable identifier to the current permitted resource before action. Missing/deleted/forbidden link behavior must avoid private-label leakage. Never parse tokens for identifiers on the client.

## SD-10 — Commands, scheduling and side effects

Separate pure reads, writes, queue intent, external execution and reconciliation. Record idempotency scope per operation, unchanged replay payload, receipt identity and stale-write policy. Concurrency uses database constraints/locks/atomic transitions plus tests; memory-only guards are insufficient.

Existing administration schedules and proposed user-owned scheduled actions are different surfaces. Review DTO-specific time/cron/queue/argument validation against actual scheduler behavior before tightening it. A future execution instant needs timezone-aware confirmation and explicit lateness/cancellation rules. A task due date does not mean delayed creation. Do not grant ordinary chat users `admin.tasks.manage`.

Use the existing scheduler/outbox/workers. Never use an API-process sleep or a second scheduler for chat actions. Recheck authority and pinned approved operations at dispatch. Approval binds the relevant payload/version; AI suggestions and read-only tool approvals cannot replace required human business approval. Database rollback does not reverse a provider effect.

## SD-11 — OpenAPI / Swagger design

Generate from the real FastAPI app with its localization/documentation enrichment. Inspect effective generated schemas, not only route decorators: shared tags/headers are injected centrally [E10]. Keep subject-oriented tags and operation order; Swagger need not be themed to look like PrimeNG.

Every changed public field documents meaning, type, units, bounds, defaults and null/omission behavior. Nested variants document discriminators and applicability. A bounded flexible document has a dialect, allowed subset, limits and metadata/validation mechanism. No unexplained `dict[str, Any]` replaces a structured supported editor contract.

Each operation documents purpose, authority, lifecycle, inputs, output family/content type, success and actual error statuses, references, replay semantics, side effects, limits and required private/correlation/language headers. Include synthetic valid and failure examples. Validate examples against the correct request/response schema; invalid examples must be deliberately labeled and checked as rejections. Do not require exact prose snapshots.

English/Farsi variants have identical paths, operation IDs, security, structural schema, enum values and canonical examples; only approved human-readable text changes. Check input- and output-mode schemas separately. Run Swagger UI smoke when changing documentation rendering, complex nested display or “Try it out” behavior; generated JSON alone is not browser evidence.

## SD-12 — Frontend contract boundary and feature completeness

One frozen producer identity drives the main generated transport and reviewable metadata slices. Do not accumulate separate stale schema copies for each new service. Existing per-feature generators may remain but must point to the same source identity. Changing a schema hash is not semantic reconciliation.

For every relevant operation record persona, screen, action, input control, result presentation, authorization, implementation status and evidence. Legitimate dispositions include standard UI, advanced administration, session boundary, internal or explicit exclusion. Generated client presence is not functional UI coverage.

Unknown document versions or enum values trigger a bounded compatibility state that preserves recoverable edits; never silently reinterpret or erase them. Adapter fixtures preserve false/zero/empty/null/missing, exact decimals, refs and nested identity. Do not fetch privileged design schemas to render an ordinary user's form.

## SD-13 — Visual design system

Use the current PrimeNG-first policy for new/redesigned business controls, semantic theme tokens and Tailwind layout. Retain justified Material/CDK/native/canvas adapters. Do not replace libraries or add a paid widget without a scoped decision. A native textarea for a person's comment is not a JSON defect.

Define reusable patterns for list/query/filter/selection, detail/header/actions, form field/errors, dialog/drawer confirmation, status/empty/loading/forbidden, notification/deep link, help and incident. Shared patterns carry behavior and accessibility; feature editors retain domain meaning. Do not introduce one universal schema console for every screen.

State badges distinguish business outcome, execution state, save state and delivery state. Styling uses semantic tokens, logical CSS for direction, predictable spacing/typography/density and accessible contrast. Overlay focus, keyboard restoration and error association are part of the component contract. Visual consistency is tested on actual light/dark and en/fa combinations, not inferred from PrimeNG imports.

## SD-14 — Forms and canvas

The same runtime renderer and canonical documents power author preview and the authorized runtime, with clearly different context/permissions. All supported ordinary form/workflow configuration has purposeful controls; expert JSON is optional, labeled, redacted and unnecessary for completion.

Keep form field keys, row identities, graph keys/ports and version pins stable during reordering/renaming. Editing display labels must not rename canonical properties implicitly. Removing a visible field or mapping must preserve unrelated and unknown-compatible state, warn about dependencies and never delete hidden canonical values. Preserve unsaved edits through validation errors and deliberate stale-write reconciliation.

Canvas summaries show relevant information; selection reveals detail. Distinguish control edges from data mappings. Do not offer executable connections unsupported by the registry. A saved workspace is not necessarily promoted or published. Synthetic preview, live read-only test and side-effectful execution are distinct controls and permissions.

Default restore, layout reset, unsaved-discard and demo-environment reset stay separate. Restoring an immutable version produces a draft/successor; active cases keep pins. Rich seeds have full form/graph/layout/dependency provenance and never overwrite a user's changed definitions.

## SD-15 — Lightweight help, notifications and recorded failures

Keep help content frontend-owned and multilingual; persist only the small actor/key/revision/locale seen/dismissed state. Reading help continues when acknowledgement persistence fails, with an honest unsaved state. No CMS or marketing-tour engine is required.

The notification map ties committed event to recipient policy, template/version/locale, channel policy, safe target, dedup identity, invalidation and verification. Source changes and permission revocation are rechecked before delivery/open. Notification presence does not prove provider receipt.

Support incidents retain approved safe code/category/operation/build/correlation and counts, not business payloads, prompts, uploads or stack traces. UI labels reflect actual persistence. Browser intake is bounded, rate-controlled and nonrecursive; normal validation/stale errors are not endless technical incidents.

## SD-16 — Complete screen states and session lifecycle

For each standard interaction exercise loading, empty, invalid, forbidden/revoked, stale/conflicting, failed, uncertain and successful states. Include slow responses, out-of-order responses, session expiry, logout/login as another actor, route teardown and unsaved navigation. Actor epochs fence all asynchronous state and cached selected labels.

English/Farsi catalogs cover added display text, plural/parameter requirements, dialogs and errors. Keep canonical strings and machine values intact. Test keyboard, screen-reader announcements/focus, RTL mixed identifiers, zoom and responsive layouts. Automated accessibility checks cannot attest unperformed manual review.

## SD-17 — Verification and status

Final `mise run check` is mandatory on an unchanged source tree, followed by or including the feature's required database/HTTP/browser/worker/service checks. Record exact source pair, lock hashes, test profile, warnings, skips, artifact paths and limitations. No hidden stderr, ignored return code, weakened budget, all-purpose warning filter or fixture fallback earns completion.

Current backend D07 records two exact SDK exceptions. Respect the recorded decision and label its result `VERIFIED_WITH_EXCEPTION`; strict exception-free verification remains a separate unmet property. Do not silently revoke approval or manufacture strict readiness. New exceptions need explicit review. Frontend diagnostics remain failure conditions under its existing rule.

A no-peer local frontend check is not an integrated check. Required demo verification fails when the peer or services are missing. Every gate must reject source changes during execution, missing/empty scenario evidence, required skips and unsuccessful child processes. Add bounded deadlines and cancellation cleanup; diagnostic events never include secrets.

Separate designed, implemented, locally verified, integrated, demo-ready, deployed and user-accepted. A source-level convention check cannot attest all feature paths. All required original APP work remains open until its own acceptance passes.

## SD-18 — Change, migration and scope control

Before implementation reconcile the current source and all overlapping tasks. Existing satisfied acceptance is reused; new discoveries amend the correct parent or a traceable child without changing old completion history. Implement one coherent task at a time; one worker owns migrations/lockfiles/generated contracts.

DB-002's recorded two-revision baseline and legacy-transition requirement supersede old additive-policy prose. New persistent fields/tables require a recorded safe upgrade approach; this package authorizes no stamp, reset, downgrade or rewrite of applied revisions. Metadata-only review can proceed while that question is resolved.

Run graphify query/path/explain when its local graph exists and update after code changes as AGENTS requires. An unavailable tool must be reported, not claimed to run. Do not mix a full repository reformat or framework upgrade into a feature. Preserve existing public interfaces or provide deliberate compatibility/migration tests.

This design contract is a checklist to make incompleteness visible, not a claim that nothing else can ever be missing.
