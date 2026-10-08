# Changelog

## Unreleased

### Documentation

- Added an English user handbook and framework-neutral frontend walkthrough with checked
  TypeScript and request/response examples. Replaced fabricated response samples with curated
  examples or explicit coverage gaps, added portable navigation, and marked historical migration
  guidance. Documentation tests check API examples, local links and generated-reference drift.
  See [DOCS-001](docs/changes/DOCS-001.md).

### Fixed

- Restore local cache startup with bounded Dragonfly threads and authenticated health gates,
  defer Celery scheduler cleanup during signal interruption, and constrain SQLAlchemy to the
  OpenTelemetry-supported 2.0 series. Rebuild cache and application images; see
  [REPO-004](docs/changes/REPO-004.md).

- Local workflow checks now start the configured PostgreSQL service when the default port is
  unavailable, wait for readiness, and report setup/cleanup failures safely. See
  [REPO-003](docs/changes/REPO-003.md).

- Restore async database imports after the SQLAlchemy 2.1 upgrade by explicitly installing
  its asyncio extra. See [REPO-002](docs/changes/REPO-002.md).

- Disabled duplicate FastAPI native HTTP telemetry exporters when the application's gRPC
  pipeline owns instrumentation, and removed internal structlog metadata from exported logs.
  Verified real backend log delivery and Jaeger traces. See [OBS-002](docs/changes/OBS-002.md).

- Prevented OpenTelemetry diagnostics from feeding back into OTLP log export while preserving
  local diagnostic output. Added recovery instructions for stale HTTP exporters targeting the
  gRPC Collector port. See [OBS-001](docs/changes/OBS-001.md).

### Changed

- Keep local Compose credentials out of Git and provide development templates in
  `.envs/examples/`. Secret checks now include untracked source/configuration and compare findings
  against reviewed fingerprints. Added Obsidian vault instructions. See
  [REPO-001](docs/changes/REPO-001.md).

- Consolidated 33 Alembic revisions into one initial migration while retaining head ID
  `b13a0c7d2e44`. Existing databases at earlier revisions must first upgrade using the previous
  migration chain. See [DB-001](docs/changes/DB-001.md).

- Updated compatible locked dependencies, kept Pydantic on the stable 2.13 line, and made the production image explicitly omit the local `dev` group. `mise run check` now runs the complete local quality gate sequentially. See the [dependency policy](docs/operations/dependencies.md).


- Private user file and image downloads accept a bounded `Content-Disposition` request
  preference. Generic files remain attachments; WebP images can be inline or attachments.
  Responses remain `private, no-store`. See MEDIA-002.

- Removed the optional xAI adapter and conflicting `ai-xai` dependency profile. Configurations selecting `xai` now fail as unavailable; the TypeSafe/Jev adapter remains in the standard AI build. See BPMS-018.

- Live Jev evaluations now inject the published agent and governed connection from the database
  using agent/actor references, replacing the separate evaluation API-key environment variable.
  See the BPMS-018 checkpoint and
  [evaluation instructions](docs/evaluations/README.md).

- Select responses now use `key`/`value` items and support `response_format=page|items`. Task
  selects default to the shared paginated envelope; enum selectors include translated English/Farsi
  labels. This breaks the previous `value`/`title` convention. See
  BPMS-021.

### Security

- Made file and image downloads private and owner-authorized, added server-side passive-file
  validation, S3 metadata integrity preflight, bounded streaming, and a code-owned BPMS access
  policy seam. See MEDIA-001.
- Removed production assertions from form/cache invariants and parameterized the step-type catalog
  seed SQL. Bandit now reports no production-source findings without suppressions. See
  SEC-001.

### Fixed

- Backend images now install production Python packages from `uv.lock` and fail the build
  when it is out of sync with `pyproject.toml`, preventing container and local version drift.

- Swagger now groups all operations by subject in a clear topic order, with English and Farsi
  descriptions for every topic. Only probe endpoints appear under health. See
  DOCS-002.

- Generated Swagger now lists the optional shared request headers used by middleware,
  including language, correlation ID and audit reason, with Farsi descriptions. Existing Date and
  User-Agent inputs remain documented once per operation. See HTTP-003.

- BPMS workers now consume the automation queue; bounded retention preserves active work,
  BPMS execution references and business audit history. SQL logging hides bound parameters.
  Added audited administrator recovery and verified restore/worker-restart procedures.
  See BPMS-016.

- OpenTelemetry now honors SDK/per-signal exporter disable settings and shuts down API telemetry
  providers during lifespan cleanup, preventing collector retry threads from logging after pytest
  closes capture streams. See OBS-001.

### Added

- Workflow authoring selectors now include exact published form/workflow versions and verified service/notification connections with per-resource access checks. The [full workflow roadmap](docs/roadmap/full-workflow.md), [response scenarios](docs/api/response-scenarios.md), and [Obsidian home](docs/Home.md) support frontend design.


- Added a protected read-only workflow field inventory with exact version pins, localized
  dependency evidence, bounded review suggestions, and separate counts for unique fields and
  collection occurrences. Backend images now compile the checked-in Farsi catalog. See
  BPMS-035 and the
  [field inventory guide](docs/api/field-inventory.md).

- Added a permission-aware definition library for authored components, data types and
  subprocesses, including category/help/sample discovery, dependency and where-used reports,
  version guidance, independent form/workflow template drafts, and guarded bulk upgrade
  preview/apply. Apply migration `b13a0c7d2e44` before using template creation. See
  BPMS-033 and the
  [definition library guide](docs/api/definition-library.md).

- Pinned subprocess calls now execute as durable child processes with isolated typed inputs,
  separate human/timer waits, one-time parent continuation, nested timeline positions and
  explicit failure routing. Apply migration `5a73d9102b6e` and run the existing automation
  workers/outbox publisher. See BPMS-032 and the
  [subprocess guide](docs/api/subprocess-authoring.md).

- Added published reusable subprocess interfaces with typed input/output mappings, exact child
  version pins, access and recursion checks, and designer discovery. Execution is delivered by
  BPMS-032. Apply migration `4e6f8a913c02`. See
  BPMS-031 and the
  [subprocess authoring guide](docs/api/subprocess-authoring.md).

- Added pinned human-task views and action profiles with server-enforced field writes, scoped
  review/print data, correction feedback and linked draft rounds. Task-only candidates use the
  filtered work-item view. Apply migration `7f42c641ab30`. See
  BPMS-030 and [task-view API guide](docs/api/task-views.md).

- Added authored reusable form components and data types with exact published-version pins,
  current grants, draft upgrade preview, and copy-to-inline authoring. Apply migration
  `9154a7157416`. See BPMS-028.

- Added opt-in deterministic form behavior, permissioned calculation overrides, stable UUIDv7
  collection identities, and attachment-safe row movement for request and human-work drafts.
  Apply migration `58e200bb4077` after the library revision. See
  BPMS-029.

- Added the shared primitive field catalog, typed/dependent option sources, current domain
  membership checks at request and human completion, capability fallbacks and atomic host
  navigation previews. New field-option keys use explicit `json-scalar/1` encoding. Operators
  approve remote URLs/routes through `FORM_CLIENT_OPTION_URLS` and `FORM_NAVIGATION_ROUTES`;
  both default empty. No migration is needed. See BPMS-024.

- Added immutable English/Persian form catalogs, reviewed translations, localized preview/runtime
  text and exact date/decimal formatting. Locale switches preserve canonical data and pinned
  interactions. Apply migration `49c0a2d18e76` before deployment; the initial calendar profile is
  Gregorian. See BPMS-027.

- Added typed client conditions for form variants and workflow routing, with numeric release
  ranges, authenticated-context preview, saved-origin execution and localized API descriptions.
  Historical form checksums remain valid. See BPMS-023.

- AI decisions can now pause for an encrypted, claimant-authorized read-only tool approval and
  resume through the existing outbox. Saved-report lookup reuses registered queries, bounds and
  current permissions. Denial, expiry, cancellation and duplicate delivery cannot repeat a lookup.
  Copilot/Codex accept governed access tokens. See BPMS-018
  for deployment requirements and limits.

- Added a protected, versioned AI decision API and background execution path with pinned
  data and choice contracts, human-review routing, configured provider connections, and
  durable task budgets. Apply migrations `00cf0e3945e2`, `918927598e70` and `6bc31d7f2a10`; configure
  `AI_ADMIN_LIMITS` and `AI_PRICE_CATALOG` before publishing agents. Provider coverage
  and remaining live-evaluation requirements are tracked in the
  BPMS-018 checkpoint.

- Added authenticated client/release registration, restricted request starts, immutable client-aware form/page designs and audited cross-client draft resume. Apply migrations `381f1cc8bb7e` through `5e0683de2f52`. See BPMS-022.

- Added trusted class-based workflow step extensions with automatic draft reconciliation,
  protected publish/select APIs, localized help, typed sync/background execution and worker
  contract checks. Deploy the same extension package to API and workers; no migration is needed.
  See BPMS-025.

- Added optional RFC 9110 client Date diagnostics and a configurable device-time
  advisory without changing request acceptance. See HTTP-001.
- Documented optional User-Agent on application APIs and bounded its capture consistently
  for request logs, authentication and history. See HTTP-002.

- Added durable localized workflow notifications, recipient-owned in-app search/detail/read APIs,
  governed email delivery with retry and bounce tracking, and retention redaction. Apply migration
  `d7f3a9c1e204`. See BPMS-020.
- Added parallel workflow splits and joins, bounded loop visits, per-step retry limits, durable
  reverse-order compensation with explicit recovery, and publication checks for unsafe advanced
  graphs. Apply migration `c6e48a72d1b0`. See BPMS-015.
- Added an append-only, transactionally ordered process event stream plus authorized graph/runtime
  timeline and report projections with bounded redacted payloads, stable pagination, candidate and
  attempt details, and parallel-ready current positions. Apply migration `f27c81b4930d`. See
  BPMS-014.
- Added durable event waits, delays, and deadlines with hashed correlations, authenticated adapter
  delivery, scheduler leases, transactional broker handoff, restart recovery, and exactly-once
  process resume. Apply migration `a13d5e7f9012`. See BPMS-013.
- Added group and direct-user cartables with atomic claiming, audited human-work actions,
  step-specific form and attachment completion, reassignment, per-user state, and exactly-once
  workflow resume. Apply migration `9d7c2e4f6a11`. See BPMS-011.
- Added audited mixed file/image attachment collections with form-level constraints, atomic draft
  editing, private request-scoped downloads, submission materialization, and safe abandoned-upload
  cleanup. Apply migration `c41e8a7d2f90`. See BPMS-004.
- Added crash-safe registered background service automation with atomic outbox dispatch, pinned
  connection execution, broker priority mapping, idempotent callbacks, and worker-loss recovery.
  Apply migration `8ac9d34f210b`. See BPMS-012.
- Added protected, bounded designer catalogs, permission-aware resource selectors, and typed
  workflow expression completion with private-graph and forward-step filtering. See
  BPMS-005.
- Added a durable single-token workflow runtime with transactional request start, validated step
  snapshots, deterministic transitions, persistent waits, bounded retries, and idempotent process
  controls. Apply migration `0afa840431f1`. See BPMS-010.
- Added permission-protected request types and business-request drafts with exact published
  form/workflow pins, access-bound search/detail/report APIs, validated idempotent submission, and
  database-sealed submitted data. Apply migration `14d62d43235e`. See
  BPMS-009.
- Added bounded typed workflow expressions, expression-backed form calculations, and explicit
  versioned transforms for scalar, date/time, array, projection, null/default, and formatting
  conversions. Apply migration `6f5e2a1c9b80`. See BPMS-008.
- Added immutable, versioned workflow graphs with typed port bindings, open/restricted user and
  group grants, human task targets and form policies, canonical publication checksums, and
  protected authoring APIs. Apply migration `13097937b4c8`. See
  BPMS-007.
- Added versioned forms with bounded schema/render validation, preview, immutable publication,
  and history. Apply migration `be9a70072a3d`. See BPMS-003.
- Added governed integration connections, user/group grants, credential-version rotation,
  verification, and revocation. Apply migration `41b114f1c753`; provider use requires separately
  provisioned encrypted credentials and endpoint settings. See BPMS-019.

- Added a versioned workflow step catalog with eight initial types, typed ports, trusted handler
  validation, and database-enforced publication immutability. Deployments must apply the additive
  catalog migration. See BPMS-006.
- Added permission-protected operational work groups, user membership lifecycle management, and
  bounded user/group selectors for future workflow routing and cartables. See
  BPMS-002.
