---
tags: [operations]
---

# BPMS recovery, retention and deployment

Use this with [observability](bpms-observability.md) and the
[integration secret recovery contract](../architecture/integration-secrets.md).

## Inspect and recover

Administrators inspect the existing process detail and timeline first. The timeline includes
current positions, failed attempts, actor/correlation evidence and immutable version pins.
`POST /api/v1/processes/{ref_id}/scheduled-actions/search` accepts `page` and `size` (maximum 100)
and returns a deterministic page of timer references, state, due time, delivery attempts and safe
error codes. Both operational endpoints require an authenticated, non-deleted superuser;
granting `processes.recover` alone does not grant recovery authority.

`POST /api/v1/processes/{ref_id}/recover` accepts:

```json
{"command_key":"incident-42-resume","action":"resume","reason":"OPS-42"}
```

Use a non-sensitive ticket/reason code of at most 64 characters, containing letters, digits,
periods, underscores, colons or hyphens. Never send personal data or credentials in reason codes.
The supported actions are:

| Action | Required state | Result |
| --- | --- | --- |
| `resume` | Paused process with one current position | Continue the existing engine; a waiting position remains waiting. No fabricated human/event output is accepted. |
| `retry` | Failed process and failed/timed-out current step, below its published retry limit | Invoke the existing typed handler/outbox retry path. |
| `retry_timer` | Failed scheduled action, with its exact execution and process still waiting | Add one delivery allowance and make the action pending. Supply `scheduled_action_ref_id`. |

Process and timer references are optimistic versions. A successfully committed duplicate command
is recognized before checking the now-stale process version. Reusing a command key with a different
actor, action, reason or target returns conflict. Concurrent commands serialize on the process;
state changes and `operation.recovered` audit evidence share one transaction. A rolled-back
operation has neither state changes nor an audit event. Command keys are hashed for storage.
Timer attempt numbers never reset, so old dispatch identities cannot become current again.
A failed-step retry reuses its existing wait registration, invalidates its previous lease and
adds a fresh delivery budget; repeated exhaustion commands have distinct delivery identities.
Reopening a process clears its terminal timestamp before any autoflush.

A process with multiple current positions cannot be retried by guessing a branch. Terminal
processes, live timer leases, human completions and ambiguous external compensation cannot be
force-advanced by this endpoint. For compensation, stop/drain the responsible worker and reconcile
the provider result first; retain the incident evidence and use the existing trusted compensation
service under controlled operator access. Never rewrite runtime rows or replay an external effect
merely because a delivery acknowledgment is missing. A failed timer already propagated into a
failed process uses normal process retry, subject to its retry budget.

Outbox publication retries automatically with the original message identity. Expired timer and
worker leases use the existing scheduler recovery. Inspect broker/worker health before invoking
recovery; a missing queue consumer is an infrastructure problem.

## Retention

Schedule `system.cleanup_task_history` through the existing periodic-task API. Each invocation
processes at most 500 rows per disposable task table (trusted internal callers may choose 1–1000).
Run more frequently if that throughput is insufficient; monitor backlog instead of increasing to
an unbounded transaction. No new scheduler is introduced.

| Data | Policy |
| --- | --- |
| Published definitions, submitted forms, business requests, process events/transitions, work-item actions and compensation evidence | Retain; no automatic deletion. |
| Generated configuration/identity history | Retain. The cleanup job no longer uses `HISTORY_RETENTION_DAYS` to delete these records. |
| BPMS task executions, outbox and associated successful deduplication claims | Retain as durable runtime/replay evidence. This intentionally trades storage for safety. |
| Other task executions | Delete only terminal `SUCCESS`, `FAILURE`, `REVOKED` records whose finish time exceeds `CELERY_RESULT_RETENTION_DAYS`, and which no step attempt references. |
| Other published outbox messages | Prune after the configured task retention period; unpublished messages remain. |
| Other successful task deduplication claims | Prune after claim expiry. Running claims remain under lease recovery. |
| Draft forms/requests | Retain while active; user cancellation/abandonment is explicit. Do not infer abandonment from age. |
| Upload bytes | Existing bounded cleanup uses `ABANDONED_UPLOAD_RETENTION_HOURS`, locks candidates, and rechecks active draft/submitted attachment references before deletion. |
| Notification text | Existing notification retention redacts expired content while retaining delivery metadata. |

Back up before any separately approved business-data archival policy. Time partitioning and
business-record deletion are not implicit consequences of task retention.

## Limits and secrets

The existing tests verify schema document/depth/reference limits, expression compile/runtime work
budgets, typed handler input/output boundaries, attachment item/byte rules, upload size/rate limits,
private media authorization, integration endpoint allowlists and encrypted-secret failure behavior.
Upload rate limiting fails closed when the cache is unavailable. Authenticated recovery is bounded
by engine retry budgets and timer recovery grants one additional delivery per explicit command.

SQL logging now disables automatic echo and hides bound parameters even if an operator raises the
SQLAlchemy logger level. The existing localized error mapper returns safe public error codes,
not the internal recovery exception text. Metrics and process events use their existing allowlists.
Keep business values in bound parameters; literal SQL and operator-injected diagnostic log messages
are outside parameter redaction. Credential keyrings and ciphertext remain separate from workflow
JSON, database snapshots, broker messages and ordinary logs.

## Consistent backup and restore

For the supported quiescent backup procedure:

1. Stop accepting mutations, stop the scheduler, drain workers, and suspend upload cleanup. Confirm
   there are no in-flight storage mutations or ambiguous provider operations.
2. Take a PostgreSQL custom-format dump at the current Alembic head. Back up all retained private
   object bytes and integrity metadata referenced by that snapshot, preserving object keys.
3. Back up every referenced encrypted credential version, its file permissions, endpoint allowlist
   and runtime configuration. Escrow encryption keys and the application reference-encryption key
   separately under restricted operator access. Record one backup-set identifier and checksums.
4. Restore into an isolated database and private bucket before redirecting traffic. Restore
   ciphertext files and provision the corresponding keyring separately. Run migration/drift checks;
   verify immutable workflow/form pins, submitted attachments and SHA-256 metadata, actor access,
   and a governed connection before resuming dispatch.
5. Reconcile external effects since the recovery point. A database restore cannot roll back a
   provider action. Resume scheduler/workers only after that reconciliation, then reopen writes.

`tests/integration/test_bpms_restore.py` exercises a real `pg_dump`/`pg_restore` into a new database,
restores a private object into a new bucket, verifies the submitted attachment and pinned form,
restores credential metadata/ciphertext, rejects a wrong key, and completes the restored timer
workflow. It requires `RUN_BPMS_RESTORE=1` and a source database named `bpms016_*`. All generated
restore databases/buckets are removed. This verifies the procedure, not a production RPO/RTO;
measure those against the deployment's actual data volume and backup frequency.

## Worker rollout and schema compatibility

This change retains Alembic head `d7f3a9c1e204`, published handler versions and existing task
argument formats. Supported rolling replacement is between application builds that retain those
same contracts on that schema. Mixed incompatible handlers or older database heads are unsupported;
check `alembic current`, `alembic heads` and `alembic check` before enabling dispatch.

Rebuild the backend image because `/start-worker` is copied into it. The general worker now consumes
both `CELERY_DEFAULT_QUEUE` and `CELERY_AUTOMATION_QUEUE`; the reporting worker remains isolated.
Retain the Compose 21-minute worker stop grace (longer than the default 20-minute hard task limit).
If hard limits change, adjust the grace period accordingly. Send TERM for warm shutdown, wait for
active tasks to finish, then replace the worker. Retain at least one consumer where availability
requires it. The outbox/broker retain work during a full consumer gap.

The real-worker test starts a task, sends TERM while it is active, verifies successful drain,
commits/publishes work while the worker is down, restarts it, and verifies delivery plus duplicate
side-effect protection. Other worker tests exercise actual soft/hard timeouts, retries and lease
recovery. Migration round-trip and drift tests use a separate disposable database; never run a
base downgrade against application data. This task adds no migration requiring an expand/contract
window.

## Measured query plans

The rollback-only volume fixture adds 25,000 events to a hot process, 25,000 audit rows and 50,000
outbox rows (100 pending). Queries use production event/history ordering and outbox lock ordering.
On the local PostgreSQL fixture on 2026-09-27:

| Query | Rows returned | Execution time | Existing access path |
| --- | --- | --- | --- |
| Latest process events | 100 | 0.048 ms | `uq_PROCESS_EVENT_sequence` |
| Entity audit page | 100 | 0.072 ms | Changed-at index with bounded ordering |
| Next due unpublished outbox row | 1 | 0.097 ms | Published-at index, small in-memory sort and row lock |

These are warm local measurements, not production latency guarantees. No new index or partition
was justified by this fixture. Rerun `test_bpms_volume.py` with `RUN_BPMS_VOLUME=1`; use
`BPMS_PLAN_OUTPUT` to preserve JSON plans. Re-measure with actual entity distribution, deep-page
queries, backlog skew and storage latency before introducing partitioning or additional indexes.
