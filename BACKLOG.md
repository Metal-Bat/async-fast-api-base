# Engineering Backlog

## REPO-002 — Restore the quality gate after dependency updates

Priority: P1
Status: DONE
Area: repository/dependencies
Depends-On: None
Related: REPO-001
Change-Record: docs/changes/REPO-002.md

### Goal

Make the current working tree pass `mise run check` with the updated uv dependencies,
and prepare the user-authorized changes for Conventional Commit delivery.

### Context

RELATED REPO-001: retain all-file secret scanning and exact reviewed fingerprints.
The upgraded type checker reports optional truth tests and changed typing contracts;
SQLAlchemy 2.1 requires the explicit asyncio extra for async database imports.
Existing frontend runtime and studio workspace work is included in the requested commit.

Completed: `mise run check` passes with 664 default tests, 119 opt-in skips, one doctest,
four disposable PostgreSQL workflow tests, and all applicable hooks. The knowledge graph
was refreshed and Commitizen validated the delivery message. PostgreSQL was started locally;
an interrupted first flow run passed on retry and in the final complete gate.

### Acceptance Criteria

- Preserve empty-value behavior while resolving type diagnostics without disabling rules.
- Fresh uv synchronization includes SQLAlchemy's async runtime dependency.
- Review individual secret findings without weakening scanner failure behavior.
- The complete quality gate passes, including disposable PostgreSQL workflow tests and hooks.
- Refresh the knowledge graph and validate the proposed Conventional Commit message.

## REPO-001 — Prepare a clean, reproducible repository baseline

Priority: P1
Status: DONE
Area: repository/tooling
Depends-On: None
Related: DOCS-001
Change-Record: docs/changes/REPO-001.md

### Goal

Commit the implemented backend, documentation and contributor tooling in coherent groups,
keeping local credentials private and documenting Obsidian navigation.

### Context

RELATED DOCS-001: document opening the project root as an Obsidian vault. Initial staging exposed
that the old secret scan ignored untracked files. The corrected gate scans untracked files too
and permits only reviewed file/type/fingerprint matches. Runtime local files remain unchanged.

Completed: development templates validate with Settings; 631 tests pass, 114 integration skips;
Ruff, ty and pre-commit pass. Reviewed fixture and schema-identifier findings are recorded in
`.secrets.baseline`. No push or history rewrite is part of this task.

### Acceptance Criteria

- Local environment credentials and reader state stay out of Git; fresh clones have templates.
- A new secret finding or a reviewed value moved to another file fails the gate.
- Vendored Swagger/ReDoc assets retain upstream bytes during formatting checks.
- Documentation explains setup, verification and Obsidian entry points.
- Commit groups describe the implemented scope and leave a clean working tree.

## OBS-002 — Resolve structlog and duplicate FastAPI telemetry

Priority: P1
Status: DONE
Area: core/observability
Depends-On: OBS-001
Related: OBS-001
Change-Record: docs/changes/OBS-002.md

### Goal

Remove invalid Logger attribute warnings while preserving local log rendering, and verify
current exporter delivery through FastAPI startup and a real gRPC collector.

### Context

RELATED OBS-001: its diagnostic filter stops feedback but still exports structlog's internal
`_logger` and `_name` extras. Supplied logs also show HTTP exporter traffic reaching a gRPC
receiver. A real Compose startup identified FastAPI native auto-configuration adding duplicate
HTTP exporters alongside the application gRPC pipeline. Disable native telemetry; retain the
existing instrumentation and providers.

Completed: metadata and lifespan regressions reproduced both causes, then passed after fixes.
629 tests passed; static checks and hooks passed. Rebuilt images and restarted the local backend.
Swagger requests returned 200 without telemetry errors; collector received logs and Jaeger received
new API traces. Local services are left running; database data was preserved.

### Acceptance Criteria

- Structured application logs export without internal formatter metadata; local handlers retain it.
- Preserve diagnostic exclusion and trace correlation; add a failing regression before the fix.
- Verify real collector receipt of logs, traces and metrics using current providers.
- FastAPI lifespan adds no HTTP exporters; real Swagger requests export through the existing pipeline.
- Run project checks and document remaining deployment verification limits.

## DOCS-002 — Execute the documented HTTP workflow

Priority: P1
Status: DONE
Area: documentation/testing
Depends-On: DOCS-001
Related: DOCS-001
Change-Record: docs/changes/DOCS-002.md

### Goal

Validate the documented login-to-approval sequence against real authentication and PostgreSQL,
make the check repeatable, and correct missing setup steps.

### Context

RELATED DOCS-001: close its full HTTP sequence evidence gap. User requested validation of the
current process. Keep English guides and framework-neutral examples. In-process HTTP coverage
must not be presented as deployed browser, external-service or reader acceptance.

Completed: real HTTP journey and original purchase regression passed on fresh PostgreSQL;
628 default tests passed (114 opt-in skips), static checks and hooks passed. Setup requirements
and deployment acceptance are documented. Temporary database/container removed.

### Acceptance Criteria

- A newly migrated disposable database passes the existing purchase flow and the documented
  HTTP journey with ordinary users, real bearer sessions and no authorization overrides.
- Verify invalid input, stale writes, ownership/permission denial, command replay, completion,
  refresh rotation/reuse and logout through HTTP responses.
- The standard flow command includes the HTTP regression; documentation states exact setup,
  observable success criteria and remaining deployment/reader checks.
- Existing tests, static checks and repository hooks pass; record evidence and limits.

## DOCS-001 — User and frontend documentation handoff

Priority: P1
Status: DONE
Area: documentation
Depends-On: None
Related: DB-001
Change-Record: docs/changes/DOCS-001.md

### Goal

Provide English user journeys, a framework-neutral TypeScript frontend walkthrough,
trustworthy examples and portable documentation navigation.

### Context

User requested all four identified documentation gaps be filled. Existing guides and generated
references remain the foundation. RELATED DB-001: replace outdated migration instructions.
Do not change runtime contracts to make a guide work; explicitly document current access and
discovery limits. English only; frontend code is framework-neutral TypeScript.

Completed: user handbook, frontend walkthrough/shared contracts, checked TypeScript and 11
curated wire cases; six documentation checks, portable navigation and historical-design labels.
Full suite: 628 passed, 113 skipped; separate disposable PostgreSQL purchase regression passed.
Static checks passed. Browser/reader validation remains an explicitly documented future check.

### Acceptance Criteria

- Plain-language handbook covers starting, tracking, reviewing and correcting requests.
- Login-to-completion frontend guide includes prerequisites, calls, payloads, UI states,
  authorization, current refs, retries and errors, with checked TypeScript examples.
- Curated examples validate against current OpenAPI/DTOs; generated references stop emitting
  fabricated business values such as `status: example`.
- Documentation home provides audience routes; internal links work in ordinary Markdown;
  implemented, historical and proposed material is clearly distinguished.
- Automated checks cover local links, documented API examples and generated-reference drift.

## DB-001 — Consolidate Alembic into one initial revision

Priority: P2
Status: DONE
Area: migrations
Depends-On: None
Related: None
Change-Record: docs/changes/DB-001.md

### Goal

Replace the 33-file migration chain with one self-contained root/head migration.

### Context

User explicitly requested one migration file. Preserve frozen operations, seeds and triggers,
and retain the existing head ID `b13a0c7d2e44` for databases already fully upgraded.
Intermediate revisions must be upgraded with the previous chain before switching.
No overlap with OBS-001; verify against isolated PostgreSQL without touching project databases.

Completed: one root/head file, identical PostgreSQL schema dumps and normalized seed data across
91 tables, successful fresh upgrade and downgrade/re-upgrade, and no-op upgrade from the former
head. Migration integration test passed; full suite: 622 passed, 113 skipped. Ruff, ty and
pre-commit passed. Temporary database container removed; README explains earlier-revision handling.

### Acceptance Criteria

- Exactly one revision file, with no parent and the former head ID.
- Fresh upgrade preserves schema, functions, triggers and seeds compared with the old chain.
- Disposable PostgreSQL upgrade/downgrade/upgrade succeeds; an existing head remains a no-op.
- Update migration tests and deployment documentation; run project quality checks.

## OBS-001 — Prevent telemetry diagnostic feedback

Priority: P1
Status: DONE
Area: core/observability
Depends-On: None
Related: None
Change-Record: docs/changes/OBS-001.md

### Goal

Prevent telemetry diagnostics from re-entering OTLP logging and document recovery from
HTTP exporters targeting the Compose gRPC receiver.

### Context

Reported connection resets use HTTP exporter messages, while current source explicitly uses
gRPC exporters and Compose targets port 4317. No running Compose services are available locally.
The OTLP log handler currently accepts SDK diagnostics, allowing recursive logging and export
failure feedback. No other backlog tasks exist in the current checkout.

Completed: handler filter and regression coverage added in `src/core/observability.py` and
`tests/core/test_observability.py`; README documents deployment recovery. Full pytest run outside
the sandbox: 622 passed, 113 integration tests skipped. Ruff, ty and pre-commit passed.
Live recovery remains unverified because no Compose services are running locally.

### Acceptance Criteria

- Application records reach OTLP; OpenTelemetry diagnostics remain available to local handlers
  without entering the OTLP pipeline.
- Regression coverage verifies all three exporters use gRPC and the configured endpoint.
- Document rebuild/recreation and protocol troubleshooting; report live verification limits.
- Record focused and project-wide check results without hiding pre-existing failures.
