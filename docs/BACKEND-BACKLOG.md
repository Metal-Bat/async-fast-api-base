# BACKEND — Complete application and connected-workflow backlog

Delivery pack: 1.0.0  
Prepared: 2026-10-08  
Repository: `Metal-Bat/async-fast-api-base`  
Reviewed commit: `995829eebd9483ac6b589c1648fc799c650ad464`  
Companion: `FRONTEND-BACKLOG.md` in the other repository pack  
Primary goal: **fully usable application and a repeatable, truthful connected-system demonstration**  
Implementation status: **APP-BE-001–020 and APP-BE-026 DONE; 11 remaining task scopes retain their individual status**

## How to use this file

Place this file at `docs/delivery/BACKEND-BACKLOG.md`. Keep the current root `BACKLOG.md` intact and add a link to this delivery supplement. Apply `AGENTS.addendum.md` by merging its section into existing AGENTS.md, never replacing the original instructions. The optional product-delivery skill references the same rules and does not replace existing skills.

This main file is self-contained: task specs, shared contracts, acceptance, execution rules and timing are embedded below. Companion copies of the shared rules/ledger/timing are supplied for convenient reuse. Keep their version/hash synchronized; editing one contract in one repo requires a paired handoff, not silent divergence.

Recommended agent instruction: “Read AGENTS.md, the existing backlog and this file. Execute APP-BE-001 first; then select the next dependency-ready task. Reuse existing code and preserve IDs. Do not mark implementation complete without the full warning-free mise run check and the task’s actual acceptance evidence.”

## Contents

1. Status, evidence and current architecture.
2. Decisions and exact gates.
3. Requirement traceability and milestones.
4. Task index and detailed implementation tickets.
5. Shared proposed contracts and notification map.
6. Agent execution rules.
7. Detailed effort/timing model.
8. Source evidence.

## Status and starting instructions

This is a proposed, source-grounded delivery backlog. No task is marked implemented or verified merely because this file exists. `Status: READY` means ready to START; deliverable readiness requires the verification gates below. `Verification: NOT_RUN` is the initial evidence state for every new task. Existing completed work is reused, not reset.

The first agent executes task 001 for its repository, records the actual local baseline and selects a dependency-ready unit. Do not execute the entire file as one unreviewable change. Large tasks are subdivided using suffixes (for example APP-FE-016a) with their own acceptance, without renumbering the parent. One worker owns migrations, lockfiles and generated contracts at a time.

These files do not authorize repository pushes, production changes, provider spend or destructive shared-data operations. Installation is additive. Existing backlog IDs remain authoritative for their old scope; add a link to this supplement and maintain APP status here, not a second duplicated task body.

## Current implementation to preserve

| Area | Evidence and exact delta direction |
| --- | --- |
| Ownership | `src/apps` domain/application/data/presentation and shared `src/core`/`src/utils` remain. Follow BaseDTO/snake_case and entity formatting [B01]. |
| Tooling | Python 3.14.7 is pinned in .mise; pyproject has Python ≥3.14.7. The reviewed lock update moves FastAPI to 0.143.0. Read the complete actual lock at intake; never infer installed versions from minimum constraints [B03–B05]. |
| Migrations | Current repository baseline is exactly `0001_schema -> 0002_required_data`, authorized in DB-002. The initial planning inventory of b13a0c7d2e44/c24f913ab601 and later additive revisions is historical; legacy database markers require a reviewed transition before deployment. |
| Runtime | Versioned forms/workflows, requests, human tasks, runtime projection and prior frontend contract fixes exist. Extend their tests; do not recreate them from API DTOs [B09–B11/B16, F02]. |
| Canvas persistence | Workspace WIP, separate revision, promotion and publication checks exist. Default restoration reuses them [B09]. |
| Integrations/AI | Governed execution/grants/budgets/tool approval exist. The built-in catalog inspected exposes connection.status; real business effect and full supervision need the listed deltas [B12–B15]. |
| Notifications | Existing templates, search/read/delivery domain and required case refs exist. General application notifications need compatible extension, not fake request IDs [B18–B20]. |
| Operations | Outbox, scheduler, retries, recovery, private media, reports, OTel and restore mechanisms exist. Their combined current-pair evidence must be renewed, not claimed absent [B17/B22]. |
| Personal services | Reuse users/media/auth for profile; frontend baseline holds theme in memory. New persistent preference/help/view/favorite scope is explicit [F05/B08]. |
| Live queries | Shared list/count and pagination seams do not themselves add live-record filtering. Audit individual paths before claiming a concrete leak; preserve audit/history exceptions [B06/B07]. |

This planning session used GitHub file reads and current-ref inspection. Local git access failed with DNS resolution; no repository tests, graphify query/update, browser, migration, deployment or paid provider calls ran here. No application code was changed. Historical test numbers remain historical, not evidence for the new tasks.

## Repository-specific implementation contract

Start by reading `.agents/skills/smart-backlog/SKILL.md` and `change-journal/SKILL.md`, plus relevant route/Swagger skills when coding contracts. Use existing services rather than calling private methods from new routes as a shortcut. New persistence belongs to the appropriate business owner; proposed owner choices are users for preferences/help/views/favorites, notifications for the unified inbox, reporting for metric definitions, and a focused calendar owner only if none exists. A small failure projection integrates current errors/process/task evidence rather than creating a second log platform.

Keep transactions explicit. Never share a mutable AsyncSession across concurrent tasks or event loops, block async routes with synchronous network/CPU work, swallow cancellation or retry ambiguous external effects automatically. Constraints/atomic operations enforce uniqueness and replay identities. Recovery commands preserve current restrictions. Bound inputs/queries/retries/row fan-out; add indexes only after relevant query evidence.

For new APIs, candidate contracts in the shared ledger must be frozen against actual route/schema conventions first. All sample refs are replaced by fixture-generated ones. Initial new test paths in task text are proposed and must reuse matching existing tests where available; they are not claims that files already exist.

## Decisions, defaults and scope boundaries

User-confirmed scope: application bootstrap/permissions; calendar/chart services; persisted profile/theme/preferences; no deleted objects in ordinary lists; complete relevant API UI coverage; Angular/code/PrimeNG review; rich linked workflow authoring; setup checklist; shared pickers; dependency repair; saved views/favorites; notification map; demo harness/default restoration; small multilingual help with seen state; recorded supportable failures; strict warning-free checks. These are user requirements, not invented prior approvals of technical choices below.

| ID | Choice and proposed default | Why it matters / blocked work |
| --- | --- | --- |
| D01 — **SUPERSEDED 2026-10-09** | The owner explicitly requested exactly two repository migration files: `0001_schema -> 0002_required_data`. See [DB-002](changes/DB-002.md). | The earlier additive-only policy and its validation remain historical evidence. New IDs reject old markers; database reset/stamp or production rebaseline was not authorized or performed. |
| D02 — integration and AI | First connected-system demo uses a clearly labeled separate HTTP sandbox with an actual durable receipt and deterministic AI fixtures. Select a named vendor sandbox and approved live AI agent/data/cost cap for live claims. | Allows useful genuine network/worker demonstration without inventing vendor access. Named-vendor/live-AI acceptance remains blocked until access and evidence exist; no hidden automatic purchases/calls. |
| D03 — calendar | Preserve implemented Gregorian canonical wire dates and deliver English/Farsi UI. Jalali input/conversion is a separate explicitly approved extension, not automatically implied by Farsi. | Current backend rejects persian calendar. Do not offer a nonfunctional UI toggle or silently change date interpretation. |
| D04 — execution authority | Least-change demo retains existing publisher-bound execution identity with a dedicated non-superuser demo publisher and tested fail-closed offboarding. A service-principal redesign requires explicit approval. | Do not silently elevate or change active-case pins. APP-BE-022 documents the exact pilot policy; only a new authority model is blocked on further decision. |
| D05 — browser/performance | Use the provisional C14 desktop/mobile, Chromium/Firefox, en/fa/light/dark profile; identify actual test device and agree performance budgets before pass/fail certification. | Implementation/measurement can proceed; supported-device/performance/user acceptance cannot be invented. No untested “works on all browsers” claim. |
| D06 — session/deployment | Retain same-origin server-held tokens. A single-process, restart-signout demo is the minimal existing topology; multiple replicas require a protected shared session design and separate validation. | No automatic browser-token-store switch, new auth architecture or unverified HA claim. Production topology is not established by this plan. |

No assumption is made about tenants, staffing, deadlines, compliance, production scale or recovery commitments. Do not treat clients/work groups as a tenant model. New business approvals, quorum, self-approval restrictions, monetary units or holiday policies need explicit domain requirements.

Later-release candidates, **not silently added to this initial scope**: external calendar sync/invitations/recurrence/holiday engine; Jalali conversion; team-shared views; multi-user collaborative canvas/offline drafts; general bulk commands; arbitrary connector marketplace; BPMN interoperability; enterprise SSO/tenancy; new HA session store. A current existing API cannot be excluded under this list just to avoid finishing its legitimate UI.

## Exact backend gate and evidence ladder

**Current baseline command:** `mise run check` [B03]. It executes lock-check, fmt-check, lint, docstrings, typecheck, security, doctest, test, flow-test and precommit-check in order. Preserve this sequence and add new deterministic contract and feature checks through APP-BE-002; do not replace it with one pytest invocation.

During work, run focused tests. Before any implementation task is DONE, run the full final gate with zero warnings, then its required DB/HTTP/worker/storage/recovery checks. Default check must eventually include the non-paid connected-demo smoke via the existing disposable runner; paid AI/vendor calls remain explicit opt-ins. A missing dependency does not turn into a fixture-only pass.

The normal pytest suite historically contains environmental skips. List them. Each scenario required for this task/demo must run in its appropriate explicit integration profile, regardless of the default suite’s aggregate success. A destructive migration/restore test is allowed only against its named fresh disposable resources. Initial migration policy D01 must be resolved, and image rebuild evidence is separate from the developer environment.

Required final record: command/return code, exact versions, tree/pair hashes, warning count, failed/skipped/xfail details, services/DB identity, test names, migration/head, observed timeline/receipt, browser handoff, support/reset limitations and sanitized evidence. Passing `mise run check` is the minimum engineering gate; feature verified, demo-ready, deployed and user-accepted remain distinct.

## User-requirement traceability

| Requirement | Backend producer | Frontend consumer | Acceptance |
| --- | --- | --- | --- |
| Seed data and permissions | APP-BE-004/005 | APP-FE-001/011/031/037 | A01/A02 |
| No deleted records in ordinary lists | APP-BE-006 | APP-FE-006/007/009/031 | A02/A05/A09 |
| Profile/themes/preferences | APP-BE-007 | APP-FE-008 | A03 |
| Reusable resource pickers | APP-BE-008 | APP-FE-006 | A02/A11 |
| Saved views and favorites | APP-BE-009 | APP-FE-009 | A03/A05 |
| Small multilingual help + seen table/list | APP-BE-010 | APP-FE-010 | A03/A04 |
| Setup/readiness checklist | APP-BE-011 | APP-FE-011 | A06 |
| Dependency readiness/repair | APP-BE-012/019 | APP-FE-011/021/027 | A06/A11/A12 |
| Notification map, inbox and deep links | APP-BE-013/014 | APP-FE-012 | A07 |
| Recorded supportable failures | APP-BE-015 | APP-FE-013/032 | A20 |
| Calendar + reminders | APP-BE-016/017 | APP-FE-014 | A08 |
| Charts/analytics | APP-BE-018 | APP-FE-015 | A09 |
| All relevant API/UI support; no normal JSON | APP-BE-019/020 + owning contracts | APP-FE-001/005/007/016–033 | A10/A11/A14/A15/A24 |
| Code review and Angular best practice | APP-BE-030 | APP-FE-003 | A22/A23/A24 |
| PrimeNG-first design audit/adoption | APP-BE-019 metadata only | APP-FE-004/007 and domain editors | A23 |
| Rich linked workflow canvas | APP-BE-019/021/022/024/026 | APP-FE-020–027 | A11/A12/A16/A17/A18 |
| Required approval and useful integrations | APP-BE-021–025/028 | APP-FE-022/025/026/028–030 | A16/A17/A18/A26 |
| Safe return-to-default workflows | APP-BE-026 | APP-FE-027 | A13 |
| Demonstration harness + environment reset | APP-BE-005/028/029 | APP-FE-037 | A25/A26 |
| Zero-warning mise run check and actual readiness | APP-BE-002/031/032 | APP-FE-002/034–038 | A24/A26 |
| Private attachments, reports, sessions, recovery | APP-BE-024/027/028/032 | APP-FE-028/029/032/036/037 | A19/A21/A22 |

## Milestones and what the demonstration must show

| Milestone | User-visible result | Do not confuse with |
| --- | --- | --- |
| M0 | Audited baseline, scoped deltas, exact contracts and honest strict check behavior. | A complete application or a ready production deployment. |
| M1 | Seeded usable accounts, live-only lists, readable shared records, profile/preferences, saved views/favorites, help and support foundations. | Finishing all visual authoring or the connected case. |
| M2 | Normal visual form/workflow editing, typed mappings/semantics, publication/dependency repair and safe default restoration. | Arbitrary scripting, all BPMN/n8n features or collaborative editing. |
| M3 | Actual requester/reviewer + supervised AI policy + branches + HTTP sandbox business receipt + notification/report/private transfer and recovery. | A named vendor or live model having been verified when a local sandbox/simulator was used. |
| M4 | Operational calendar/reminders and real authorized dashboards that reflect case activity. | Recurrence/external sync/Jalali/BI platform unless separately approved. |
| M5 | Full API/UI/no-JSON closure, repeatable reset, real-service/browser/manual/performance evidence and acceptance handoff. | Automatic production/user acceptance from tests alone. |

Numbers organize outcomes, not an instruction to serialize independent teams. Use actual dependency edges. Deliver incremental demonstrations after meaningful slices, while reserving FULL_DEMO_READY for the whole mandatory requested scope and evidence. Purchase approval is the reference journey; the smaller service-request template demonstrates configurability without building a second business domain application.

## Task index and dependency map

Effort includes implementation, focused review, tests and task documentation. It excludes decision/vendor waiting and the separate contingency in the timing section. An existing fulfilled criterion removes work after intake; do not spend the estimate recreating it.

| Task | Outcome | Milestone | Person-days | Required predecessors |
| --- | --- | --- | ---: | --- |
| [APP-BE-001](#app-be-001) | Reconcile the real baseline, ownership and paired contract inventory | M0 | 1.5–3 | None |
| [APP-BE-002](#app-be-002) | Enforce the complete warning-free local gate and retain evidence | M0 | 2–4 | APP-BE-001 |
| [APP-BE-003](#app-be-003) | Resolve migration policy and establish safe upgrade verification | M0 | 1–2 | APP-BE-001 |
| [APP-BE-004](#app-be-004) | Make system catalogs and permission seeds complete and idempotent | M1 | 2–4 | APP-BE-001, APP-BE-003 |
| [APP-BE-005](#app-be-005) | Provide supported bootstrap and realistic demo fixtures | M1 | 3–5 | APP-BE-004 |
| [APP-BE-006](#app-be-006) | Exclude deleted objects consistently from live queries | M1 | 3–6 | APP-BE-001, APP-BE-002 |
| [APP-BE-007](#app-be-007) | Persist self profile and typed preferences | M1 | 2–4 | APP-BE-003, APP-BE-004 |
| [APP-BE-008](#app-be-008) | Normalize authorized selectors and add durable resource resolution | M1 | 3–5 | APP-BE-003, APP-BE-004, APP-BE-006 |
| [APP-BE-009](#app-be-009) | Add private saved views and favorites without stale-reference storage | M1 | 3–5 | APP-BE-003, APP-BE-004, APP-BE-008 |
| [APP-BE-010](#app-be-010) | Store only the small per-user multilingual help-state table | M1 | 1–2 | APP-BE-003, APP-BE-004 |
| [APP-BE-011](#app-be-011) | Expose truthful setup/readiness checks with safe repair destinations | M1 | 2–4 | APP-BE-004, APP-BE-005, APP-BE-008 |
| [APP-BE-012](#app-be-012) | Add definition dependency readiness and guided repair metadata | M2 | 2–4 | APP-BE-008, APP-BE-019 |
| [APP-BE-013](#app-be-013) | Specify the complete notification event map and compatibility design | M1 | 1–2 | APP-BE-001 |
| [APP-BE-014](#app-be-014) | Implement unified notifications and transactional event delivery | M3 | 4–7 | APP-BE-003, APP-BE-004, APP-BE-008, APP-BE-013 |
| [APP-BE-015](#app-be-015) | Record supportable failures and expose a safe incident projection | M1 | 3–5 | APP-BE-003, APP-BE-004, APP-BE-008 |
| [APP-BE-016](#app-be-016) | Add a workflow-aware calendar with correct time and ownership semantics | M4 | 4–7 | APP-BE-003, APP-BE-004, APP-BE-007, APP-BE-008 |
| [APP-BE-017](#app-be-017) | Deliver calendar and work reminders through existing scheduling | M4 | 2–4 | APP-BE-014, APP-BE-016 |
| [APP-BE-018](#app-be-018) | Provide authorized metric definitions and chart data | M4 | 3–5 | APP-BE-003, APP-BE-004, APP-BE-006 |
| [APP-BE-019](#app-be-019) | Complete typed authoring metadata instead of generic JSON contracts | M2 | 3–6 | APP-BE-001, APP-BE-004 |
| [APP-BE-020](#app-be-020) | Close runtime form and complex-value conformance gaps | M2 | 3–5 | APP-BE-006, APP-BE-019 |
| [APP-BE-021](#app-be-021) | Enforce required human approval before protected business effects | M3 | 4–7 | APP-BE-003, APP-BE-004, APP-BE-019 |
| [APP-BE-022](#app-be-022) | Define governed business operations and execution-principal policy | M3 | 3–6 | APP-BE-003, APP-BE-004, APP-BE-019, APP-BE-021 |
| [APP-BE-023](#app-be-023) | Implement one real HTTP demo business operation with a receipt | M3 | 4–7 | APP-BE-022, APP-BE-015 |
| [APP-BE-024](#app-be-024) | Handle unknown outcomes, reconciliation and supported compensation | M3 | 3–6 | APP-BE-023 |
| [APP-BE-025](#app-be-025) | Verify supervised AI behavior and provide an explicit evaluation path | M3 | 3–6 | APP-BE-021, APP-BE-022 |
| [APP-BE-026](#app-be-026) | Support immutable template baselines and safe return-to-default | M2 | 4–7 | APP-BE-003, APP-BE-004, APP-BE-008, APP-BE-012 |
| [APP-BE-027](#app-be-027) | Complete private transfer/report contracts and backend operational bounds | M3 | 2–4 | APP-BE-001, APP-BE-006 |
| [APP-BE-028](#app-be-028) | Extend one combined workflow regression across all included features | M3 | 4–7 | APP-BE-005, APP-BE-020, APP-BE-024, APP-BE-025, APP-BE-026, APP-BE-027, APP-BE-014 |
| [APP-BE-029](#app-be-029) | Build the guarded demo harness and reversible scenario reset | M5 | 3–5 | APP-BE-005, APP-BE-016, APP-BE-017, APP-BE-018, APP-BE-028, APP-BE-015, APP-BE-009, APP-BE-010, APP-BE-011 |
| [APP-BE-030](#app-be-030) | Review backend code quality and repair feature-critical issues | M5 | 2–4 | APP-BE-001, APP-BE-002 |
| [APP-BE-031](#app-be-031) | Automate paired contracts, hosted checks and rebuilt image verification | M5 | 2–4 | APP-BE-002, APP-BE-028 |
| [APP-BE-032](#app-be-032) | Close backend demo acceptance, restore and support handoff | M5 | 3–5 | APP-BE-029, APP-BE-030, APP-BE-031 |

<a id="app-be-001"></a>

## APP-BE-001 — Reconcile the real baseline, ownership and paired contract inventory

Priority: P1  
Status: DONE  
Verification: VERIFIED_LOCAL  
Area: backend / M0  
Depends-On: None  
Related: REPO-001–004; DOCS-001/002; frontend ARC-04/API-01  
Decisions: None  
Owner: Codex  
Estimate: 1.5–3 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-001.md

### Goal

Give both agents a trustworthy starting point and prevent duplicate implementation. This is intake and evidence work, not permission to rebuild existing features.

### Context: preserve and extend

Completed intake: see `docs/delivery/baseline-and-reuse.md` and
`docs/delivery/contract-manifest.json`. Actual head is c24f913ab601.
685 default tests and four disposable PostgreSQL flow tests passed; 119 opt-in
skips and the two existing SDK filters remain explicit limitations.

B01–B05, B22–B24; F02/F11/F17. Latest reviewed backend SHA is 995829e; the last change only updates the lock, not a feature-completion signal. Existing backend code and tests remain the authority.

### Implementation sequence

1. Read the entire current backlog and change records; inventory src/apps and all currently registered routes/permissions/handlers. Run graphify when its local graph exists. Record a file-level reuse/extend/verify/new disposition for every task in this file.
2. Read pyproject.toml and parse uv.lock; record installed Python/FastAPI/Pydantic/SQLModel/SQLAlchemy/Celery/AI/tool versions rather than copying stale docs. Compare effective uv-run tools with mise pins.
3. Run the existing mise run check without modifying it first. Record warnings, skips and environmental failures individually. Never start its destructive reset task. Read current Alembic heads/history before any DB change.
4. Generate the current English/Farsi OpenAPI using the repository-supported path, hash it and enumerate operations/schemas/envelopes/binary operations. Classify exact capabilities versus existing frontend snapshot; deliver a consumer manifest to APP-FE-001.
5. Create docs/delivery/baseline-and-reuse.md and docs/delivery/contract-index.md (proposed artifacts), link existing IDs and record D01–D06 decisions. Mark already-met APP subcriteria covered by actual evidence, without reimplementing them.

### Acceptance criteria

- Every APP task points to an owning module and an existing feature or explicitly new gap; no duplicate seed/auth/notification/workflow subsystem is proposed.
- The peer can identify the exact API snapshot, schema head and task dependencies. Existing checks are reported honestly even when intake itself is the only completed work.
- If baseline checks fail, this intake record may be complete as analysis but no implementation is marked DONE/VERIFIED; APP-BE-002 owns actual gate repair.

### Verification and required evidence

Validate manifest operation IDs against the running or generated application schema, check links and hashes, and inspect git diff. Do not claim a test suite ran if tool/network setup prevented it.

### Data, compatibility, rollout and peer handoff

No production schema/API change. Outputs are repository-local evidence, task crosswalk, decision log and the exact baseline check result. Shared contract C01–C14 headings must match the frontend ledger.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-001.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

<a id="app-be-002"></a>

## APP-BE-002 — Enforce the complete warning-free local gate and retain evidence

Priority: P0  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M0  
Depends-On: APP-BE-001  
Related: REPO-002/003/004; OBS-001/002  
Decisions: None  
Owner: Codex  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-002.md  


### Goal

Make mise run check the real minimum completion contract, preserving every existing check and exposing warning/skip limitations instead of cosmetically hiding them.

### Context: preserve and extend

B03 defines the actual chain: lock, format, lint, docstrings, types, security, doctest, pytest, flow regression, precommit. B04 contains narrow SDK filters; B02 documents previous local passes and an unverified image rebuild.

### Implementation sequence

1. Reproduce each baseline warning/failure and classify project diagnostic, known dependency diagnostic, expected negative-test output or environment failure. Make the smallest compatible fix with a regression.
2. Use native warning-as-error enforcement for pytest and type checks. Review the two SDK ignores; obtain compatible fixes or leave strict readiness blocked with an explicit exception decision. Do not broaden ignores or silence SDK stderr.
3. Add a structured gate report with exit codes, diagnostics and skip reasons. Fail on warnings, missing required suites, xfail of required scenarios, or mismatched tool/lock state. Keep shell pipe failures visible.
4. Wire contract/schema examples, notification/help manifests and task-owned deterministic HTTP checks into the existing gate as they are delivered. Use disposable services; no paid providers or shared-DB downgrade in this command.
5. Add negative probes that inject one lint warning, type warning, Python warning and broken test to prove the gate rejects them; remove injected files afterward. Add documentation and CI-friendly sanitized artifact paths.

### Acceptance criteria

- A final clean-check run exits zero with zero emitted warnings; injected warning/failure probes each fail for the intended reason.
- Existing suites, thresholds and secret scans still execute. A skipped required service scenario cannot be labeled integrated.
- Third-party suppressions cannot be hidden behind a clean summary; unresolved exceptions remain visibly outside strict readiness.

### Verification and required evidence

Proposed tests/delivery/test_gate_contract.py plus existing REPO/OBS regressions. Run actual mise run check; retain per-step reports and negative-probe outcomes. Rebuild/image checks are later APP-BE-031 evidence, not implied here.

### Data, compatibility, rollout and peer handoff

Changes .mise.toml, tests and diagnostics policy only as needed. Do not upgrade major dependencies to clean logs. C14/A24; peer APP-FE-002 uses the same evidence vocabulary.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-002.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-002` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-003"></a>

## APP-BE-003 — Resolve migration policy and establish safe upgrade verification

Current policy update (2026-10-09): [DB-002](changes/DB-002.md) implements the explicit
owner request for two revision files and supersedes the earlier additive-only file strategy.
The completion evidence below records the earlier policy/tree. No project database rebaseline
was executed; fresh installation and legacy transition limits are documented separately.


Priority: P0  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M0  
Depends-On: APP-BE-001  
Related: DB-001  
Decisions: D01  
Owner: Codex  
Estimate: 1–2 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-003.md  


### Goal

Enable persistent features without violating the existing single-initial-migration decision or leaving installed databases unaware of new schema.

### Context: preserve and extend

B02 DB-001 explicitly consolidated the old chain into b13a0c7d2e44 with one revision file. This is a real constraint, not obsolete advice to ignore. Read the current revision rather than the historical head in B17.

### Implementation sequence

1. Record D01: recommended path is keep the consolidated initial revision immutable and permit additive revisions on one linear head for new features. Explain that editing an applied revision would not upgrade existing databases.
2. Obtain explicit owner acceptance before implementing a different migration policy. If one-file-only is retained, specify a separately versioned, tested upgrade mechanism; do not improvise stamping or destructive recreation.
3. After the decision, update migration tests/documentation to allow the approved policy while preserving fresh-install equivalence, old-head upgrade, triggers/history and schema-drift checks.
4. Create a repeatable disposable upgrade fixture with representative existing published versions, requests and media references. Verify fresh install and upgrade from the reviewed head, and test forward repair/rollback only as actually supported.
5. Require a single migration owner during parallel work and record version ordering in each task handoff.

### Acceptance criteria

- There is an explicit approved decision and a tested way to upgrade an existing installation without deleting data.
- No agent rewrites the applied initial migration, removes audit/immutability triggers, creates competing heads or uses a shared database for destructive tests.

### Verification and required evidence

Extend tests/integration/test_migrations.py under a confirmed disposable database; add an old-head upgrade fixture. Record current/head/check before/after and schema/data assertions. Never run its downgrade case on project data.

### Data, compatibility, rollout and peer handoff

D01 additive migrations approved on 2026-10-08; both applied revisions remain byte-identical. The final full gate remains blocked by the separate secret-baseline approval; no invented deployment rollback guarantee.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-003.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-003` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-004"></a>

## APP-BE-004 — Make system catalogs and permission seeds complete and idempotent

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-001, APP-BE-003  
Related: DB-001; existing step-type seeds; frontend BE-09/AUTH-03  
Decisions: None  
Owner: Codex  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-004.md  


### Goal

A migrated installation has every code-owned permission and registered operation needed by the shipped application, without over-granting people or inventing universal business defaults.

### Context: preserve and extend

B08 is a browser fixture, not the seed owner. Inspect the actual initial migration seeds, identity permission registry, step registry, template registry B20 and relevant seed tests before creating a new manifest.

### Implementation sequence

1. Inventory authoritative capability codes from route checks and services, registered handlers/versions, transforms and templates. Classify system-owned versus operator-managed data; freeze stable keys and a dependency-ordered versioned seed manifest.
2. Reuse existing migration seeding for immutable system records and add a supported reconcile/check entry point only where missing. Parameterize SQL; apply uniqueness constraints and bounded transactions.
3. Create least-privilege role templates for requester, reviewer, designer, administrator, operator and auditor as explicit installation options. Do not give operators superuser because a recovery endpoint requires it; surface the authority limitation.
4. For new features, add exact permission definitions after their contracts are approved. No wildcard or automatic grant of new privileges to all existing users. Missing/new permission reports must be actionable.
5. Verify repeat runs, concurrent invocation, partial previous seed and a changed operator-managed role. New published catalog versions append, never update prior version payloads.

### Acceptance criteria

- Each in-scope route capability has a seeded definition or a documented non-DB authority check; no duplicate permission codes.
- Repeat/concurrent seed runs converge without resetting memberships, passwords, grants or published catalogs.
- An ordinary seeded role can perform only its demonstrated actions; direct forbidden API calls still fail.

### Verification and required evidence

Extend existing seed tests; proposed tests/integration/test_application_seed.py. A01/A02: empty migrated DB, repeated run, role isolation, deleted existing target and concurrency. End with mise run check.

### Data, compatibility, rollout and peer handoff

C01 manifest handed to APP-BE-005 and APP-FE-001/011. Safe seed summaries omit credentials. New seed schema obeys D01.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-004.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-004` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-005"></a>

## APP-BE-005 — Provide supported bootstrap and realistic demo fixtures

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-004  
Related: DOCS-002; scripts/seed_frontend_browser.py; scripts/seed_studio_browser.py  
Decisions: None  
Owner: Codex  
Estimate: 3–5 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-005.md


### Goal

Start a new installation and a separately enabled demo without importing tests into production runtime or manually building every definition in Swagger.

### Context: preserve and extend

Reuse the existing purchase conformance scenario and actual application services, B08/B16/B22. Do not clone a second business-request implementation into a script.

### Implementation sequence

1. Provide documented system/install/demo modes plus check-only and dry-run. Validate environment identity and dependencies before writes. Keep credentials in a private owned file or approved secret mechanism, not logs or committed fixtures.
2. Create synthetic persona accounts and groups through identity services. Record current ref mappings internally without hard-coded encrypted refs. Register the correct client and release through the existing confidential/public policy.
3. Create/reference immutable localized form/workflow template versions using application publication paths, not raw rows bypassing invariants. Seed normal, waiting, correction, rejected and completed cases by legitimate transitions or label pure fixtures explicitly.
4. Provide a minimal second service-request template that reuses the same platform. Add assets with ownership/integrity metadata; avoid real personal data. Ready-made integration settings point only to explicitly configured test systems.
5. Record seed version and ownership marker. If an operator changed a demo template, report conflict and offer an explicit new version/default-restore flow, never silently overwrite. Write verified setup/start instructions.

### Acceptance criteria

- Fresh migration + documented bootstrap produces usable ordinary accounts and coherent catalogs; rerun has no duplicates.
- The setup does not mark a provider verified or a workflow completed without that actual result.
- Demo fixtures and credentials cannot be accidentally enabled in production; production setup does not depend on tests.conftest.

### Verification and required evidence

Proposed tests/integration/test_demo_seed.py with two consecutive runs, interrupted run repair and production refusal. Run A01/A02 and the existing HTTP core journey; mise run check.

### Data, compatibility, rollout and peer handoff

C01 and C13. APP-BE-029 later adds full destructive demo-environment reset; this task does not call mise reset or delete shared volumes.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-005.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-005` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-006"></a>

## APP-BE-006 — Exclude deleted objects consistently from live queries

Priority: P0  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-001, APP-BE-002  
Related: Existing users/roles/forms/workflows/search/report work; frontend REQ/ADMIN catalogs  
Decisions: None  
Owner: Codex  
Estimate: 3–6 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-006.md  


### Goal

Normal lists, selectors, totals and operational projections show only live eligible objects, while audit/history and explicit restore remain intact.

### Context: preserve and extend

B06/B07 identify shared query seams without asserting every route is broken. Audit both BaseCrudRepository and direct paginate_entities/service queries. Reuse current deletion and restore semantics.

### Implementation sequence

1. Create an entity/endpoint matrix: ordinary list/search/select/count/export, child collections, joins, favorites/cache, and explicit history/recycle-bin. Identify supported soft-delete marker and parent deletion rules per domain.
2. Introduce or reuse an explicit live-query policy at the persistence owner; apply identical base predicates to item and count queries before pagination. Ensure user-supplied filters cannot remove that predicate.
3. Audit selected relationships and joins, not just root queries. Preserve historical pinned versions and active-case evidence; deleted versus inactive/retired/cancelled are different domain concepts.
4. Invalidate appropriate caches and ensure queued exports reapply current authority according to their existing policy. Do not silently mutate existing audit exports into live-only reports.
5. Provide deliberate authorized deleted-object management where restore already exists. A normal list cannot offer an unrestricted include_deleted flag. Test safe detail behavior and restore conflicts.

### Acceptance criteria

- A deleted item disappears from all inventoried normal result sets and counts, including deep pages and selectors; filters cannot bypass exclusion.
- Unrelated records do not disappear when a referenced object is deleted; active case pins and retained history still resolve through their authorized historical paths.
- Deletion/restore refreshes refs and cached lists; unauthorized restore remains forbidden.

### Verification and required evidence

Proposed tests/integration/test_live_query_policy.py covering at least users, groups, forms, workflows, request types and their selectors; add route-specific cases from the matrix. A02/A05/A09. Final mise run check.

### Data, compatibility, rollout and peer handoff

Keep business lifecycle and published history unchanged. C03/C04/C09/C10 consumers must reuse this policy. No global ORM filter that accidentally hides historical execution dependencies.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-006.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-006` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-007"></a>

## APP-BE-007 — Persist self profile and typed preferences

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-003, APP-BE-004  
Related: Existing users/auth/media; frontend AUTH-04/UI-03  
Decisions: None  
Owner: Codex  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-007.md


### Goal

Users can personalize their account and workspace across sessions without private state leaking to another actor.

### Context: preserve and extend

Existing identity and private-media owners remain authoritative; do not add a competing account system. F05 documents in-memory theme preference at baseline.

### Implementation sequence

1. Freeze C02 against existing self/profile routes. Separate user-editable profile fields from verified contact/security attributes. Use a dedicated typed preference DTO and persistence adapter under the users owner.
2. Create defaults for theme mode/key, density, locale, timezone, landing key and list page size. Validate allowed values and supported calendar; do not silently accept persian while B21 only implements gregory.
3. Implement current-ref read and patch with explicit missing/null semantics and atomic group preservation. Prevent body actor_id and privilege fields. Add bounded self-only reset-to-settings-defaults if required by UI.
4. Bind avatar operations to existing private-media authorization, size/type handling and cleanup; security/account actions reuse auth APIs. Do not expose an arbitrary avatar URL fetch endpoint.
5. Add safe cache behavior and user-deactivation handling; issue fresh references after changes. Record initial localization/default rules in docs.

### Acceptance criteria

- Reload/login yields persisted appearance and locale; two users cannot read/write each other’s settings.
- Concurrent preference edits conflict explicitly or merge only disjoint approved groups without losing updates; unrelated profile fields survive.
- Invalid timezone, unsupported calendar, unknown theme and attempted privilege fields fail safely.

### Verification and required evidence

Proposed tests/integration/test_personal_preferences.py and DTO tests. A03/A22, stale writes, no-op patch, explicit null, avatar removal and unauthorized actor. mise run check.

### Data, compatibility, rollout and peer handoff

New small users-owned persistence follows D01. Handoff C02 examples to APP-FE-008; preference payload is private, excluded from diagnostic bodies.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-007.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-007` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-008"></a>

## APP-BE-008 — Normalize authorized selectors and add durable resource resolution

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-006  
Related: Existing designer selectors; workflow/connection grants; frontend API-02/STUDIO-09  
Decisions: None  
Owner: Codex  
Estimate: 3–5 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-008.md


### Goal

Every normal editor can select named authorized objects, and bookmarks/deep links can locate them after their revision changes.

### Context: preserve and extend

Reuse existing /select endpoints, C03 and B11 grants. A normalization adapter may be frontend-only where the server already exposes all needed data; do not rename every API for uniformity.

### Implementation sequence

1. Inventory required resource kinds: users, groups, client/releases, form/workflow roots and versions, step versions, request types, connections, agent versions and reusable definitions. Specify selection eligibility separately from read authorization.
2. Repair missing safe display/version metadata or selected-value lookup only where evidence requires it. Apply limits and filter permissions before count/page; preserve typed keys and locale.
3. Implement a minimal code-owned resource-link resolver: canonical stable identity remains server-side, locator is opaque, current ref/route key is returned only after the owning service authorizes the read.
4. Bind pinned-version links to the selected version, not latest; use live-current refs for mutation. Add deactivation/deletion behavior without revealing forbidden titles. Avoid browser knowledge of internal table names.
5. Provide fixture pages with selected item outside page one, changed permissions and changed revisions. Deliver adapter contract tests and examples to all consuming features.

### Acceptance criteria

- Picker search and selected summaries are complete, paginated and permission-safe; no opaque reference entry is necessary.
- A bookmark survives normal revision updates but does not confer access or silently move an execution pin.
- Forged kind/locator, deleted target, wrong actor and unsafe route key fail without an information leak.

### Verification and required evidence

Proposed tests/integration/test_resource_links.py plus selector regressions. A02/A05/A06/A07. Test current-reference refresh after mutation and context changes; mise run check.

### Data, compatibility, rollout and peer handoff

C03 is shared by favorites/notifications/calendar/default restoration. Keep domain authorization in owners, not one generic ORM resolver with broad access.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-008.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-008` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-009"></a>

## APP-BE-009 — Add private saved views and favorites without stale-reference storage

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-008  
Related: Existing personal work-item metadata; frontend FUTURE-01 only for overlapping saved-query scope  
Decisions: None  
Owner: Codex  
Estimate: 3–5 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-009.md

### Goal

Users can preserve useful list layouts/queries and return to frequently used resources without leaking data or restoring obsolete authority.

### Context: preserve and extend

Reuse C03 links, existing SearchRequest/page conventions and existing work-item personal metadata where its favorite flag already covers that target. Do not create two favorite states for the same work item.

### Implementation sequence

1. Freeze C04 scopes and schema versions for each supported list. Validate stored filters against the same domain allowlist used on execution; document unsupported fields and migration of saved query schemas.
2. Persist self-owned saved views and favorites with uniqueness constraints, per-user bounds, deterministic ordering and one default per scope. Resolve identity at write time and never persist encrypted revision refs as the only target identity.
3. Implement create/update/delete/search and explicit default selection through current refs. Preserve missing/null semantics and operation replay; never allow mass user_id reassignment.
4. On apply/read, recheck current target/list permissions and live-record policy. Do not expose unavailable target names through a favorites sidebar or saved-filter chips.
5. Define safe recovery for a removed column/filter: show a compatibility issue and preserve the original preset for deliberate repair; do not silently broaden the query. Sharing and collaborative views remain excluded.

### Acceptance criteria

- Saved views round-trip filters, sort order, columns and page size and never save page offset or raw result bodies.
- Repeated favorite creation is one favorite; revoked/deleted objects do not appear in normal favorite lists.
- Concurrent default changes yield one default, and actors cannot modify another user’s state.

### Verification and required evidence

Proposed tests/integration/test_saved_views_favorites.py; A03/A05. Include filter injection, unavailable target, renamed target, schema drift, duplicate creation and concurrent default changes. mise run check.

### Data, compatibility, rollout and peer handoff

C04 → APP-FE-009. Private free-text filters must not enter logs, analytics or public seed data. New schema obeys D01.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-009.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.


Completion evidence (2026-10-08): `APP-BE-009` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-010"></a>

## APP-BE-010 — Store only the small per-user multilingual help-state table

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-003, APP-BE-004  
Related: Existing localization; frontend UI-03  
Decisions: None  
Owner: Codex  
Estimate: 1–2 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-010.md


### Goal

Allow the frontend to remember which help a user actually opened or dismissed while keeping help content and presentation simple.

### Context: preserve and extend

C05; translations and help list stay frontend-owned. This is not a CMS, feature-flag engine or behavior-tracking product.

### Implementation sequence

1. Agree help_key/revision/locale metadata with APP-FE-010. Add a compact release metadata manifest for allowed keys; generate/validate it as part of a paired release rather than hand-copy translations.
2. Implement one users-owned state table with uniqueness, bounded key lengths, server timestamps and self-derived ownership. Provide seen, dismiss, read and deliberate self reset contracts.
3. Make duplicate seen/dismiss calls safe and preserve first-seen time. New revision or locale is independently reviewable; do not infer that opening English help proves Farsi was read.
4. Keep unrecognized/stale manifest keys bounded and return a safe compatibility response. The help-state service must not authorize access to a business screen.
5. Test failure behavior so unavailable seen-state persistence does not prevent the static help from rendering; frontend reports an unsaved preference, not a business failure.

### Acceptance criteria

- State is recorded only after a real user open/acknowledgment action, not list retrieval.
- Two users and two locales remain isolated; reset affects help state only.
- No help HTML/text, form values, browsing duration or arbitrary event payload is persisted.

### Verification and required evidence

Proposed tests/integration/test_help_state.py and release-manifest contract tests. A03/A04; repeat requests, updated revision, invalid keys, self-reset and outsider denial. mise run check.

### Data, compatibility, rollout and peer handoff

C05 → APP-FE-010. Initial small table only. Help content can ship independently as frontend code but persistence requires this verified contract.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-010.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-010` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-011"></a>

## APP-BE-011 — Expose truthful setup/readiness checks with safe repair destinations

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-004, APP-BE-005, APP-BE-008  
Related: Existing health/readiness and operations docs  
Decisions: None  
Owner: Codex  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-011.md

### Goal

An administrator can identify why an installation cannot run a demonstration without reading environment files or interpreting raw service errors.

### Context: preserve and extend

Reuse existing health dependencies, client/release state and registered catalogs. A new checklist is a projection over existing facts, not another scheduler or provisioning service.

### Implementation sequence

1. Define C06 checklist: schema head, system seeds, required role/capability mappings, client release, enabled templates, private storage, scheduler/queues and required configured connections. Separate required checks from optional features.
2. Implement bounded read-only checks with ready/blocked/unknown/not_applicable, checked_at and localized message keys. Protect detailed setup visibility; do not reveal DSNs, secrets, internal hosts or user lists to requesters.
3. Use verified existing worker heartbeat evidence when available. If no execution probe ran, say unknown—not ready because RabbitMQ accepted a connection. Active probe commands require explicit operator action.
4. Return allowlisted repair routes to owning screens and safe context; never auto-create or grant/publish on GET. Distinguish development demo readiness from production commitments.
5. Add fixtures for a fresh empty installation, seeded installation, one missing dependency and a timeout. Give the UI a refresh rule and last-checked label.

### Acceptance criteria

- Every blocked check names a safe reason and actionable next destination or explicit operator requirement.
- Unknown dependencies cannot produce a green overall readiness result for a required capability.
- No read changes configuration or performs an unapproved paid/live provider call.

### Verification and required evidence

Proposed tests/integration/test_setup_readiness.py plus dependency timeout unit tests. A06; authorized admin, outsider, partial outage and no-side-effect reads. mise run check.

### Data, compatibility, rollout and peer handoff

C06 → APP-FE-011. Setup projection can use existing permission checks until a reviewed new capability is seeded; never assume processes.recover grants superuser powers.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-011.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.


Completion evidence (2026-10-08): `APP-BE-011` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-012"></a>

## APP-BE-012 — Add definition dependency readiness and guided repair metadata

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M2  
Depends-On: APP-BE-008, APP-BE-019  
Related: Existing designer/library dependencies and workflow validators; frontend STUDIO-09  
Decisions: None  
Owner: Codex  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-012.md

### Goal

Designers can see missing or incompatible forms, versions, handlers, candidates, client capabilities and connections before attempting publication.

### Context: preserve and extend

B09–B11 and existing library dependency/where-used tools. Do not implement a second graph validator. Call the authoritative validation pipeline and enrich safe diagnostics.

### Implementation sequence

1. Enumerate readiness categories from the actual graph/form dependency models and emitted errors. Map exact existing machine codes to logical repair targets and field/node pointers.
2. Add missing safe metadata through C06 only where existing tools cannot supply it. Include exact pinned references/checksums and distinguish missing, inaccessible, retired for new use and incompatible.
3. Keep normal user eligibility separate from author publication readiness. A designer’s access does not authorize a requester or service principal.
4. Return a bounded repair plan explaining which current record must be edited; dependent edits stay explicit with refreshed refs and revalidation. Never silently replace a published dependency with latest.
5. Support returning from the repair screen to the same selected node and rerunning checks, including changed/granted/revoked dependencies.

### Acceptance criteria

- A failing publication has node/field-level explanations and a usable authorized repair destination.
- An inaccessible dependency cannot be enumerated by title or content through diagnostics.
- Repair suggestions preserve exact version intent and do not grant/publish automatically.

### Verification and required evidence

Extend graph/library validation tests; proposed tests/integration/test_dependency_readiness.py. A06/A11/A12 with missing form, incompatible port, unavailable connection, empty candidate set and stale repair plan. mise run check.

### Data, compatibility, rollout and peer handoff

C06/C11 → APP-FE-011/021/027. Pure projection where possible; no duplicate persistence of dependency state.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-012.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.


Completion evidence (2026-10-08): `APP-BE-012` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-013"></a>

## APP-BE-013 — Specify the complete notification event map and compatibility design

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-001  
Related: Existing notifications templates/delivery; frontend OPS-01  
Decisions: None  
Owner: Codex  
Estimate: 1–2 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-013.md  


### Goal

Every notification has a deliberate trigger, audience, channel, template, deep-link target and dedupe rule, including non-workflow application events.

### Context: preserve and extend

B18–B20: current DTO and route mapper require request/process context; template registry is code-owned. Reuse this domain and distinguish current event codes from proposed map meanings.

### Implementation sequence

1. For MAP-01–MAP-14 in C07, bind each row to the exact current domain event or command hook. Mark unavailable source events as producer subtasks, not fictional implemented names.
2. Define recipient resolution at commit/delivery/open, optional versus mandatory notices, en/fa templates, bounded variables and dedupe/cancellation identities. Avoid notification-per-poll behavior.
3. Choose the additive unified-inbox projection needed for calendar/report/support events, preserving old case-only payload expectations. Specify migration, serializers, route permissions and frontend feature negotiation.
4. Create a machine-checkable map/translation manifest and one acceptance fixture per map row. Reuse existing report completion and account security hooks instead of duplicating them.
5. Freeze channel scope: in-app plus one supported real test channel; paid SMS/push providers are outside the initial pack. Record template ownership and retention behavior.

### Acceptance criteria

- All included rows have exact trigger ownership, audience, target and tests, or explicit blocked producer work.
- No fake request/process is created to carry a calendar/support notification.
- The old notification contract remains documented and compatible during rollout.

### Verification and required evidence

Proposed tests/delivery/test_notification_map.py checks uniqueness, allowed routes, template keys, en/fa coverage, dedupe fields and producer references. A07. mise run check.

### Data, compatibility, rollout and peer handoff

C07 is the notification map the user requested, not a promise all mapped events already exist. Handoff to APP-BE-014 and APP-FE-012.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-013.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-013` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-014"></a>

## APP-BE-014 — Implement unified notifications and transactional event delivery

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M3  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-008, APP-BE-013  
Related: Existing notifications/outbox/templates; frontend OPS-01  
Decisions: None  
Owner: Codex  
Estimate: 4–7 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-014.md

### Goal

Deliver coherent, localized in-app notifications for the agreed map and open the correct authorized current resource.

### Context: preserve and extend

Extend B18–B20 and existing delivery workers. Legacy search/report behavior must not be relabeled as queued export; B19 report currently delegates to search.

### Implementation sequence

1. Implement the frozen C07 compatibility design in the existing domain. Migrate existing rows without losing delivery/read state; introduce discriminated non-case targets without corrupting legacy required refs.
2. Stage notification intent in the same transaction as each successful domain event; fan out in bounded chunks using the existing outbox/task infrastructure. Enforce unique event/recipient/template or equivalent dedupe constraints.
3. Render en/fa templates with allowlisted safe variables. Honor optional preferences without suppressing required task/approval notices. Recheck current recipient authorization before sending sensitive details.
4. Implement unified inbox search/detail/read and accurate unread totals with existing pagination/current-ref semantics. Resolve deep-link current refs at open; mark-read never performs a workflow action.
5. Handle stale reminders, deleted targets, duplicate worker delivery, provider uncertainty and retention redaction. Coalesce incident-notification failures to avoid feedback loops; do not generate unbounded recipient sets.

### Acceptance criteria

- MAP fixtures emit one intended notice per valid recipient and occurrence, including correction rounds and changed assignments.
- Old clients continue receiving valid old case shapes; new inbox shows non-case events without fabricated context.
- Read/unread counts, locale, current deep links and access revocation are correct; actual worker and selected channel evidence is retained.

### Verification and required evidence

Proposed tests/integration/test_unified_notifications.py plus actual notification worker tests. A07/A19/A20. Split into .1 schema/projection, .2 event production, .3 worker/deep-link acceptance before parallel implementation; each slice preserves compatibility. mise run check.

### Data, compatibility, rollout and peer handoff

C07 → APP-FE-012. Calendar reminder source comes later APP-BE-017 but map and inbox must accept its typed event. No parallel delivery engine.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-014.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.


Completion evidence (2026-10-08): `APP-BE-014` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-015"></a>

## APP-BE-015 — Record supportable failures and expose a safe incident projection

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M1  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-008  
Related: OBS-001/002; existing process/task failure evidence and recovery  
Decisions: None  
Owner: Codex  
Estimate: 3–5 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-015.md

### Goal

Users receive a support reference and authorized operators can inspect recurring technical failures without recording confidential payloads.

### Context: preserve and extend

Reuse existing request/trace correlation, task attempts, process timeline and error catalog. Persist a support record/projection only for gaps; do not duplicate all logs or count every validation error as an incident.

### Implementation sequence

1. Freeze C08 classification and a bounded allowlist of recorded fields. Define episode/fingerprint semantics, occurrence count, retention and authorized search/detail/acknowledge/resolve actions.
2. Record a technical failure after the business transaction rolls back using an independent session/transaction. Never commit the failed business session to save diagnostics. Link existing attempts instead of copying their private snapshots.
3. Add public support_ref or use existing correlation response metadata compatibly. For client intake, allow only build/screen/error codes and a correlation identifier with size/rate limits; no arbitrary stack trace or message body.
4. Make the recorder non-recursive; use sanitized log/metric fallback when DB is down and record that durability could not be established. Do not change a successful business response into failure because support storage failed.
5. Expose permission-protected incident lists and audited acknowledgment/resolution. Repeated errors increment a bounded episode rather than infinite notifications; a resolved incident’s recurrence follows explicit tested episode rules.

### Acceptance criteria

- A real failed transaction leaves no business mutation but yields a correlated failure record when the store is available.
- Credentials, private form data, provider payloads, prompts and stack text are absent from API and diagnostic artifacts.
- Recorder outage cannot recurse or cause duplicate business effects; the UI never claims a persisted incident without evidence.

### Verification and required evidence

Proposed tests/integration/test_support_failures.py and recorder fallback unit tests. A20, duplicate episode, outsider, server rollback, client ingest abuse and sink outage; mise run check.

### Data, compatibility, rollout and peer handoff

C08 → APP-FE-013/032. Reuse notification map MAP-13 with bounded escalation. New retention defaults require an operator-visible policy; no indefinite raw-event archive.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-015.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Dependency update (2026-10-08): prerequisites and the shared gate are satisfied. READY records eligibility for remaining work or task-specific acceptance review; this through-014 closure does not mark this separate task DONE.

Completion evidence (2026-10-08): the complete fourteen-stage gate passed with exactly D07. See [through-020-verification.md](delivery/through-020-verification.md) and [through-020-gate.json](delivery/through-020-gate.json). Required service profiles have no skips. Task change record and C08/C09/C10/C11 handoff match actual implemented ownership and tested behavior. Frontend, deployment and later task acceptance remain separate.

<a id="app-be-016"></a>

## APP-BE-016 — Add a workflow-aware calendar with correct time and ownership semantics

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M4  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-007, APP-BE-008  
Related: Existing work items/process due data and localization  
Decisions: None  
Owner: Codex  
Estimate: 4–7 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-016.md

### Goal

Provide personal and explicitly authorized team events alongside derived workflow deadlines through a bounded calendar API.

### Context: preserve and extend

C09 and B21; timezone display is not a new workflow lifecycle. Inspect actual due/deadline fields and reuse them rather than adding another source of truth.

### Implementation sequence

1. Define separate personal/team event records and read-only workflow-derived event projections. Assign a domain owner for calendar while reusing users/groups/media/time infrastructure. Freeze half-open range/date/time DTOs.
2. Implement bounded search and explicit CRUD with server-derived ownership, current refs and correct interval-overlap predicates. Validate event end after start, all-day date types, IANA zones and DST ambiguities.
3. Map only actual workflow due dates; suppress nonexistent deadlines rather than inventing them. Preserve stable source links through revision changes and remove obsolete derived entries as the domain state changes.
4. Define permissible team visibility and membership revocation; return no secret titles through aggregate range results. API search/count must apply ownership and live-record predicates before paging.
5. Keep recurring events, calendar invitations, provider synchronization, holiday calculations and Jalali conversion separate. Provide Gregorian en/fa fixtures and an explicit unsupported-calendar error until D03 scope is approved.

### Acceptance criteria

- Month/week/agenda ranges contain exactly overlapping authorized events, including multi-day and all-day cases.
- Editing a personal event does not edit a work-item deadline; workflow source changes appear without duplicate derived records.
- Timezone and date-only values round-trip and revoked members cannot see team events.

### Verification and required evidence

Proposed tests/integration/test_calendar_events.py plus pure time-boundary tests. A08: range endpoints, DST gap/fold, UTC+04, leap day, all-day exclusive end, deleted source and stale write. mise run check.

### Data, compatibility, rollout and peer handoff

C09 → APP-FE-014. Split .1 date/ownership contracts, .2 persistence/derived projection, .3 service integration. New tables require D01; Jalali beyond Gregorian is D03 conditional scope.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-016.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Dependency update (2026-10-08): prerequisites and the shared gate are satisfied. READY records eligibility for remaining work or task-specific acceptance review; this through-014 closure does not mark this separate task DONE.

Completion evidence (2026-10-08): the complete fourteen-stage gate passed with exactly D07. See [through-020-verification.md](delivery/through-020-verification.md) and [through-020-gate.json](delivery/through-020-gate.json). Required service profiles have no skips. Task change record and C08/C09/C10/C11 handoff match actual implemented ownership and tested behavior. Frontend, deployment and later task acceptance remain separate.

<a id="app-be-017"></a>

## APP-BE-017 — Deliver calendar and work reminders through existing scheduling

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M4  
Depends-On: APP-BE-014, APP-BE-016  
Related: Existing Celery scheduler/outbox/timer recovery  
Decisions: None  
Owner: Codex  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-017.md

### Goal

Reminders arrive once for the current event/deadline and disappear when their source is edited or cancelled.

### Context: preserve and extend

Use existing task scheduling, durable outbox and C07 MAP-10/11. Do not create an in-process timer loop or second scheduler. Existing SLA/escalation semantics must be verified before use.

### Implementation sequence

1. Add explicit one-off reminder configuration to supported event types with bounded count and offset. Convert local intent using C09; assign durable reminder identity from source revision and occurrence.
2. Stage create/change/cancel in the source transaction. Invalidate old pending work without reusing old attempt identities, and recheck source/recipient eligibility at dispatch.
3. Invoke the unified notification pipeline, keeping provider/network work outside the source transaction. Reuse queue separation and backoff; distinguish a missed notification from a missed business deadline.
4. Expose safe delivery state only to authorized users. Use observed lag metrics and a support incident threshold, not a new unbounded notification for each retry.
5. Test scheduler restart, broker outage, concurrent event edit, cancellation after enqueue and duplicate delivery. Define late reminder policy explicitly (deliver once if still relevant; otherwise expire).

### Acceptance criteria

- An event edit cancels the old reminder and schedules the new one without duplicate notification.
- A cancelled/completed/inaccessible source cannot generate an obsolete reminder.
- Restart and broker recovery preserve delivery identity and current eligibility.

### Verification and required evidence

Proposed tests/integration/test_calendar_reminders.py plus a real Celery/scheduler case. A07/A08/A21. Database-only publication mocks do not satisfy final delivery acceptance; mise run check plus actual services.

### Data, compatibility, rollout and peer handoff

C09/C07 → APP-FE-014/012. Reminder timers do not create workflow transitions or reschedule work without an existing authorized command.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-017.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): the complete fourteen-stage gate passed with exactly D07. See [through-020-verification.md](delivery/through-020-verification.md) and [through-020-gate.json](delivery/through-020-gate.json). Required service profiles have no skips. Task change record and C08/C09/C10/C11 handoff match actual implemented ownership and tested behavior. Frontend, deployment and later task acceptance remain separate.

<a id="app-be-018"></a>

## APP-BE-018 — Provide authorized metric definitions and chart data

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M4  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-006  
Related: Existing reporting, Polars/openpyxl and operational telemetry  
Decisions: None  
Owner: Codex  
Estimate: 3–5 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-018.md

Earlier preparation evidence: docs/delivery/wave-four-verification.md. The shared gate and exact baseline approval are now resolved; see the dependency update below.

### Goal

Give the UI real chart-ready business metrics that agree with lists and respect authorization, instead of mock numbers or arbitrary query services.

### Context: preserve and extend

Reuse reporting definitions/query policies, existing process/work-item timestamps and metric aggregation where applicable. Operational telemetry is not automatically a user-authorized reporting API.

### Implementation sequence

1. Freeze C10’s initial metric dictionary: population, timestamps, status/outcome mapping, dimensions, units, timezone bucket rules, null/unknown and excluded records. Avoid approved/rejected inference from generic terminal state.
2. Implement typed bounded metric queries through existing data access, with allowed dimensions/filters and source-specific authorization. No browser SQL or arbitrary chart options.
3. Return domain-neutral buckets/series, generated_at/as_of and a drill-down descriptor validated against the corresponding list query. Do not show a partial first page as a global aggregate.
4. Apply live-query rules for operational charts; preserve explicitly named historical audit metrics under proper authority. Cache only with actor/permission/filter isolation and documented invalidation.
5. Use controlled fixtures and inspect query plans for representative distributions before adding indexes. Keep exports on reporting infrastructure; distinguish unavailable service from empty/zero data.

### Acceptance criteria

- Fixture metric totals match the authorized drill-down across date boundaries and soft deletes.
- Restricted users cannot infer another group’s work through counts, filters or cached series.
- Monetary units remain explicit; mixed currencies are not silently added; unknown execution outcomes remain unknown.

### Verification and required evidence

Proposed tests/integration/test_business_analytics.py plus metric-spec tests. A02/A09; exact counts, DST bucket, cancelled state, forbidden dimension, cache isolation and query bound. mise run check.

### Data, compatibility, rollout and peer handoff

C10 → APP-FE-015. Initial charts are a small registered catalog, not a BI designer or new warehouse.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-018.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Dependency update (2026-10-08): prerequisites and the shared gate are satisfied. READY records eligibility for remaining work or task-specific acceptance review; this through-014 closure does not mark this separate task DONE.

Completion evidence (2026-10-08): the complete fourteen-stage gate passed with exactly D07. See [through-020-verification.md](delivery/through-020-verification.md) and [through-020-gate.json](delivery/through-020-gate.json). Required service profiles have no skips. Task change record and C08/C09/C10/C11 handoff match actual implemented ownership and tested behavior. Frontend, deployment and later task acceptance remain separate.

<a id="app-be-019"></a>

## APP-BE-019 — Complete typed authoring metadata instead of generic JSON contracts

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M2  
Depends-On: APP-BE-001, APP-BE-004  
Related: Existing designer API, step registry, forms/runtime-preview; frontend BE-04/STUDIO-07  
Decisions: None  
Owner: Codex  
Estimate: 3–6 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-019.md


### Goal

Provide authoritative versioned configuration metadata for purpose-built frontend inspectors across every shipped node/complex field.

### Context: preserve and extend

B10–B13, F07/F08/F10. Inventory existing registry schemas, designer selectors/completion and published-form metadata before adding fields. Keep backend config and render data separate.

### Implementation sequence

1. Build a contract matrix for every registered handler/version and the twenty supported form primitive kinds: input/output, config, conditional fields, enums, references, outcomes, validation and localized help.
2. Replace avoidable Any/untyped JSON DTO fields with explicit nested BaseDTO schemas when semantics are fixed. Keep genuinely extensible documents under a versioned validated dialect; preserve legacy published snapshots.
3. Add missing safe inspector metadata: selector kind and scope, secret-reference field classification, config discriminators, required capabilities and field-level diagnostic pointers. Do not return credentials or backend-defined HTML.
4. Expose expression/schema completion from authoritative prior outputs, not all process data. Preview runs bounded pure evaluation with synthetic data, not actual workflow execution or arbitrary code.
5. Generate OpenAPI/examples and the frontend metadata fixture from the same source, including negative unions and omitted/null cases. Freeze the C11 handoff per handler to allow incremental UI delivery.

### Acceptance criteria

- Every shipped node and form kind is classified; normal configuration no longer requires a frontend to infer unknown JSON structures.
- Existing graphs and pinned versions still deserialize/validate; additive metadata does not change their checksums unless intentionally versioned.
- Unknown or incompatible config has safe typed diagnostics and no secret/hidden-field leakage.

### Verification and required evidence

Proposed tests/delivery/test_authoring_metadata.py plus registry/designer/API schema tests. A10/A11/A12. Split .1 inventory, .2 metadata gaps, .3 compatibility fixtures. mise run check.

### Data, compatibility, rollout and peer handoff

C11 → APP-FE-016–026; serves APP-BE-012. No replacement execution engine or form-package-v2 rollout is authorized.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-019.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Completion evidence (2026-10-08): `APP-BE-019` passed the complete thirteen-stage gate; see [through-014-verification.md](delivery/through-014-verification.md) and [through-014-gate.json](delivery/through-014-gate.json). D01, D07 and the exact ten-entry baseline review are owner-approved. VERIFIED_WITH_EXCEPTION denotes the two exact SDK deprecations; frontend/deployment acceptance and later producer tasks remain separate.

<a id="app-be-020"></a>

## APP-BE-020 — Close runtime form and complex-value conformance gaps

Priority: P1  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M2  
Depends-On: APP-BE-006, APP-BE-019  
Related: Existing frontend BE-01–05/BE-08; existing form conformance and work-item patch fixes  
Decisions: None  
Owner: Codex  
Estimate: 3–5 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-020.md

### Goal

Ensure visual editors and all supported runtime controls preserve canonical data, permissions, nested rows and mutation references.

### Context: preserve and extend

The earlier projection, hidden-field preservation and runtime-document work is already implemented according to F02. Reuse it; this is additional conformance and repairs found by the full visual coverage matrix.

### Implementation sequence

1. For each C11 form primitive, enumerate create/read/edit/summary/print/correction behavior and actual supported options. Include render behavior, localization and active-version pins.
2. Replay numeric strings, false/zero/empty/null/missing values, typed option keys, nested repeaters and private attachments. Do not normalize money through floating-point arithmetic.
3. Inspect all mutation/validation/error paths for hidden data or schema/default leakage; retain writable patch semantics and current refs for submission/work-item/rows.
4. Fix only uncovered server semantics needed by visual controls. Unsupported form dialects or capabilities fail closed with a usable compatibility reason; no silent lossy fallback.
5. Update fixtures with the frontend consumer and preserve API contracts; annotate any true breaking gap and migration rather than broad refactoring.

### Acceptance criteria

- Every supported control has a backend canonical-value fixture shared with preview/runtime, including correction before/after data.
- Hidden data survives permitted edits without being returned; row identities survive reorder and stale writes fail safely.
- No previously fixed BE-01/02/03 behavior regresses while editors become richer.

### Verification and required evidence

Extend existing form/work-item tests and proposed tests/integration/test_visual_runtime_conformance.py. A10/A14/A15/A19, include property/row-based table cases. mise run check.

### Data, compatibility, rollout and peer handoff

C11 and existing bpms.runtime/1 remain the authority. No new rendering dialect without an explicit compatibility task.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-020.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Dependency update (2026-10-08): prerequisites and the shared gate are satisfied. READY records eligibility for remaining work or task-specific acceptance review; this through-014 closure does not mark this separate task DONE.

Completion evidence (2026-10-08): the complete fourteen-stage gate passed with exactly D07. See [through-020-verification.md](delivery/through-020-verification.md) and [through-020-gate.json](delivery/through-020-gate.json). Required service profiles have no skips. Task change record and C08/C09/C10/C11 handoff match actual implemented ownership and tested behavior. Frontend, deployment and later task acceptance remain separate.

<a id="app-be-021"></a>

## APP-BE-021 — Enforce required human approval before protected business effects

Priority: P0  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M3  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-019  
Related: BPMS-018 design/implementation; current workflow validation and work-item completion  
Decisions: None  
Owner: Codex  
Estimate: 4–7 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Make the product’s human-supervision requirement true in publication and execution, including normal AI paths, corrections and parallel/subprocess routes.

### Context: preserve and extend

Current completion work (2026-10-09): the concrete sandbox.order.create/1 human-action/payload-hash policy is prepared in docs/delivery/protected-effect-policy.md and awaits the exact owner product decision required by this task. No protected effect or authority change has been enabled.

B11/B15 explicitly establish the gap: next exists and at least one review target is human, but stricter pilot normal-path policy is not universally enforced. Extend existing validators and work-item evidence.

### Implementation sequence

1. Define the initial protected-effect policy explicitly: which registered operations require which declared human approval action and which canonical input revision that approval covers. Approval of a lookup tool is a different permission/event.
2. Add publication validation over every selectable normal/review/default/conditional route and supported subprocess interface. Reject bypasses and ambiguous unsupported policy composition instead of guessing graph dominance from visual layout.
3. At protected execution, verify the required eligible human decision evidence matches the immutable policy/pin and relevant data revision. Keep the approval check and dispatch authorization fence atomic.
4. Invalidate approval after correction of relevant inputs; define safe reapproval for rejected/returned branches without fabricating lifecycle actions. Do not accept model output or a generic arbitrary human task as approval.
5. Test parallel branch bypass, stale completion, replay, direct command invocation, version successor and cancelled process. Add localized diagnostics usable in the node inspector.

### Acceptance criteria

- An AI normal path or alternate review path cannot dispatch a protected operation without actual required human approval.
- Changing approval-relevant inputs prevents reuse of the prior approval; replay of the same committed action stays idempotent.
- Existing unrestricted workflows retain their declared semantics; protected policy changes are versioned and not silently imposed on old pins.

### Verification and required evidence

Proposed tests/integration/test_required_human_approval.py plus graph tests. A16/A17/A18, adversarial graph fixtures and race tests on PostgreSQL. Split .1 policy/schema, .2 publication, .3 dispatch evidence. mise run check.

### Data, compatibility, rollout and peer handoff

C12 → APP-FE-022/025/026. Product decision on exact protected-operation/approval mapping is part of contract freeze; do not add self-approval/quorum rules without a business decision.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-021.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Dependency update (2026-10-08): prerequisites and the shared gate are satisfied. READY records eligibility for remaining work or task-specific acceptance review; this through-014 closure does not mark this separate task DONE.

<a id="app-be-022"></a>

## APP-BE-022 — Define governed business operations and execution-principal policy

Priority: P1  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M3  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-019, APP-BE-021  
Related: Existing extension registration/integration grants; B12–B14  
Decisions: D04  
Owner: TBD  
Estimate: 3–6 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Create a typed, versioned catalog of business effects and their authorized execution identity without converting the workflow platform into arbitrary HTTP scripting.

### Context: preserve and extend

Reuse trusted step extensions and ConnectionService, existing grant/secret pinning and outbox. Existing publisher-derived actor is a real contract and cannot be replaced by implicit superuser.

### Implementation sequence

1. Resolve D04 with an explicit pilot policy. Recommended least-change pilot: retain publisher-bound authority with dedicated non-superuser demo publisher and fail-closed offboarding; a persistent service-principal feature needs separate approved scope and tests.
2. Define operation versions, typed request/result, endpoint_key, authentication, allowed connection kind, approval requirement, idempotency key, deadline/retry and reconciliation/compensation capability. Seed only registered implementations.
3. Ensure code-owned endpoints and secrets remain outside authored graph JSON. Prevent user-directed arbitrary URLs, redirect credential leakage and implicit provider SDK retries.
4. Expose safe operation metadata and selectable connections to inspectors. Distinguish configured, secret-resolvable, live-verified and executable states.
5. Test publisher deactivation/grant revocation/connection rotation during waiting and before dispatch. Preserve old pins and record supportable failure rather than silently substituting a credential or principal.

### Acceptance criteria

- Only registered compatible operations and authorized pinned connections can be published and executed.
- Offboarding/rotation has explicit, tested outcomes; no fallback to admin credentials or latest connection.
- The UI can explain operation inputs, outputs and side-effect/retry properties without handling secrets.

### Verification and required evidence

Proposed tests/integration/test_business_operation_contracts.py and provider boundary tests. A06/A11/A16/A18; role revocation, secret-version mismatch and unsupported handler. mise run check.

### Data, compatibility, rollout and peer handoff

C11/C12 → APP-FE-025/030. D04 is an explicit product/security authority decision; no new service identity is assumed.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-022.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

<a id="app-be-023"></a>

## APP-BE-023 — Implement one real HTTP demo business operation with a receipt

Priority: P1  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M3  
Depends-On: APP-BE-022, APP-BE-015  
Related: Existing trusted extensions/provider/outbox; connection.status retained as diagnostic  
Decisions: D02 for named-provider acceptance only  
Owner: TBD  
Estimate: 4–7 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Demonstrate actual connected-system work rather than a status check or frontend fixture returning success.

### Context: preserve and extend

B12/B13 identify the current built-in status operation. Use a separate explicitly labeled HTTP sandbox order service and the governed operation contract; named vendor evidence is a distinct D02 gate.

### Implementation sequence

1. Implement a deterministic separate sandbox service with an authenticated create-order operation, durable idempotency key, stable receipt and lookup-by-operation-key. Keep it isolated from production endpoints and clearly label its role.
2. Implement a trusted backend adapter that sends typed approved inputs, bounds timeouts and payloads, handles schema-valid output and records receipt/operation identity. Network calls do not hold a mutable DB transaction/session across unrelated work.
3. Stage dispatch only after required approval and commit; preserve existing outbox worker/task identities. Register result mappings that expose a business receipt rather than merely HTTP status.
4. Provide sandbox fault controls: validation rejection, transient pre-dispatch failure, delayed reply and effect accepted with acknowledgment lost. Fault controls must not be callable in production.
5. When a named external vendor sandbox is chosen, implement/verify its actual auth and receipt behavior as the same operation family or a new version, recording separate evidence and cost/access approval. Do not present the local sandbox as vendor integration.

### Acceptance criteria

- The browser-triggered workflow sends an actual HTTP request through the worker to the separate sandbox and shows an inspectable receipt.
- Provider results are bounded/validated/redacted and queued does not mean completed.
- No live production purchase or paid provider action is triggered by ordinary checks.

### Verification and required evidence

Proposed tests/integration/test_demo_business_connector.py plus disposable sandbox contract tests; actual worker required for A18/A19. Split .1 sandbox, .2 adapter, .3 full effect evidence. mise run check plus explicit real-service run.

### Data, compatibility, rollout and peer handoff

C12 → APP-FE-025/026/030/037. D02 named provider choice is not required to build a truthful local connected-system demo, but blocks claims of vendor-certified integration.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-023.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

<a id="app-be-024"></a>

## APP-BE-024 — Handle unknown outcomes, reconciliation and supported compensation

Priority: P0  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M3  
Depends-On: APP-BE-023  
Related: Existing retries/recovery/compensation; B17  
Decisions: None  
Owner: TBD  
Estimate: 3–6 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Lost acknowledgments and retries do not create duplicate business effects, and operators can resolve supported incidents deliberately.

### Context: preserve and extend

Existing recovery rejects ambiguous force-advance and guessed multi-position branches [B17]. Extend actual operation evidence; do not create a generic retry-everything command.

### Implementation sequence

1. Persist logical operation identity and dispatch/receipt evidence at existing attempt boundaries. Distinguish confirmed pre-dispatch failure from unknown-after-dispatch result without inventing new process status strings.
2. For the sandbox adapter, reconcile by the same idempotency key and return the original receipt. Freeze payload hashes; a reused key with different input conflicts. Do not assume provider timeouts imply rollback.
3. Add an authorized reconciliation command or reuse existing one, with reason and current refs. Record action/result in existing process timeline and support projection.
4. Implement compensation only for an explicitly registered reversible sandbox operation, with its own operation identity and receipt. Show unsupported/manual compensation honestly; DB rollback never reverses external effects.
5. Exercise crash points: before commit, after outbox commit, after dispatch, after provider effect, before local success record, during reconciliation and during compensation.

### Acceptance criteria

- Accepted-effect/lost-reply replay results in one logical order and one stable receipt.
- Unsafe retries are unavailable until reconciliation resolves uncertainty; changed-payload replay is rejected.
- Compensation is deliberate, auditable and never labeled successful without provider evidence.

### Verification and required evidence

Extend existing recovery/outbox/compensation tests plus proposed tests/integration/test_operation_reconciliation.py. A18/A20/A21 with real sandbox and worker fault cases; mise run check.

### Data, compatibility, rollout and peer handoff

C12 → APP-FE-026/032/037. Preserve existing operation-specific keys and process lifecycle; only add bounded compatible DTOs where necessary.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-024.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

<a id="app-be-025"></a>

## APP-BE-025 — Verify supervised AI behavior and provide an explicit evaluation path

Priority: P1  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M3  
Depends-On: APP-BE-021, APP-BE-022  
Related: Existing BPMS-018 agents/budgets/tool approvals/evaluation CLI  
Decisions: D02 for live-AI evaluation  
Owner: TBD  
Estimate: 3–6 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Make AI assistance useful and inspectable while preserving human authority, data boundaries and honest demo labeling.

### Context: preserve and extend

B15 documents typed agents, reservations, unknown usage, read-only tool approval, one-request dispatch and outstanding live evaluation. Reuse those implementations; do not build a second agent framework.

### Implementation sequence

1. Audit the existing agent publication/dispatch/output/tool-approval path against the current lock. Record which checks are fake-backed, local deterministic and live provider evidence.
2. Create representative labeled en/fa recommendation cases with acceptable output schema, abstention/review behavior and misuse/prompt-injection cases from untrusted attachments/text. Bound data disclosure and approved tool access.
3. Provide an explicitly labeled deterministic AI simulator for repeatable checks if existing fixtures cannot serve the demo. It is never proof of model quality, provider credentials or calibrated confidence.
4. Add an explicit opt-in live evaluation workflow using an approved existing agent/connection, quote cap and permitted test data. Capture aggregate quality, invalid output, latency, request/token/spend reservations and unknown usage without raw private prompts in logs.
5. Test human wait versus compute deadline, denied/expired approval, cancelled process, changed connection and budget exhaustion. Fix uncovered gaps; never extend approval authority based on high confidence.

### Acceptance criteria

- Both normal/review outputs remain blocked by required human approval for protected effects.
- AI evidence screens can show allowed inputs, recommendation, model/agent identity and human outcome without secret or unapproved trace content.
- Live evaluation is either actually recorded with approval or explicitly blocked; deterministic demo is labeled and no business-accuracy claim is invented.

### Verification and required evidence

Extend existing AI deterministic/integration/evaluation tests; proposed tests/delivery/test_supervised_ai_profile.py. A16/A22/A26. mise run check never makes paid calls; approved live evaluation is separate mandatory evidence for a live-AI claim.

### Data, compatibility, rollout and peer handoff

C12 → APP-FE-025/026/030. AI cost, provider and test-data approvals are D02; raw prompts/responses need a separate retention design before storage.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-025.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

<a id="app-be-026"></a>

## APP-BE-026 — Support immutable template baselines and safe return-to-default

Priority: P0  
Status: DONE  
Verification: VERIFIED_WITH_EXCEPTION  
Area: backend / M2  
Depends-On: APP-BE-003, APP-BE-004, APP-BE-008, APP-BE-012  
Related: Existing library template/version tools, workspace promotion; frontend STUDIO-09  
Decisions: None  
Owner: Codex  
Estimate: 4–7 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-026.md

### Goal

Restore a workflow’s known default safely without overwriting active executions, secrets, grants or published versions.

### Context: preserve and extend

Current completion work (2026-10-09): exact baseline preview/apply, durable command replay and layout reset are implemented. The complete fifteen-stage gate passes with exactly the accepted SDK exceptions: 808 default passes, one doctest and 76 required service-profile passes with zero required skips. The restoration/workspace/library profile passes twelve tests, including concurrent replay, active pins, stale plans, retired sources/targets, role revocation, rollback and oversized-template blockers. Contract: docs/delivery/workflow-defaults.md; evidence: docs/delivery/completion-verification.md.

C13; reuse version creation/library template tools and WorkspaceService [B09]. Existing published immutability and independent workspace revisions remain intact.

### Implementation sequence

1. Define immutable template/baseline association, content hash and symbolic dependency manifest. Resolve dependencies through current authorized selectors/application services, not hard-coded ref_id strings from another environment.
2. Implement a read-only preview that freezes target version/workspace refs, template version/hash and binding mapping. Return a safe structured diff, blockers and expiring plan token; show whether the result replaces DRAFT or creates a new DRAFT.
3. Apply only the identical reviewed plan with a dedicated command_key and current concurrency checks. Create successor drafts for published/retired targets; never auto-publish or alter request-type routing.
4. For draft replacement, retain history and increment both relevant revisions atomically. Published payloads, active case pins and private runtime data are untouched. Plan invalidation includes changed template bindings and peer edits.
5. Add separate layout-only reset and local-unsaved-discard semantics where needed; do not conflate either with default-definition restore. Unassociated custom workflows require explicit template choice.
6. Verify retry, concurrent apply, missing dependency, wrong role, mixed form/workflow template and partial failure. Keep bounded template application atomic or stage it invisibly with an explicit repair journal.

### Acceptance criteria

- The same restore command creates one result; changed-payload/key reuse conflicts.
- Published/retired reset creates a new editable draft; an already running case retains original graph/form/subprocess pins and data.
- A stale preview fails without partial updates; no secrets, users, roles or integration identities reset as a side effect.

### Verification and required evidence

Proposed tests/integration/test_workflow_defaults.py plus workspace/library regressions. A12/A13/A25. Split .1 baseline manifest, .2 preview/apply, .3 concurrency/active-case proof. mise run check.

### Data, compatibility, rollout and peer handoff

C13 → APP-FE-027/037. This is normal authoring functionality, not the destructive demo-environment reset. New baseline metadata follows D01.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-026.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Dependency update (2026-10-08): prerequisites and the shared gate are satisfied. READY records eligibility for remaining work or task-specific acceptance review; this through-014 closure does not mark this separate task DONE.

Completion evidence (2026-10-09): [completion-verification.md](delivery/completion-verification.md) and [completion-gate.json](delivery/completion-gate.json). Original applied migration bytes are preserved; additive head is k026_workflow_restore. C13 handoff and generated en/fa schemas are current. Remaining protected-effect, paired frontend transfer, demo/reset, image/CI/restore and browser acceptance are not inferred from this closure.

<a id="app-be-027"></a>

## APP-BE-027 — Complete private transfer/report contracts and backend operational bounds

Priority: P1  
Status: BLOCKED  
Verification: IMPLEMENTED  
Area: backend / M3  
Depends-On: APP-BE-001, APP-BE-006  
Related: Existing private media/reporting; frontend API-04 and session boundary  
Decisions: None  
Owner: Codex  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-027.md

Earlier preparation evidence: docs/delivery/wave-four-verification.md. The shared gate and exact baseline approval are now resolved; see the dependency update below.

### Goal

Private attachments and generated reports work through the paired application at explicit supported sizes without exposing files or conflating queued and complete output.

### Context: preserve and extend

Current completion work (2026-10-09): backend bounds and actual worker/storage evidence remain valid. Graceful rejection while an oversized body is still streaming through the paired frontend is unverified/blocked: clients can receive a connection reset. Header-only preflight evidence does not satisfy this acceptance; APP-FE-036 must resolve the peer behavior.

Reuse current media auth/integrity, report definitions and isolated reporting worker. F15/F16 identify boundary buffering/deadline risks; Angular’s Node service is APP-FE-036, not duplicate Python transport work.

### Implementation sequence

1. Inventory upload/download/report paths, size/rate limits, headers, pagination and timeout behavior; compare them with the boundary’s body and deadline policies.
2. Fix backend inconsistencies in private authorization, late-stream errors, cancellation/resource cleanup and bounded exports. Preserve private no-store and safe content disposition; do not expose direct ungoverned bucket URLs.
3. Specify streamed/binary responses separately from JSON envelopes; clarify accepted/queued/report-ready results. Avoid turning a POST search/report alias into an assumed generated-file job.
4. Document operation-specific limits and memory behavior for the initial demo profile; add out-of-bound rejection before excessive work. Keep DB sessions isolated across concurrency and async code nonblocking.
5. Coordinate exact header forwarding and error/reconciliation behavior with APP-FE-036. Test actual storage and report worker, not only BytesIO fixtures.

### Acceptance criteria

- The agreed maximum accepted upload/download/report passes through the entire app; oversize fails early with a safe recoverable error.
- Private files, generated archives and report lists remain actor-authorized and no-store.
- Dropped transfers release owned resources and do not falsely mark the workflow or report completed.

### Verification and required evidence

Extend existing service/media/report worker tests plus transfer limit cases. A19/A22; real S3-compatible storage, broker and reporting worker; mise run check and explicit integration evidence.

### Data, compatibility, rollout and peer handoff

C14 → APP-FE-036. No browser token exposure, public media shortcut or hidden change to download authorization.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-027.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Dependency update (2026-10-08): prerequisites and the shared gate are satisfied. READY records eligibility for remaining work or task-specific acceptance review; this through-014 closure does not mark this separate task DONE.

<a id="app-be-028"></a>

## APP-BE-028 — Extend one combined workflow regression across all included features

Priority: P0  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M3  
Depends-On: APP-BE-005, APP-BE-020, APP-BE-024, APP-BE-025, APP-BE-026, APP-BE-027, APP-BE-014  
Related: DOCS-002; existing full workflow regression; B16  
Decisions: None  
Owner: TBD  
Estimate: 4–7 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Prove the same case traverses authored definitions, private data, human approval, AI supervision, branches, integrations and notifications instead of relying on disconnected feature tests.

### Context: preserve and extend

Reuse the saved purchase vector and existing disposable PostgreSQL flow runner. B16 explicitly distinguishes core combined coverage from separately covered AI/parallel/delivery stages.

### Implementation sequence

1. Extend the existing runner with exact template/client/role setup and a shared scenario manifest consumed by the frontend browser harness. Keep all fixture data synthetic and refs generated fresh.
2. Execute approve, reject and correction variants with actual auth, non-superuser actors, hidden fields, nested rows, attachments and unchanged submission replay keys.
3. Exercise required AI supervision (deterministic labeled provider for regular gate), finance/procurement branch/join and pinned child process, actual sandbox external effect, receipt and notification.
4. Publish successor form/workflow and restore a default while an older case waits; prove original pins persist. Include race claims, stale refs, lost mutation responses, cancellation and supported compensation.
5. Capture sanitized assertions/timeline/operation evidence and exact skipped exclusions. Fail if a required stage is missing or a fake worker replaces the real stage needed by the profile.

### Acceptance criteria

- A single paired scenario records every included stage and the final business outcome; each fault variant preserves invariants.
- AI cannot approve; two reviewers cannot both win the same claim; duplicate submission/effect creates one logical result.
- The regular check includes the deterministic combined path; actual worker/storage/network profile runs separately where needed and is required for demo readiness.

### Verification and required evidence

Extend existing full workflow and HTTP tests; proposed tests/integration/test_connected_workflow.py. A12–A22/A24. Use disposable DB/cache/broker/bucket with cleanup ownership. mise run check plus real-service profile.

### Data, compatibility, rollout and peer handoff

C12–C14 → APP-FE-037. Define fixtures once; do not make frontend and backend invent different purchase semantics.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-028.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

<a id="app-be-029"></a>

## APP-BE-029 — Build the guarded demo harness and reversible scenario reset

Priority: P0  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M5  
Depends-On: APP-BE-005, APP-BE-016, APP-BE-017, APP-BE-018, APP-BE-028, APP-BE-015, APP-BE-009, APP-BE-010, APP-BE-011  
Related: Existing flow/browser seed runners; backend reset task is excluded  
Decisions: None  
Owner: TBD  
Estimate: 3–5 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Run, inspect and repeat the complete application demonstration with restored default workflows while refusing to touch non-demo data.

### Context: preserve and extend

Reuse C01/C13 templates and existing disposable harness patterns. The backend mise reset task calls docker compose down -v [B03]; it must never be substituted for this task.

### Implementation sequence

1. Provide documented proposed commands `mise run demo-prepare`, `mise run demo-verify`, and `mise run demo-reset` only after implementing them. Include environment identity and a private run manifest listing exact owned resources.
2. Populate dashboard/calendar/help/notification/view/favorite fixtures through actual services where behavior matters. Seed past histories via controlled fixtures only if labeled; do not pretend they were observed production traffic.
3. Guard reset with explicit disposable profile, exact environment ID and confirmation. Refuse remote/shared/production endpoints and unknown ownership. Stop new producers and safely drain/reconcile owned workers and sandbox effects first.
4. Recreate only the isolated demo resources or run a narrowly scoped transactional reset with a proven ownership manifest. Restore immutable template defaults, new demo credentials and known scenarios. Do not alter operator/private shared data.
5. Keep reset logs sanitized and verify resulting graphs/pins/template hashes. Include instructions for an interrupted reset and separate layout/draft-default restoration.
6. Publish a demo script with actor changes, expected screens/results and failure demonstrations; maintain a compact evidence index, not a collection of private response dumps.

### Acceptance criteria

- Prepare → demo → reset → demo → reset is repeatable with known defaults, no duplicate jobs and no stray deliveries.
- Reset against a non-demo target fails before any delete; unknown resource ownership is not guessed.
- System demo, live vendor and live AI labels remain distinct; support failures are inspectable.

### Verification and required evidence

Proposed tests/integration/test_demo_harness.py, including production/shared refusal and interrupted reset recovery. A01–A26 as relevant, with A25 mandatory. mise run check plus actual full demo rehearsal.

### Data, compatibility, rollout and peer handoff

C13/C14 → APP-FE-037/038. Destructive action is explicit and confined to disposable owned resources. No background promises or live system resets.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-029.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

<a id="app-be-030"></a>

## APP-BE-030 — Review backend code quality and repair feature-critical issues

Priority: P1  
Status: IN_PROGRESS  
Verification: IMPLEMENTED  
Area: backend / M5  
Depends-On: APP-BE-001, APP-BE-002  
Related: Existing Python skills and domain boundaries  
Decisions: None  
Owner: Codex  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: docs/changes/APP-BE-030.md  

Earlier preparation evidence: docs/delivery/wave-three-verification.md. The shared gate is now resolved; separate task closure remains eligible for review.

### Goal

Close architecture and correctness defects uncovered by the product work without starting an unrelated repository-wide rewrite.

### Context: preserve and extend

Current completion work (2026-10-09): historical migration/SDK blockers are resolved by the accepted decisions and through-020 gate. Restoration findings and repairs are added to docs/delivery/backend-review.md. Final review remains scoped and incomplete for unimplemented protected-effect/demo/release capabilities.

Inspect src/apps owners and shared core/utils, focused services B09–B14 and relevant final diffs. Existing test passes are not proof of safe concurrency or transaction boundaries.

### Implementation sequence

1. Produce a findings register by file/function with evidence, impact, minimal repair and test. Include untyped new service boundaries, mutable session sharing, blocking async calls, swallowed cancellations, transaction scope and unbounded work.
2. Check new DB invariants have constraints/atomic updates where required, row locks use current instances, queries apply authorization/live predicates, and effects are staged outside mutable business transactions.
3. Review all new JSON/envelope/page/nested DTO inheritance and snake_case OpenAPI. Follow multiline entity formatting only in changed declarations. No serialization alias or error-code changes without compatibility notes.
4. Fix critical findings in small owned PRs or suffix tasks linked to the affected feature; re-run its contract/concurrency/browser handoff tests. Nonblocking refactors get explicit later scope.
5. Recheck migrations, seeds, query indexes with evidence, cancellation/timeouts and public error redaction. Close the register only for actually inspected scope and verified repairs.

### Acceptance criteria

- All feature-critical findings are resolved or explicitly block the affected capability; a checklist alone is not completion.
- No new architecture layer duplicates an existing owner, and no broad formatting migration hides behavioral changes.
- Full check and relevant service tests pass after repairs.

### Verification and required evidence

Use task-specific regressions plus static/typing/security and real DB race tests. A02/A16/A18/A20/A24. mise run check; retain a reviewed-scope list and unresolved backlog links.

### Data, compatibility, rollout and peer handoff

Review effort is bounded initial allowance; large new findings trigger revised estimates and separate linked tasks, not invented completion.

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-030.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

Dependency update (2026-10-08): prerequisites and the shared gate are satisfied. READY records eligibility for remaining work or task-specific acceptance review; this through-014 closure does not mark this separate task DONE.

<a id="app-be-031"></a>

## APP-BE-031 — Automate paired contracts, hosted checks and rebuilt image verification

Priority: P0  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M5  
Depends-On: APP-BE-002, APP-BE-028  
Related: REPO-004; frontend ARC-04/API-01/QA-07  
Decisions: None  
Owner: TBD  
Estimate: 2–4 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Certify a concrete backend/frontend pair and actual application image instead of trusting stale checked-in API snapshots or local dependency fixes.

### Context: preserve and extend

F11 verifies stored snapshots, not a live peer. B02 records that application image rebuild for REPO-004 was unverified. Inspect current .github workflows before adding any duplicate job.

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

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-031.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

<a id="app-be-032"></a>

## APP-BE-032 — Close backend demo acceptance, restore and support handoff

Priority: P0  
Status: BLOCKED  
Verification: NOT_RUN  
Area: backend / M5  
Depends-On: APP-BE-029, APP-BE-030, APP-BE-031  
Related: Existing QA-03–07 cross-project release scope; safeguards/restore  
Decisions: None  
Owner: TBD  
Estimate: 3–5 person-days; confidence low-to-medium before intake  
Change-Record: None

### Goal

Publish a truthful backend capability ledger and demonstrate the operational behavior needed for the requested application, without confusing demo readiness with production certification.

### Context: preserve and extend

Reuse B17 and existing real worker/restore tests. New application features must be included in backup/readiness/restore evidence; historical test counts are not fresh results.

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

### Completion instruction

Follow the full execution rules below. Record exact files reused/changed, contract IDs, migration/seed impact, focused and full commands, warnings/skips, and peer limits. Update the task and docs/changes/APP-BE-032.md only from observed evidence. Do not label a missing service, unresolved warning or required untested action complete.

---

# Appendix A — Shared contracts and acceptance

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
| --- | --- | --- | --- | --- |
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
| --- | --- |
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

---

# Appendix B — Execution and completion rules

# Product delivery execution rules

Version: 1.0.0 · Prepared 2026-10-08 · Applies to the new APP-BE / APP-FE work only, while preserving existing repository rules.

## 1. Outcome and scope

Deliver the agreed product, not a replacement architecture: a usable seed-backed application, no JSON-dependent normal workflows, visual authoring, actual requests and human decisions, an integration receipt, calendar/analytics, settings, saved views/favorites, help, notifications and recorded supportable failures. “n8n-level” means the enumerated editing capabilities, not feature parity with all n8n integrations.

Do not claim perfect software, general production readiness, or acceptance from passing tests. Make each status evidence-based. The product owner retains business decisions and authority to approve scope changes.

## 2. Mandatory intake and no-redo rule

1. Read AGENTS.md, applicable nested instructions, existing root backlog / docs/BACKLOG.md, the APP backlog, relevant change records, README and tool manifests.
2. Record the exact current commit and local modifications without overwriting them. Read the corresponding peer contract manifest when another repository is involved.
3. When graphify-out/graph.json exists and graphify is available, run a scoped graphify query first; use its wiki for broad navigation. After code changes run graphify update . when required. Record unavailable tooling honestly; do not invent a graph result.
4. Search titles, IDs, code, tests and contract owners. Mark the scope REUSE, EXTEND, VERIFY, NEW or CONFLICT. Existing implementations are not new work merely because old docs call them planned.
5. If acceptance already holds, add missing evidence and close only the uncovered delta. Do not rebuild auth, the form renderer, CRUD/search, the canvas, notification delivery, outbox or process engine.
6. Existing IDs stay unchanged. APP tasks are new delivery deltas; their Related field is a crosswalk, not permission to reset old DONE tasks. The APP backlog is authoritative for APP status; old backlog indexes link to it instead of duplicating full task bodies.

## 3. Status vocabulary

Keep legacy Status values READY / BLOCKED / CONFLICT / IN_PROGRESS / DONE. READY means eligible to start, never verified. Initially every task has Verification: NOT_RUN, Change-Record: None, Owner: TBD.

Track evidence separately: DESIGNED → IMPLEMENTED → VERIFIED_LOCAL → VERIFIED_INTEGRATED → DEMO_READY → DEPLOYED → USER_ACCEPTED. These are capability/evidence labels, not application lifecycle states. Do not add these words to process/work-item enums.

A blocked peer contract, inaccessible service, skipped required test, unresolved warning, or missing user signoff remains visible. A dependency is satisfied by actual verified behavior at the required scope, not only another ticket's label.

## 4. Exact completion gate

Every completed implementation task must pass `mise run check` in its repository, from the final working tree, with exit code 0 and zero emitted toolchain/lint/type/build/test warnings. Record command, start/end, tool versions, commit/tree digest, changed files, return codes, pass/fail/skip totals and sanitized log locations. Fast focused commands are useful while working but do not replace the final gate.

Do not shorten the task, remove test files, relax thresholds, add blanket warning suppression, use `--no-warnings`, discard stderr, mask failures with `|| true`, or claim success from an earlier run. Retain exit status when piping logs. Disable automatic retries of failing test runs as a way to hide flaky behavior; fix and rerun, recording the failure and final evidence.

Use native warning enforcement first: linter warning ceiling, type-checker warnings as errors, pytest warning policy, build diagnostics and captured browser console/runtime diagnostics. A final structured summary verifies categories; a grep for the word “warning” is not sufficient. Expected failure-case diagnostics must be explicitly asserted inside negative tests, not escape as unexplained warnings.

The backend baseline contains two narrowly scoped third-party deprecation filters [B04]. Inventory and remediate them; do not quietly classify masked warnings as absent. An unavoidable existing exception needs a separately recorded owner decision and status VERIFIED_WITH_EXCEPTION, not strict warning-free readiness. Existing test names/skips remain visible. An environmental skip does not prove service integration; a deliberate platform-inapplicable test must have a documented reason and cannot cover an acceptance requirement.

Upgrade `mise run check` additively so new contract, help/map, and affected deterministic browser/HTTP checks become repeatable gates. Preserve baseline checks. Keep paid provider calls and destructive restore tests explicit opt-ins; a demo including their outcomes additionally requires separate recorded runs. Do not trigger paid accounts during ordinary checks.

## 5. Integrated and demo completion

A check pass is necessary, not sufficient. A feature crossing API/DB/worker/storage boundaries also needs its specified real-service tests and both sides of the contract. Fixture-only work must be labeled, and not closed as integrated. An unavailable prerequisite means BLOCKED, with the exact setup needed and no false readiness claim.

DEMO_READY requires a pinned repository pair, current generated contracts, genuine browser/network flow, actual migrated disposable services, required scenario coverage, no unexpected browser/server warnings, a reset rehearsal, documented limits, and an inspectable final outcome. Required human approval and no-duplicate-effect behavior are functional acceptance conditions. USER_ACCEPTED requires a named authorized person's actual signoff, never an agent's assumption.

## 6. Contract and architecture rules

Backend business behavior stays under its existing src/apps owner. Routes adapt HTTP; transactions and side effects belong in application services. Shared infrastructure stays in src/core / src/utils only when truly shared. Use existing query/DTO/error/permission conventions. All Python JSON DTOs—including nested request/response/envelope/page models—inherit core.base_dto.BaseDTO. New JSON/OpenAPI fields are snake_case, no serialization aliases; headers are exempt. Preserve existing machine codes even where their strings are not snake_case. Follow multiline SQLModel Field/Column/ForeignKey formatting in AGENTS.md.

Frontend generated types live at the transport edge. Domain models remain independent of PrimeNG, Material and the canvas library. Keep the existing same-origin session boundary; do not move tokens into browser storage. Preserve legacy session wire names during this plan unless an explicit compatible migration is agreed. Never decode opaque ref_id in Angular. Replace mutation references from authoritative responses; a durable favorite/deep link must resolve fresh refs before action.

Proposed paths and DTOs in this pack are design candidates, not discovered APIs. The responsible backend task must check for an existing equivalent, freeze the exact compatible contract and examples, generate OpenAPI, and supply the peer handoff before frontend integration is marked complete. No endpoint may silently change its envelope. Existing operation-specific idempotency keys stay unchanged; new command keys freeze target and payload and reject reuse with different intent.

## 7. Product/UI rules

PrimeNG-first for new/redesigned business controls, Tailwind for layout, existing Material/CDK and specialist canvas controls retained as documented exceptions. Do not remove established libraries or adopt paid replacements without approval. Use pinned-version public APIs and semantic tokens. A generic payload console is not a finished domain screen. Ordinary users must never need a JSON editor or copied reference to complete an in-scope journey.

Every screen specifies loading, empty, invalid, forbidden/revoked, stale/conflicting, uncertain, failed and successful states; preserves edits where safe; and fences async results after actor/context change. English/Farsi display text, keyboard use and RTL/LTR are acceptance, not optional polish. Do not translate machine codes or alter canonical values. Do not introduce Signal Forms/NgRx/a new component framework merely because current documentation advertises it.

## 8. Data, migration and reset safety

Never edit an already-applied migration to add new production schema without an explicit migration decision. The owner-authorized DB-002 restructuring supersedes the previous one-file/additive-only repository policy with exactly two revision files, schema first and required data second. Legacy database transitions remain separate reviewed operator actions. Do not stamp away drift, reset shared data or downgrade a populated database to make tests pass. Use uniquely named disposable DB/bucket/queue resources with explicit ownership.

Default restoration operates on editable definitions or creates a new draft. It never changes published payloads, execution pins, submitted data, users/roles/secrets, or provider side effects. Demo-environment reset is a different, guarded operation. The existing backend `mise run reset` deletes Compose volumes: never use it as the demo harness command [B03].

No secret, token, raw payload, private file content, arbitrary stack trace or personal field belongs in ordinary telemetry, support records, screenshots or public artifacts. Failure recording must survive business rollback where possible, but must not recursively fail the request when the recording store is unavailable. Report fallback limitations honestly.

## 9. Execution rhythm and handoff

Select one coherent ready unit, state its result, implement bounded changes, run focused tests, inspect the diff, run the full gate, then update evidence. A large parent task has numbered implementation substeps; split it into suffix tickets before parallel work. Never renumber or duplicate the parent. Serialize migrations, lockfile updates, generated contracts and shared component changes per repository.

Each cross-repo handoff includes exact SHA/tree digest, contract IDs, path/method/operation IDs, DTO/schema changes, permission mapping, lifecycle/replay rules, sample successes/errors, migration/head, service prerequisites, generated OpenAPI hash, tests and unresolved limits. A handoff request does not prove the peer implemented it.

Use docs/changes/TASK-ID.md and the existing change-journal structure. Include baseline reuse, final behavior, compatibility, commands/results, supported limits, risk/decision/backlog updates and peer readiness. Record execution facts only. No new completion claims without a corresponding evidence record.

## 10. Decision and estimate discipline

Unknown owners are TBD. Calendar dates start only after kickoff/capacity is agreed. Effort ranges are planning estimates, not agent runtime guarantees. Re-estimate after intake and the first three implementation tickets. Do not invent model-specific speed multipliers or fabricate deployment, approval, provider access or browser observations.

When a decision blocks only one branch, continue independent tasks; do not repeatedly ask answered questions. Record the exact unresolved choice, recommended default, consequence and affected tasks. Do not silently choose a tenancy model, external provider, destructive reset or incompatible migration policy.

## Non-negotiable distinction checklist

- Published version vs editable workspace vs promoted executable graph: different states and references.
- Stable resource locator vs optimistic mutation ref_id: favorites/deep links resolve current refs, not stale saved tokens.
- Process finished vs business approved vs external receipt confirmed: different evidence; no invented transition codes.
- Soft-deleted vs inactive/retired/cancelled vs retained history: live lists exclude deletion without erasing audit.
- AI recommendation vs read-only tool approval vs required human business approval: none substitutes for another.
- Secret exists vs provider live-verified vs successful business effect: readiness labels must state the actual check.
- Layout reset vs discard unsaved edits vs restore default definition vs destructive demo-environment reset: separate actions and authority.
- Saved view vs raw case data vs permission grant: private query preferences never grant access.
- Seen help content vs permission or task completion: user acknowledgment has no workflow authority.
- Code implemented vs tests verified vs demo-ready vs deployed vs user-accepted: never promote evidence by wording.

---

# Appendix C — Effort and delivery timing

# Timing, capacity and dependency plan

Prepared 2026-10-08. These are analyst planning ranges for future implementation, not measured delivery speed, commitments, model runtimes or dates when work will be done. No task is running asynchronously. Staffing, budget, availability and start date are unknown.

## Estimation model

One person-day is eight hours of task effort including implementation, focused review, tests and documentation. The calendar illustrations assume **four task-days per person per week**; the fifth day covers general coordination/unplanned interruptions outside task estimates. Design/QA/product review capacity must be available, but people are not assigned here. Parallel agents do not automatically equal independent staffed engineers: review and shared-file ownership remain constraints.

Low/high values are optimistic-to-cautious planning estimates, not statistical P50/P90. The ranges have low-to-medium confidence until APP-BE-001 / APP-FE-001 and the first three implementation tasks provide measured throughput. Do not multiply by an invented Sol/model speed factor.

| Workstream | Tasks | Base effort (person-days) | Base hours |
| --- | ---: | ---: | ---: |
| Backend | 32 | 85.5–157 | 684–1256 |
| Frontend | 38 | 123.5–213 | 988–1704 |
| Combined | 70 | 209–370 | 1672–2960 |

For planning, hold an additional **25% explicit integration/rework reserve**: combined **261.25–462.5 person-days**. This is a separately visible assumption, not effort already included in each task or a calibrated probability. Do not add a second unnamed buffer. External access/approval delays are additional elapsed time and are not estimated as engineer work.

## Work by milestone

| Milestone | Backend person-days | Frontend person-days | Combined |
| --- | ---: | ---: | ---: |
| M0 — Baseline and trustworthy checks | 4.5–9 | 4–7 | 8.5–16 |
| M1 — Usable application foundation | 23–42 | 26.5–48 | 49.5–90 |
| M2 — Visual authoring and safe defaults | 12–22 | 38–64 | 50–86 |
| M3 — Connected case and actual system outcome | 27–50 | 32–55 | 59–105 |
| M4 — Calendar, reminders and business insights | 9–16 | 7–12 | 16–28 |
| M5 — Full coverage, repeatable demo and acceptance | 10–18 | 16–27 | 26–45 |

Milestone grouping is not a strict waterfall: a calendar/API contract can advance while an unrelated visual inspector is being built. Dependencies in the task index decide ordering. The complete demo requires every mandatory task, not only early milestones.

## Illustrative elapsed-time scenarios

The model schedules the listed dependency graph onto backend/frontend work slots (one non-preempted task per slot), choosing earliest available work and then milestone/ID. Week zero begins only after kickoff/access. It excludes decision/provider waiting and does not explicitly model every shared-file collision; the 25% reserve addresses some, not all, integration uncertainty. These are planning illustrations, not guaranteed deadlines.

| Hypothetical available delivery capacity | Base modeled weeks | With 25% reserve | Interpretation |
| --- | ---: | ---: | --- |
| 1 backend + 1 frontend | 32–55 | 40–69 | Design/QA/product support available; frontend scope is substantial. |
| 1 backend + 2 frontend | 23–42 | 29–52 | Backend and shared contract decisions increasingly constrain parallel UI work. |
| 2 backend + 2 frontend | 18–31 | 23–39 | Requires real review capacity and serialized migration/lockfile ownership. |

One person performing both workstreams serially has a base workload floor of **53–93 weeks** at the assumed four task-days/week, before reserve and waiting. This is not a recommendation to staff that way; it prevents treating total effort as instant parallel agent throughput.

## Detailed relative windows — illustrative 1 backend + 2 frontend slots

Rows show separate low/high schedules, rounded to one decimal week. “Start L/H” and “Finish L/H” are each scenario’s modeled positions, not a promise that a task may start anywhere in that interval. No calendar start date is assumed.

| Task | Base days | Start L/H (week) | Finish L/H (week) |
| --- | ---: | ---: | ---: |
| APP-BE-001 | 1.5–3 | 0.0 / 0.0 | 0.4 / 0.8 |
| APP-BE-002 | 2–4 | 0.4 / 0.8 | 0.9 / 1.8 |
| APP-BE-003 | 1–2 | 0.9 / 1.8 | 1.1 / 2.2 |
| APP-BE-004 | 2–4 | 1.1 / 2.2 | 1.6 / 3.2 |
| APP-BE-005 | 3–5 | 1.6 / 3.2 | 2.4 / 4.5 |
| APP-BE-006 | 3–6 | 2.4 / 4.5 | 3.1 / 6.0 |
| APP-BE-007 | 2–4 | 3.1 / 6.0 | 3.6 / 7.0 |
| APP-BE-008 | 3–5 | 3.6 / 7.0 | 4.4 / 8.2 |
| APP-BE-009 | 3–5 | 4.4 / 8.2 | 5.1 / 9.5 |
| APP-BE-010 | 1–2 | 5.1 / 9.5 | 5.4 / 10.0 |
| APP-BE-011 | 2–4 | 5.4 / 10.0 | 5.9 / 11.0 |
| APP-BE-012 | 2–4 | 7.6 / 14.2 | 8.1 / 15.2 |
| APP-BE-013 | 1–2 | 5.9 / 11.0 | 6.1 / 11.5 |
| APP-BE-014 | 4–7 | 9.9 / 18.2 | 10.9 / 20.0 |
| APP-BE-015 | 3–5 | 6.1 / 11.5 | 6.9 / 12.8 |
| APP-BE-016 | 4–7 | 16.6 / 30.8 | 17.6 / 32.5 |
| APP-BE-017 | 2–4 | 17.6 / 32.5 | 18.1 / 33.5 |
| APP-BE-018 | 3–5 | 18.1 / 33.5 | 18.9 / 34.8 |
| APP-BE-019 | 3–6 | 6.9 / 12.8 | 7.6 / 14.2 |
| APP-BE-020 | 3–5 | 8.1 / 15.2 | 8.9 / 16.5 |
| APP-BE-021 | 4–7 | 10.9 / 20.0 | 11.9 / 21.8 |
| APP-BE-022 | 3–6 | 11.9 / 21.8 | 12.6 / 23.2 |
| APP-BE-023 | 4–7 | 12.6 / 23.2 | 13.6 / 25.0 |
| APP-BE-024 | 3–6 | 13.6 / 25.0 | 14.4 / 26.5 |
| APP-BE-025 | 3–6 | 14.4 / 26.5 | 15.1 / 28.0 |
| APP-BE-026 | 4–7 | 8.9 / 16.5 | 9.9 / 18.2 |
| APP-BE-027 | 2–4 | 15.1 / 28.0 | 15.6 / 29.0 |
| APP-BE-028 | 4–7 | 15.6 / 29.0 | 16.6 / 30.8 |
| APP-BE-029 | 3–5 | 18.9 / 34.8 | 19.6 / 36.0 |
| APP-BE-030 | 2–4 | 19.6 / 36.0 | 20.1 / 37.0 |
| APP-BE-031 | 2–4 | 20.1 / 37.0 | 20.6 / 38.0 |
| APP-BE-032 | 3–5 | 20.6 / 38.0 | 21.4 / 39.2 |
| APP-FE-001 | 2–3 | 0.0 / 0.0 | 0.5 / 0.8 |
| APP-FE-002 | 2–4 | 0.5 / 0.8 | 1.0 / 1.8 |
| APP-FE-003 | 3–5 | 1.0 / 1.8 | 1.8 / 3.0 |
| APP-FE-004 | 3–5 | 1.0 / 1.8 | 1.8 / 3.0 |
| APP-FE-005 | 3–5 | 1.8 / 3.0 | 2.5 / 4.2 |
| APP-FE-006 | 3–5 | 4.4 / 8.2 | 5.1 / 9.5 |
| APP-FE-007 | 4–7 | 5.1 / 9.5 | 6.1 / 11.2 |
| APP-FE-008 | 2–4 | 3.6 / 7.0 | 4.1 / 8.0 |
| APP-FE-009 | 2–4 | 5.1 / 9.5 | 5.6 / 10.5 |
| APP-FE-010 | 1.5–3 | 5.6 / 10.5 | 6.0 / 11.2 |
| APP-FE-011 | 2–4 | 8.6 / 15.8 | 9.1 / 16.8 |
| APP-FE-012 | 3–5 | 11.9 / 21.0 | 12.6 / 22.2 |
| APP-FE-013 | 2–4 | 6.9 / 12.8 | 7.4 / 13.8 |
| APP-FE-014 | 4–7 | 18.1 / 33.5 | 19.1 / 35.2 |
| APP-FE-015 | 3–5 | 18.9 / 34.8 | 19.6 / 36.0 |
| APP-FE-016 | 5–8 | 7.6 / 14.2 | 8.9 / 16.2 |
| APP-FE-017 | 4–7 | 8.9 / 16.8 | 9.9 / 18.5 |
| APP-FE-018 | 5–8 | 9.9 / 18.5 | 11.1 / 20.5 |
| APP-FE-019 | 3–5 | 11.1 / 20.5 | 11.9 / 21.8 |
| APP-FE-020 | 4–7 | 6.0 / 11.2 | 7.0 / 13.0 |
| APP-FE-021 | 4–6 | 7.6 / 14.2 | 8.6 / 15.8 |
| APP-FE-022 | 4–7 | 11.9 / 21.8 | 12.9 / 23.5 |
| APP-FE-023 | 4–7 | 9.1 / 16.2 | 10.1 / 18.0 |
| APP-FE-024 | 4–7 | 10.1 / 18.0 | 11.1 / 19.8 |
| APP-FE-025 | 4–7 | 15.1 / 28.0 | 16.1 / 29.8 |
| APP-FE-026 | 4–7 | 17.1 / 31.5 | 18.1 / 33.2 |
| APP-FE-027 | 3–5 | 11.1 / 19.8 | 11.9 / 21.0 |
| APP-FE-028 | 3–5 | 15.6 / 29.0 | 16.4 / 30.2 |
| APP-FE-029 | 4–6 | 12.9 / 23.5 | 13.9 / 25.0 |
| APP-FE-030 | 4–7 | 16.1 / 29.8 | 17.1 / 31.5 |
| APP-FE-031 | 3–6 | 6.1 / 11.2 | 6.9 / 12.8 |
| APP-FE-032 | 3–6 | 18.1 / 33.2 | 18.9 / 34.8 |
| APP-FE-033 | 4–7 | 19.6 / 36.0 | 20.6 / 37.8 |
| APP-FE-034 | 3–5 | 20.6 / 37.8 | 21.4 / 39.0 |
| APP-FE-035 | 3–5 | 20.6 / 37.8 | 21.4 / 39.0 |
| APP-FE-036 | 3–5 | 16.4 / 30.2 | 17.1 / 31.5 |
| APP-FE-037 | 4–6 | 21.4 / 39.0 | 22.4 / 40.5 |
| APP-FE-038 | 2–4 | 22.4 / 40.5 | 22.9 / 41.5 |

## Key dependencies and parallel-work rules

The principal authoring chain is baseline → typed metadata/pickers → form controls and node inspectors → human/mapping/branch/service configuration → publication/defaults → real case → combined browser demo. Calendar/reminders require their own persistence and notification contracts; dashboards require authorized metric definitions. Default restore depends on exact baseline/dependency readiness, not just a reset button.

Run baseline/review/design-system work in parallel across repos. Frontend may use labeled fixtures while a producer contract is being implemented, but that task stays unintegrated. Backend migration writers serialize through one owner. Contract generation, lockfile changes, shared picker components, route registries and seed/template manifests also need a single integration owner per batch. Do not have agents edit the same generated output concurrently.

Tasks APP-BE-032 and APP-FE-038 record backend and full-product acceptance separately. Backend-only verification does not depend on frontend final signoff, preventing a circular dependency; final frontend/product acceptance consumes the backend record.

## Scope additions not hidden in the base estimate

A named vendor integration, Jalali input/conversion, service-principal redesign, multi-replica session store, calendar sync/recurrence or major newly discovered UI/API gaps need scoped estimates after their contracts/access are known. The base includes the local HTTP sandbox adapter and AI evaluation harness, not unbounded provider certification or paid evaluation campaigns. No paid vendor/security/legal approval is assumed.

## Re-estimation checkpoints

After intake, remove already-satisfied implementation work and retain the relevant verification effort. After the first three implementation tasks, measure review/rework and actual check/setup effort, then update task ranges and rerun the dependency model. Reforecast at the first visual-authoring demo, first sandbox receipt and full reset rehearsal. Every change preserves original estimate, new estimate, reason and scope impact; never quietly revise numbers to make a missed target disappear.

## Suggested first execution batch

Start APP-BE-001 and APP-FE-001 together. Follow with APP-BE-002 and APP-FE-002, resolve D01 through APP-BE-003, then seed/live-query work and the frontend Angular/PrimeNG review. Freeze C02–C05 and C11 early so profile/help/views/pickers and visual authoring can proceed independently. No production rollout, paid calls or destructive demo reset is part of this intake batch.

---

# Appendix D — Evidence

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

## Through-020 dependency review — 2026-10-08

All unfinished tasks 021–032 and ENABLES/BLOCKS/SUPERSEDES/CONFLICTS effects reviewed.
021, 026, 027 and 030 remain READY; their separate feature/review closure is pending.
023 now has 015 satisfied but still requires 022; 028 now has 020 satisfied but still
requires 024/025/026/027. 029 has calendar/reminder/analytics/support satisfied and remains
blocked on 028. 031 still requires 028; 032 still requires 029/030/031. No task is
superseded, no new conflict is introduced, and no peer/frontend task is marked DONE.
MAP-10/11/13 producers are now verified; MAP-07/08 remain assigned to 024/023.
