# Baseline and reuse inventory

Intake: 2026-10-08. Backend commit `995829eebd9483ac6b589c1648fc799c650ad464`;
peer commit `afe4bbe5f566c80e7eb45f6ef9f12c041d60139d`. The initial tree had only
untracked delivery-pack documentation. Preserve those files and all existing DONE IDs.

## Repository evidence

The scoped graphify query returned existing repository, query, notification and seed owners.
There is no `graphify-out/wiki/index.md`. Source inspection therefore followed the scoped graph.
The actual migration chain is `base -> b13a0c7d2e44 -> c24f913ab601`, one head.
The delivery pack's single-head assertion was stale; REPO-002 already records the workspace successor.
D01 remains a pending explicit policy decision, documented in [DECISIONS.md](DECISIONS.md).

Auth, immutable form/workflow libraries, work items, process engine, AI supervision,
notification delivery, task outbox, cache invalidation and reporting already exist.
Changes extend their owners. Historical REPO/OBS/DOCS/DB records are retained, not re-certified.

## Initial verification

The unchanged `mise run check` first failed at uv cache creation in the restricted sandbox.
`UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check` passed lock/format/lint/type steps
then hit sandbox-denied multiprocessing socket creation in Bandit. The authorized
run outside the sandbox is retained in `/tmp/app-be-baseline-check-unrestricted.log`;
its final outcome is recorded in the APP-BE-001 change record. No reset task was run.

Two exact SDK deprecation filters remain: Cohere coroutine detection and Google GenAI
private union aliases. An ordinary test pass with those filters is not strict warning-free
readiness; APP-BE-002 owns remediation and structured evidence. Default integration skips
do not demonstrate DB/worker/storage/browser behavior.

## Versions and contracts

[contract-manifest.json](contract-manifest.json) records installed and locked versions,
permission owners, migration head, schema and lock hashes. Python is 3.14.7; FastAPI
0.143.0, Pydantic 2.13.5, SQLModel 0.0.48, SQLAlchemy 2.0.54, Celery 5.6.3, AI 2.54.0.
Effective uv tools Ruff 0.16.10 and ty 0.0.85 differ from mise pins 0.16.6 and 0.0.78;
APP-BE-002 must reconcile these instead of silently reporting the pins as executed tools.

The peer platform snapshot has the same 314 operations and 425 schemas; all shared schema
objects match. The older base snapshot has 302 operations and lacks 12 current operations.
Neither snapshot certifies a live deployed pair. Peer manifests were read only; no peer
files were edited and no message was sent. D02–D06 remain the pack's stated proposed
defaults/constraints, not fabricated owner signoff or live-provider/browser evidence.

## Task ownership and uncovered deltas

Disposition describes the work required, not completion. New persistence waits for D01.

| Task | Disposition | Existing owner/files | Uncovered delta |
|---|---|---|---|
| APP-BE-001 | VERIFY | `docs/tools/openapi_coverage.py` | Baseline and consumer inventory |
| APP-BE-002 | EXTEND | `scripts/run_flow_test.py; .mise.toml; pyproject.toml` | Structured strict gate, warning probes |
| APP-BE-003 | CONFLICT / VERIFY | `src/migrations/versions/; tests/integration/test_migrations.py` | D01 approval and populated upgrade proof |
| APP-BE-004 | EXTEND | `src/apps/users/application/authorization.py; src/apps/step_types/application/service.py` | Permission reconciliation and optional role templates |
| APP-BE-005 | EXTEND | `scripts/seed_frontend_browser.py; scripts/seed_studio_browser.py` | Supported runtime bootstrap without test imports |
| APP-BE-006 | EXTEND | `src/core/base_repository.py; src/utils/pagination.py` | Live lists/counts and direct-query audit |
| APP-BE-007 | NEW / EXTEND | `src/apps/users/domain/auth_dto.py; src/apps/users/application/auth_service.py` | Typed persisted self preferences |
| APP-BE-008 | EXTEND | `src/apps/designer/application/service.py; src/apps/forms/data/options.py` | Authorized locator and selection resolution |
| APP-BE-009 | NEW / REUSE | `src/apps/work_items/application/service.py` | Private views; reuse existing personal work-item metadata |
| APP-BE-010 | NEW | `src/apps/users/domain/; src/locales/` | Minimal user help state only; frontend owns help content |
| APP-BE-011 | EXTEND | `src/apps/health/routes.py` | Authorized actionable setup projection |
| APP-BE-012 | EXTEND | `src/apps/designer/application/library.py; src/apps/workflows/application/service.py` | Dependency readiness and repair metadata |
| APP-BE-013 | EXTEND | `src/apps/notifications/application/templates.py; src/apps/notifications/domain/dto.py` | Machine-checkable event/translation design |
| APP-BE-014 | EXTEND | `src/apps/notifications/application/service.py; src/apps/notifications/application/delivery.py` | Unified inbox over existing delivery owner |
| APP-BE-015 | NEW / REUSE | `src/core/bpms_observability.py; src/apps/processes/application/timeline.py` | Safe durable support projection |
| APP-BE-016 | NEW / REUSE | `src/apps/work_items/application/service.py; src/utils/date_utils.py` | Workflow-aware calendar; canonical Gregorian dates |
| APP-BE-017 | EXTEND | `src/core/celery_scheduler.py; src/apps/tasks/application/outbox.py` | Calendar/work reminders through existing scheduler |
| APP-BE-018 | EXTEND | `src/apps/reporting/application/registry.py; src/apps/users/application/reporting.py` | Authorized metric/chart query |
| APP-BE-019 | EXTEND | `src/apps/designer/application/service.py; src/apps/step_types/application/registry.py` | Typed authoring metadata gaps |
| APP-BE-020 | EXTEND | `src/apps/forms/application/runtime.py; src/apps/forms/application/behavior.py` | Runtime form conformance |
| APP-BE-021 | VERIFY / EXTEND | `src/apps/work_items/application/service.py; src/apps/workflows/application/service.py` | Protected effect approval enforcement |
| APP-BE-022 | EXTEND | `src/apps/processes/application/extension_services.py; src/apps/integrations/application/service.py` | Governed operation/principal policy |
| APP-BE-023 | NEW / REUSE | `src/apps/integrations/application/; src/apps/processes/application/automation.py` | Real HTTP sandbox receipt |
| APP-BE-024 | EXTEND | `src/apps/processes/application/recovery.py; src/apps/processes/application/automation.py` | Uncertain outcome and compensation |
| APP-BE-025 | VERIFY / EXTEND | `src/apps/ai/application/providers.py; src/apps/ai/application/` | Supervised AI evaluation; live calls need approval |
| APP-BE-026 | EXTEND | `src/apps/workflows/application/workspace.py; src/apps/designer/application/library.py` | Immutable defaults and reviewed restoration |
| APP-BE-027 | VERIFY / EXTEND | `src/apps/media/; src/apps/reporting/` | Private transfer/report bounds |
| APP-BE-028 | EXTEND | `tests/integration/test_full_workflow.py; tests/integration/test_frontend_journey.py` | Combined deterministic workflow regression |
| APP-BE-029 | NEW / REUSE | `scripts/run_flow_test.py; scripts/seed_frontend_browser.py` | Guarded disposable demo harness |
| APP-BE-030 | VERIFY / EXTEND | `src/apps/; src/core/; src/utils/` | Scoped findings register and critical repairs |
| APP-BE-031 | EXTEND | `compose/backend/Dockerfile; .github/; docs/tools/openapi_coverage.py` | Paired/image/hosted verification |
| APP-BE-032 | VERIFY / EXTEND | `docs/operations/bpms-safeguards.md; tests/integration/test_bpms_recovery.py` | Final real-service handoff |
