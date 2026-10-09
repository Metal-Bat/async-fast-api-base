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

## Evidence references

Repository snapshots reviewed on 2026-10-08. These sources establish baseline behavior, not current deployment or new test passes. Re-read changed files before implementation.

- **[B01]** [AGENTS.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/AGENTS.md) — Existing graphify, BaseDTO, snake_case, Swagger and entity-format rules.
- **[B02]** [BACKLOG.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/BACKLOG.md) — Existing IDs, DB-001 single initial revision, historical checks and REPO-004 rebuild limitation.
- **[B03]** [.mise.toml](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/.mise.toml) — Actual check sequence; reset removes Compose volumes and is not a safe demo reset.
- **[B04]** [pyproject.toml](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/pyproject.toml) — Python/dependency constraints and two narrow SDK warning filters.
- **[B23]** [.agents/skills/smart-backlog/SKILL.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/.agents/skills/smart-backlog/SKILL.md) — Preserve IDs, inspect baseline and avoid duplicate work.
- **[B24]** [.agents/skills/change-journal/SKILL.md](https://github.com/Metal-Bat/async-fast-api-base/blob/995829eebd9483ac6b589c1648fc799c650ad464/.agents/skills/change-journal/SKILL.md) — Change-record format and backlog relationships.
- **[F01]** [AGENTS.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/AGENTS.md) — Existing graphify rules.
- **[F03]** [mise.toml](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/mise.toml) — Actual frontend check commands; full browser/backend suites are separate at baseline.
- **[F04]** [package.json](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/package.json) — Pinned Angular 21.2.25, PrimeNG 21.1.10, Foblex 19.3.0, and available test scripts.
- **[F14]** [docs/SESSION-BOUNDARY.md](https://github.com/Metal-Bat/angular-base/blob/afe4bbe5f566c80e7eb45f6ef9f12c041d60139d/docs/SESSION-BOUNDARY.md) — Accepted same-origin server-held token design; single-process session-store limitations.

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
