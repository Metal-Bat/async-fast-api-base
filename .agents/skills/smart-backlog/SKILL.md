---
name: smart-backlog
description: Maintain and execute this Python project's repository-aware engineering backlog. Use whenever adding, updating, prioritizing, selecting, starting, or completing work in BACKLOG.md, including requests such as "work on backlog", "next task", or "continue" when backlog work is active.
---

# Smart Backlog

Treat `BACKLOG.md` as the project's engineering memory. Treat the repository state as the source of truth.

## Mandatory preparation

Before adding, changing, selecting, starting, or completing a backlog task:

1. Read all of `BACKLOG.md`. If it does not exist, create it only when there is a concrete task to record.
2. Follow the repository's `AGENTS.md`, including graphify discovery and update requirements.
3. Inspect the relevant Python packages, public interfaces, SQLModel entities, Alembic migrations, FastAPI routes and DTOs, tests, infrastructure, and `pyproject.toml` dependencies.
4. Search task titles, IDs, goals, and acceptance criteria for duplicates or overlap.
5. Determine dependencies, conflicts, superseded work, and the current architecture direction.

Do not add a duplicate. Update the existing task when its intended outcome matches.

## Task contract

Use stable IDs and this structure:

```yaml
## TASK-ID — Title

Priority: P0/P1/P2/P3/IDEA
Status: READY/BLOCKED/CONFLICT/IN_PROGRESS/DONE
Area:
Depends-On:
Related:
Change-Record:

### Goal

### Context

### Acceptance Criteria
```

- Keep IDs stable after creation. Never reuse a removed or completed ID.
- Use `None` for an empty `Depends-On` or `Related` field.
- Use `None` for `Change-Record` until completion; a DONE task must reference `docs/changes/TASK-ID.md`.
- In `Depends-On` and `Related`, reference task IDs and label non-dependency relationships as `BLOCKS`, `ENABLES`, `RELATED`, `CONFLICTS`, or `SUPERSEDES` in `Context`.
- Write acceptance criteria as observable outcomes. Include relevant tests, migrations, API behavior, compatibility, and operational checks; do not prescribe implementation details unless they are a required contract.
- Keep `Context` concise but preserve decisions, constraints, rejected incompatible directions, and evidence a future implementer would otherwise need to rediscover.

## Priority and execution order

Priority expresses impact or urgency; it is not queue position. Calculate execution order using:

1. Correctness, security, and data-loss risk.
2. Blocking dependencies.
3. Architecture foundations.
4. Database and API contracts.
5. Features that depend on those foundations.
6. Tests and integrations.
7. Cleanup and refactoring.

A lower-priority enabling task may execute before a higher-priority dependent task. Prefer READY work that unblocks the most valuable aligned work.

## Python project compatibility

- Respect the package layers already used under `src/apps`: `domain`, `application`, `data`, and `presentation`.
- Treat SQLModel entities, Alembic migrations, FastAPI/OpenAPI contracts, `BaseDTO` snake-case wire rules, Celery task semantics, cache invalidation, localization, and public error codes as cross-task compatibility surfaces.
- Use the project's SQLAlchemy/SQLModel expression patterns and repository abstractions. Do not plan parallel abstractions that duplicate an existing interface without recording a migration or replacement path.
- Inspect `pyproject.toml` and `uv.lock` before proposing new Python dependencies. Record why an existing dependency cannot satisfy the requirement.
- Use one migration lineage consistent with the repository's current migration policy. Detect schema conflicts before selecting database work.
- Prefer focused tests that prove behavior. Use the existing `uv` and pre-commit workflows for verification.

## Conflict handling

Mark a task `CONFLICT` when it cannot safely coexist with another task or the established architecture. Record:

- The conflicting task IDs or implemented contract.
- Why they conflict.
- The architectural or compatibility consequence.
- The decision required from the user.

Do not silently choose between incompatible directions. A task waiting only on an ordinary dependency is `BLOCKED`, not `CONFLICT`.

## Implementation workflow

When starting a task:

1. Revalidate it against the repository and all READY or IN_PROGRESS tasks.
2. Confirm its dependencies are DONE or already satisfied by the implementation.
3. Set it to `IN_PROGRESS` before making substantive changes.
4. Keep discoveries separated:
   - Required for the current acceptance criteria: implement now.
   - Small related improvement that reduces current complexity: include when proportionate.
   - Independent improvement: record as a separate backlog task.
   - Speculative work: record as `IDEA` only when it is concrete enough to be useful.

Do not expand an active task merely because nearby improvements exist.

## Completion workflow

Before setting a task to `DONE`:

1. Verify every acceptance criterion against the repository state.
2. Run the focused tests and applicable project checks. For this repository, normally include Ruff, `ty`, and pre-commit when the affected scope warrants them.
3. Run integration tests when the behavior crosses PostgreSQL, Redis, S3, Celery, or other Compose services.
4. Apply and verify any required Alembic migration using the repository's migration workflow.
5. Use the mandatory `change-journal` skill to create `docs/changes/TASK-ID.md` from final repository evidence and add its path to `Change-Record`.
6. Add concise completion notes under `Context`, including the implementation location, verification performed, and any material limitation.
7. Set the task to `DONE` only after the implementation, required verification, change record, and backlog link are complete.
8. Recalculate relationships across the backlog: enabled, newly blocked, obsolete, conflicting, or superseded tasks.
9. Run the required graphify update after code changes.

Do not mark a task DONE because work was attempted, checks were skipped, or the implementation is only partially usable.

## Selecting work

For `work on backlog`, `next task`, or `continue` while backlog work is active:

1. Review every READY task and relevant BLOCKED/CONFLICT task.
2. Build the dependency order.
3. Exclude obsolete, conflicting, and unsatisfied tasks.
4. Prefer work that resolves correctness risk or unblocks aligned foundations.
5. Select one coherent task and explain the dependency reason briefly before implementation.

Never select the first task solely because of file order or priority label.
