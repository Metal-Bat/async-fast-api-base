# Repair register — amend existing owners, do not duplicate work

Date: 2026-10-09. All items below are proposed follow-up deltas; no completion status is changed by this document. `Rxx` identifies a review finding, NOT a replacement execution ticket. Execution remains with its listed APP/CONS owner. For a historically DONE parent, add an explicitly scoped child or follow-up with an unused suffix after checking the current ledger; do not erase the historical result.

The two heads remain the same as the preceding review. Reused evidence has the same pinned identity. “Recorded gap” means the repository or prior handoff reports it; “confirmed source” means the inspected implementation shows the stated condition. Neither means a new full test run.

## Priority order

Current-pair compatibility, authority/approval, loss of data and misleading results precede cosmetic changes. Independent user settings/help/calendar integration can proceed without a completed external-operation policy. New assistant scope follows the existing usable-product work rather than forcing a replacement architecture.

## R01 — Freeze and consume one current frontend/backend contract pair

Priority: P0 for integration
Execution owners: APP-BE-031; APP-FE-005, APP-FE-033, APP-FE-037
Evidence class: Recorded integration gap [E24–E26/E35/E36]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

The earlier frontend rehearsal stopped on a recorded 53-path/121-schema mismatch. These numbers describe that historical rehearsal, not a new exact-pair diff performed here. Main client checks still use the older copied producer baseline.

### Required change

Generate and retain current en/fa schemas plus inspector/resource/help/calendar/inbox/support/metrics/defaults metadata from an exact commit. Review every method/schema/security/semantic delta. Regenerate the main transport and affected adapters rather than only copying dictionaries. Add a producer acknowledgement with byte and semantic hashes.

### Acceptance and verification

Current-pair contract comparison and actual HTTP/browser representative services pass. Deliberate drift fails. A missing peer cannot produce integrated status. Old counts/hashes remain historical. Reuse existing generation and paired-smoke.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R02 — Reconcile active instructions, migration decisions and duplicate task files

Priority: P1
Execution owners: CONS-BE-001; APP-BE-001; APP-FE-001
Evidence class: Confirmed instruction conflict [E06/E07/E15/E38]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

The generic CRUD skill forbids PATCH, but implemented self preferences/profile use PATCH. Frontend AGENTS still contains an obsolete migration-policy reference; backend root AGENTS does not include the delivery addendum. Several supplied doc copies repeat task authority.

### Required change

Merge the repository-specific addendum deliberately. Apply the scoped skill amendments after reviewing current behavior. Make current docs/delivery APP backlogs authoritative, with top-level duplicates as links or tested generated mirrors. Update current handoffs to DB-002/D07 and date-stamp old statements rather than editing old evidence.

### Acceptance and verification

An agent can identify one current rule for each HTTP exception, migration policy and readiness label. There is no endpoint rename, wiped history or new warning suppression. Duplicate status/manifest drift is detected.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R03 — Cover computed DTO names and nested public model inheritance

Priority: P1
Execution owners: CONS-BE-002
Evidence class: Confirmed guard gap; isolated reproduction [E02]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Normal fields are checked by BaseDTO, but computed names are not. An outer BaseDTO also does not ensure nested typed models inherit BaseDTO. The package probe shows synthetic violations on Python 3.13.5/Pydantic 2.13.5; it does not identify a shipped violating endpoint.

### Required change

Add red tests on the pinned environment and extend the existing guard plus route-reachable schema audit. Cover generics, inherited computed fields, aliases, custom serializers and dynamic-dialect exceptions. Only change shipped output through an explicit compatibility disposition.

### Acceptance and verification

Noncanonical fixed computed/nested wire fields are rejected or reported with the exact schema path. Valid snake_case, dynamic business keys and HTTP headers remain valid. Full final gate plus actual exported response conformance passes.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R04 — Complete entity/DTO/Swagger field documentation consistently

Priority: P2
Execution owners: CONS-BE-003; CONS-BE-004
Evidence class: Confirmed metadata variation [E03/E04/E05/E11]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

BaseEntity and preference DTOs contain explicit metadata, while new preference entity columns lack similar descriptions/comments and many incident DTO fields have no descriptions. This is a design/documentation inconsistency, not proof of corrupt data.

### Required change

Inventory meaning, constraints, units, ownership, privacy, lifecycle, null/default and mapping for each touched field. Fill public descriptions in source and required stable entity metadata. Validate effective generated schemas after shared enrichment. Do not rename database columns or expose private fields for symmetry.

### Acceptance and verification

New/touched fields have actionable descriptions and validated examples; entity/migration semantic parity remains intact. Cosmetic legacy debt is explicit and does not block unrelated safe functionality.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R05 — Make verification source-stable, bounded and explicit about integration

Priority: P1
Execution owners: APP-BE-002; APP-FE-002; APP-BE-031; APP-FE-037
Evidence class: Confirmed gate asymmetry [E14/E35/E37]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Frontend checks compare starting and ending source fingerprints. Backend run_check records a starting source fingerprint but has no equivalent final comparison in the inspected script. Frontend paired smoke is optional unless configured, and the browser parent has no per-scope deadline.

### Required change

Extend existing runners to compare final normalized source fingerprints, excluding only approved output paths. Add per-scope start/progress/deadline/cancellation cleanup and retain failure manifests. Required integrated/demo profiles must require a peer and services. Preserve default opt-in test reporting and exact D07 exception labels.

### Acceptance and verification

A stubbed stage that mutates source and exits zero makes the backend gate fail; an output-only artifact does not. A hung/cancelled browser child produces a nonzero result and bounded cleanup. Missing required services, empty evidence and required skips do not pass. Do not just raise timeouts.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R06 — Align schedule create/update/read and typed editor rules

Priority: P1
Execution owners: CONS-BE-005; APP-FE-032; APP-BE-036; APP-FE-041
Evidence class: DTO-level audit target, not reproduced deployed bug [E12/E13]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

The create model checks interval presence, clocked time presence and clocked one_off. Time awareness, cross-field ordering, irrelevant variant fields, queue/argument policy and update compatibility require a complete trace. Response inheritance from create can make later input tightening reject retained rows.

### Required change

Trace actual downstream validation; add specific negative tests. Tighten at the correct seam and provide legacy read/repair behavior. Use typed schedule editors reflecting supported variants. Keep admin scheduling separate from the ordinary-user owned-action contract.

### Acceptance and verification

Correct schedules remain readable/executable; invalid relevant combinations fail safely before dispatch. Retained data is not deleted. A self-action never grants admin.tasks.manage or arbitrary task/queue choice. Real scheduler tests accompany behavior changes.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R07 — Align persisted appearance reset and actually apply preferences

Priority: P1
Execution owners: APP-FE-008; CONS-FE-002; APP-BE-007
Evidence class: Confirmed cross-layer default mismatch [E05/E27–E29]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Backend appearance defaults to system/blue/comfortable. Frontend Reset appearance queues light/blue rather than using the backend group reset. Density is validated in the read path but not applied there; the projection does not yet apply all persisted locale/workspace settings.

### Required change

Keep neutral logout reset separate. For explicit persistent reset use the existing documented group-reset operation and apply the returned defaults/current ref. Finish supported density/timezone/numbering/workspace controls and effects. Preserve unrelated settings and existing user choices.

### Acceptance and verification

Set compact/dark/custom locale, reset only appearance, reload and compare UI with the returned backend defaults. Locale/workspace survive. Test two users/tabs, stale refs and failed save. No unsupported preference is labeled saved-and-active.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R08 — Connect saved views/favorites to existing persistence and current links

Priority: P1
Execution owners: APP-FE-009; APP-BE-008, APP-BE-009
Evidence class: Recorded missing consumer integration [E24–E26]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

The backend owner already exists; frontend snapshot preparation alone is not persistent saved-view/favorite UX.

### Required change

Add actual list/save/rename/update/delete/default actions and favorites navigation. Save the applied query, not unsaved filters or current data. Resolve durable links under current authority. Preserve restrictive filters until deliberate repair.

### Acceptance and verification

Reload/second login persists data; two-tab conflicts are clear; removed fields/resources or revoked authority give repair/remove behavior without stale private labels. No second preference/storage system is built.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R09 — Persist the small multilingual help acknowledgements

Priority: P1
Execution owners: APP-FE-010; APP-BE-010
Evidence class: Confirmed session-only consumer [E30]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

The inspected Help page uses in-memory viewed and dismissed arrays; this does not satisfy cross-session seen-state persistence.

### Required change

Consume the existing self-state APIs with the frontend help key/content revision/locale metadata. Record viewed only after explicit open. Retain help reading while a state write fails; show its unsaved condition. Reconcile metadata deployment, not a new help CMS.

### Acceptance and verification

Reload and another login retain state; a revised/other-locale topic follows defined behavior; reset affects only this user; actor switch fences late writes; forbidden topics stay unavailable.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R10 — Make readiness actionable using actual execution evidence

Priority: P1
Execution owners: APP-BE-011; APP-FE-011; APP-BE-012
Evidence class: Confirmed unknown-only execution probes [E18/E31]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Setup inspect always marks required worker_execution/scheduler_execution unknown; the displayed fixture cannot change this fact.

### Required change

Add an explicit permitted non-paid probe using existing scheduler/outbox/worker paths. Store/consume bounded safe receipts with freshness and target identity. Keep read-only GET inspect from dispatching effects automatically. Link dependency blockers to authorized repair screens.

### Acceptance and verification

Pending/failure/stale/successful probes appear truthfully; cached old success does not verify a new release. Missing group/form/version/connection explains a safe repair destination without exposing private topology.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R11 — Finish the notification map and live deep-link UX

Priority: P1
Execution owners: APP-FE-012; APP-BE-013, APP-BE-014
Evidence class: Recorded unified-notification consumer gap [E22/E26]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Map/template/inbox foundations are not a completed navigation journey until the frontend consumes current targets and receipts.

### Required change

Wire the unified inbox, filters/totals, mark-read refs and durable target resolution. Add map rows only for actual committed new assistant/schedule events. Preserve template/version/locale/recipient/dedup rules and current-access checks at delivery and open.

### Acceptance and verification

Changed/deleted/forbidden resources and expired sessions render safe outcomes. Retries do not duplicate logical notices. Provider delivered, in-app staged and read status remain distinct. No arbitrary external href is trusted.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R12 — Record client failures and expose support episodes honestly

Priority: P1
Execution owners: APP-FE-013, APP-FE-032; APP-BE-015
Evidence class: Recorded incident UX gap [E11/E22/E26]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

A returned request correlation is not a durable support incident. Backend incident intake/inspection exists in the later handoff; the old frontend blocker must be refreshed.

### Required change

Connect bounded error intake and operator list/detail/history/acknowledge/resolve. Display support_persisted/support_ref only from a real response, with rate/dedup/recursion guards and safe machine metadata. Keep expected validation/stale issues as normal UX.

### Acceptance and verification

Sink unavailable is visible but does not block the original safe error. Unauthorized incident access is denied; duplicate technical errors coalesce. No tokens, prompts, form values, provider bodies or traces are persisted in the projection.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R13 — Ship live calendar and analytics routes, not only showcase components

Priority: P1
Execution owners: APP-FE-014, APP-FE-015; APP-BE-016, APP-BE-017, APP-BE-018
Evidence class: Confirmed preview-only examined surface [E22/E31]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

The inspected FoundationPreview is hardcoded and excluded from production routing. Components and backend services should be connected, not recreated.

### Required change

Add production routes/adapters, permitted create/update/details/reminders, bounded range navigation and real metric filters/drilldown. Keep workflow due-date projections read-only unless an existing authorized command changes them. Do not imply Jalali support.

### Acceptance and verification

Real events persist and reminders arrive once under current membership. Timezone/all-day/DST behavior is tested. Metrics totals match authorized drilldown lists, including deleted/null/unknown cases; zero is not used for unavailable.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R14 — Give shared schema controls an explicit ownership boundary

Priority: P1
Execution owners: APP-FE-003; CONS-FE-004
Evidence class: Confirmed coupling; design review rather than presumed runtime defect [E32]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Studio FormInspector imports SchemaInput from Administration. This can be deliberate reuse, but its public shared seam and dependency constraints should be explicit.

### Required change

Inspect actual imports and bundle effects. Either expose a narrow shared public interface or relocate only truly generic controls with compatibility exports and tests. Keep domain-specific editors with feature owners; do not duplicate them or restructure every feature.

### Acceptance and verification

No new cycle or dependency on administration-only behavior from Studio; existing selectors/control behavior and lazy loading remain correct. Domain/application layers stay UI-library independent.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R15 — Close supported nested editors without hiding required JSON

Priority: P1
Execution owners: APP-FE-016, APP-FE-017, APP-FE-018, APP-FE-019, APP-FE-020, APP-FE-021, APP-FE-022, APP-FE-023, APP-FE-024, APP-FE-025, APP-FE-030, APP-FE-031, APP-FE-033; APP-BE-019, APP-BE-020
Evidence class: Recorded normal authoring gaps [E33/E34]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Typed inspector work is partial. Some field policies, candidates, structured/list mappings, operation/agent/connection choices and provider configuration still need purposeful controls.

### Required change

Classify each JSON match in context. Implement each supported normal shape through actual metadata, selectors and domain editors. Keep advanced diagnostic JSON optional and redacted. Unsupported compatible documents preserve data and report the exact missing capability.

### Acceptance and verification

A designer configures the reference form/workflow, saves/reopens/publishes and demonstrates it without JSON or copied refs. Legitimate comment textareas are retained. Removing a panel without replacing capability does not pass.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R16 — Use the actual restore contracts and keep environment reset separate

Priority: P1
Execution owners: APP-BE-026; APP-FE-027; APP-BE-029
Evidence class: Implemented backend/unfinished consumer boundary [E21/E26]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Default preview/apply/layout reset already exist. Some docs still describe old migrations and peer blocker status.

### Required change

Consume current plan/token/ref/error contracts through preview/confirm/apply UI. Preserve immutable baseline hash, binding choices, current permissions and command identity. Layout reset changes layout only. Environmental demo reset remains separately owned and guarded.

### Acceptance and verification

Published/retired versions get an appropriate successor draft; active process/submission pins are unchanged. Stale plan/workspace/ref and repeated confirmed command are covered. No browser-only reset is passed off as backend restoration.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R17 — Add rich scenario profiles with complete default provenance and safe repeatability

Priority: P1
Execution owners: APP-BE-005, APP-BE-028, APP-BE-029; APP-FE-037; APP-BE-038
Evidence class: Confirmed basic seeder scope and completeness gap [E19/E20]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

The existing installer has two basic templates. Provenance is based on the form document; its existing-workflow branch does not verify the complete installed graph against the expected template. This is a convergence/default-verification gap, not evidence of a bypass of published immutability.

### Required change

Extend current seeder with versioned manifest/hash over form, executable graph, layout and bound dependencies. Verify existing versions without overwriting operator changes. Use preview/apply/default contracts and rich scenario definitions already supplied. Keep basic mise aliases inert until merged; rich command family still needs implementation.

### Acceptance and verification

Seed/check twice converge; a changed expected graph with the same form is detected; modified drafts are preserved or explicitly repaired. Missing handler/provider dependencies fail or clearly block the requested profile. Reset touches only manifest-owned disposable resources.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R18 — Finish required approval, governed external operations and inspectable recovery

Priority: P0 for protected effects
Execution owners: APP-BE-021, APP-BE-022, APP-BE-023, APP-BE-024, APP-BE-025, APP-BE-028; APP-FE-025, APP-FE-026, APP-FE-029, APP-FE-030
Evidence class: Open policy/implementation/acceptance [E23/E24/E26]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

The protected-effect policy is still a proposal in the inspected record. A registered status-check connection does not prove the business action or approval-enforced path.

### Required change

Freeze the exact protected operation/evidence mapping without inventing approval. Implement server publication/execution checks, one useful typed sandbox operation, receipt/reconciliation and current authority. Cover payload changes, corrections, branches and child boundaries. Do not delay unrelated profile/help work.

### Acceptance and verification

No AI result or generic completion satisfies required approval. A lost provider acknowledgment cannot create a duplicate effect. Operators see permitted recovery and receipts, not arbitrary retry for ambiguous effects. Live vendor/paid AI evidence is a separate opt-in.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R19 — Prove private transfer limits and error recovery through the whole pair

Priority: P1
Execution owners: APP-BE-027; APP-FE-036; APP-BE-031; APP-FE-037
Evidence class: Recorded boundary acceptance gap [E26]
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

Streaming and bounded upload work exists. Maximum-size, slow, interrupted and oversized early-response behavior still needs complete actual-service evidence.

### Required change

Preserve current streaming/backpressure/CSRF/refresh behavior. Exercise browser through Node boundary to backend/storage/report worker, including simultaneous transfers and rejection while body is still arriving. Bound memory and time based on measurements; keep errors safe after headers.

### Acceptance and verification

Valid transfers complete and remain private; oversize/cancel/lost response behavior is coherent, not a false success. No automatic non-idempotent replay. Session topology and actual proxy/runtime image are recorded, not assumed.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.

## R20 — Preserve the private assistant and owned actions design from the prior handoff

Priority: P1 subsequent feature scope
Execution owners: APP-BE-033, APP-BE-034, APP-BE-035, APP-BE-036, APP-BE-037, APP-BE-038; APP-FE-039, APP-FE-040, APP-FE-041, APP-FE-042, APP-FE-043
Evidence class: Previously proposed new scope; not implemented by this review
New verification: NOT_RUN except the explicitly isolated R03 probe.

### Observation

These IDs were already proposed in the prior follow-up and must not be allocated again. A durable room, bounded assistant turns, proposal confirmation and owned schedules are new scope, not established by existing AI-decision code.

### Required change

Use the copied prior follow-up and scenario contracts. Start private user/assistant, retain messages/proposal revision and outcomes, dispatch only confirmed allowlisted actions through existing domain owners. Recheck authority/pins; distinguish task due dates from future background execution. Resolve schema evolution first.

### Acceptance and verification

Create one real self task, schedule one authorized summary, restart scheduler, and inspect actual results/notifications without JSON. Multi-user messaging, arbitrary code execution, paid calls and new approval semantics remain outside implied scope. Run complete paired acceptance.

All code changes additionally require the final unchanged-tree `mise run check`, owning regression tests and a linked change record. Required service/browser checks are not replaceable with static package validation.
