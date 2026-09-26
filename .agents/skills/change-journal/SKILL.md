---
name: change-journal
description: Create durable, repository-grounded documentation for completed backlog tasks and material Python system changes. Use when completing a backlog item or finishing an architecture, API, database, deployment, or important bug-fix change; update CHANGELOG.md only when users or release operators need to know.
---

# Change Journal

Explain the completed system change for future developers. Do not copy or paraphrase a git diff file by file. Document final behavior and verified facts from the repository.

## Required use

Create a detailed change record when any of these applies:

- A `BACKLOG.md` task is being marked `DONE`.
- Module interfaces, architecture seams, or dependency direction changed.
- A FastAPI route, DTO wire contract, authentication rule, authorization rule, or public error changed.
- A SQLModel entity, PostgreSQL schema, index, constraint, data migration, or Alembic behavior changed.
- Runtime configuration, environment variables, Compose services, worker queues, schedules, storage, caching, or deployment behavior changed.
- An important correctness, security, data-loss, concurrency, or production bug was fixed.

Minor internal cleanup with no material behavioral or maintenance consequence does not require a record unless it completes a backlog task.

## Evidence to inspect

Before writing:

1. Read the original backlog task and its relationships when one exists.
2. Inspect the final repository state, including untracked files relevant to the change; do not rely only on `git diff`.
3. Inspect affected Python modules, public interfaces, SQLModel entities, Alembic migration, FastAPI/OpenAPI DTOs, configuration, and infrastructure.
4. Inspect the tests and the actual command results produced during implementation.
5. Read related records under `docs/changes/` and the current `CHANGELOG.md`.
6. Review unfinished backlog tasks for `ENABLES`, `BLOCKS`, `SUPERSEDES`, and `CONFLICTS` effects.

Document final reality when it differs from the original plan.

## Storage and naming

Store the detailed record at:

```text
docs/changes/TASK-ID.md
```

Use the stable backlog ID as the filename. When a required material change has no backlog task, first add or update the concrete task through the mandatory `smart-backlog` workflow, then use its ID. Do not invent an unrelated second task solely to split one completed change.

Create `docs/changes/` when the first record is written. Do not create empty placeholder records.

## Record contract

Use this canonical structure:

```markdown
# TASK-ID — Title

Backlog: TASK-ID
Date: YYYY-MM-DD
Area: service/module

## Summary

## Why

## What Changed

- Important behavior changes
- Important implementation changes
- Important interfaces/data changes

## Architecture

### Before

### After

### Reason

## Compatibility

- API changes
- Database migrations
- Configuration changes
- Deployment impact

## Validation

Commands executed:

- command

Result:

PASS / PARTIAL

## Backlog Impact

Enabled:

- TASK-ID

Blocked:

- TASK-ID

Superseded:

- TASK-ID

Conflicts:

- TASK-ID

## References

Commit:

Pull Request:

Additional notes:
```

- `Summary`: state the delivered outcome in a few sentences.
- `Why`: record the actual problem and constraints that led to the change.
- `What Changed`: describe cohesive behavior, important implementation locations, interfaces, and data changes. Explain current runtime behavior, failure handling, ownership, and operational expectations here.
- `Architecture`: record Before/After/Reason when architecture changed. Otherwise state `No architecture change` below the heading and omit its subsections.
- `Compatibility`: include only relevant API, migration, configuration, deployment, and backward-compatibility facts. Write `None` when the section is useful for clarity but no compatibility impact exists.
- `Validation`: list only commands and manual checks actually completed. Use `PASS` only when all required checks passed; use `PARTIAL` when a check was skipped, failed, timed out, was unavailable, or only focused verification ran, and explain the limitation.
- `Backlog Impact`: name affected task IDs under each relationship. Use `None` beneath an empty category and confirm all unfinished tasks were reviewed.
- `References`: record commit and pull-request identifiers only when they exist; otherwise write `None`. Use additional notes for durable repository-relative links or operational details.

Use repository-relative paths in durable records. Do not include workstation-specific absolute paths.

## Python project compatibility checklist

Document these when affected:

- Python package/module interfaces and the `domain`, `application`, `data`, and `presentation` layers.
- FastAPI routes, status codes, OpenAPI behavior, and `BaseDTO` snake-case JSON fields.
- Public error codes and English/Farsi localization changes.
- SQLModel entities, PostgreSQL objects, data conversion, and the single Alembic migration lineage.
- Celery task names, queues, idempotency, retries, scheduler behavior, and background execution.
- Redis cache keys, TTLs, invalidation, and fallback behavior.
- S3/media integrity or object lifecycle behavior.
- Environment settings, Compose services, startup order, health checks, and deployment commands.
- Observability changes including logs, traces, metrics, and correlation identifiers.
- Dependency and lockfile changes from `pyproject.toml` and `uv.lock`.

Do not claim an API or schema is compatible merely because tests passed. State the actual compatibility mechanism, such as preserved fields, an accepted validation alias, a reversible migration, or a deliberate breaking change.

## Validation reporting

Write commands exactly as executed, including relevant selectors and wrappers. Example:

```text
- `uv --cache-dir /tmp/uv-cache run pytest -q tests/core/test_example.py` — passed, 4 tests.
- `uv --cache-dir /tmp/uv-cache run pre-commit run --all-files` — passed.
- `docker compose exec -T backend alembic upgrade head` — passed against the local Compose database.
```

Do not turn a planned command into a claimed result. If a broad suite failed for an unrelated known issue, record the failure and the focused verification that passed.

## CHANGELOG.md

Update `CHANGELOG.md` only when the change is visible or operationally relevant to API consumers, administrators, deployers, or users. Examples include features, important fixes, security behavior, migrations, configuration, deprecations, removals, and breaking contracts.

Do not add routine refactoring, test-only work, formatting, or internal renames with no external or operational effect.

Preserve the existing changelog style. If it has no established release structure, add entries under `## Unreleased` using `Added`, `Changed`, `Fixed`, `Security`, `Deprecated`, or `Removed` headings as applicable. Link the detailed record without duplicating it.

## Backlog completion

For a completed task, add this field to its metadata:

```yaml
Change-Record: docs/changes/TASK-ID.md
```

The record must contain:

```yaml
Backlog: TASK-ID
```

Before setting `Status: DONE`, ensure:

1. Code and required documentation are complete.
2. Required validation passed or limitations are recorded and accepted by the task criteria.
3. The change record exists and matches the final repository.
4. The backlog task references the record.
5. Unfinished tasks and dependency relationships were reviewed and updated.

Do not mark the task `DONE` until all five conditions hold.
