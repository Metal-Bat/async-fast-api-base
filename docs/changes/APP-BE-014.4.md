# APP-BE-014.4 — Live recipient-only inbox delivery

Backlog: APP-BE-014.4
Date: 2026-10-09
Area: notifications/tasks/HTTP streaming

## Summary

Add authenticated SSE invalidations over the existing persisted unified inbox. Report and
cartable notifications remain durable when no browser is connected. Backend verification
passed the full final gate with the two existing approved SDK exceptions. Parent APP-BE-014
history remains intact; browser and Node proxy acceptance remain separate.

## Why

Clients previously needed to poll to discover new persisted notifications. Live signaling
must reuse committed notification ownership and current authorization without creating
another inbox, retaining a database transaction, or exposing report/business secrets.

## What Changed

- `GET /api/v1/inbox/events` is a static route registered before member detail. Authentication
  reuses current bearer/user/session/client checks in short sessions; recipients cannot be
  supplied by callers. Rechecks close revoked, expired, inactive or unavailable sessions.
- New notification creation stages `bpms.push_inbox_notification` through the existing
  transaction-owned outbox, including producers without optional email. Existing workers
  load committed rows and publish minimal typed references through the existing cache.
  Notification rows and existing report/cartable producers remain authoritative.
- Atomic expiring cache leases enforce three recipient connections and 200 total across
  processes. Typed signals, dedupe, lifetime, auth probes, slow sends and cleanup are bounded.
  Initial/periodic/reconnect resync reconciles missed signals through existing inbox queries.
- Actual English/Farsi Swagger distinguishes SSE success from JSON errors. BaseDTO event
  schemas forbid extra data. The handoff freezes exact events, bounds, proxy requirements
  and browser/Node/deployment limitations.
- The existing mandatory delivery-transfers profile now runs real cross-process SSE tests.
  A focused notification-push profile uses the same disposable service infrastructure.

## Architecture

### Before

Persisted unified inbox, transactional notification producers, TaskOutboxEntity, dispatcher
and Celery workers already existed. Inbox updates were queried through ordinary JSON APIs.

### After

The same transaction stages a creation invalidation, then the worker publishes to an
authenticated recipient channel after commit. Domain payloads, application orchestration,
cache adapter and presentation transport have separate ownership. Pub/sub is ephemeral;
persisted inbox queries provide resynchronization. No new persistence or scheduler exists.

### Reason

Keep notification durability independent of client connections. The installed FastAPI
native generator router discards a custom response subclass, so this endpoint explicitly
returns the bounded StreamingResponse and uses FastAPI's SSE formatter. Real HTTP header
tests protect that behavior; merely declaring a response class would lose timeout/header
enforcement.

## Compatibility

Existing inbox detail/search/unread/read contracts, operation IDs, envelopes and notification
history remain unchanged. The additive SSE endpoint deliberately has no JSON success envelope.
New BaseDTO fields are snake_case; HTTP headers retain conventional names. Existing error
codes and en/fa localization apply. No migration, dependency, environment or mise change;
DB-002's two frozen revisions are untouched. API and worker deployments must include this
task and share the existing standalone cache. Creation-only signals are supplemented by
periodic resync for read/cancel/retention changes. Frontend and Node code are unchanged.

## Validation

Test-first missing-route/module failures and later malformed-signal failures were observed
before their implementations/fixes. Real-service preparation also exposed an incorrect
test token-pair assertion, discarded native response headers and cancellation of an
in-flight test dispatcher transaction; each was corrected without suppressions or skipped
mandatory checks. One focused command omitted the existing env-file and failed setup
before creating resources; its corrected form uses the existing local configuration.
Sandboxed unit threading was interrupted and rerun with the required local capability.

Commands completed:

- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run pytest tests/apps/notifications/test_live_delivery.py tests/apps/notifications/test_unified_contract.py tests/apps/tasks/application/test_outbox.py tests/scripts/test_run_flow_test.py -q --junitxml=/tmp/notification-push-unit.xml` — 33 passed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache FLOW_TEST_PROFILE=notification-push PYTEST_ADDOPTS='-x --junitxml=/tmp/notification-push-focused.xml' uv run --env-file .envs/.backend python scripts/run_flow_test.py` — three passed, zero skipped, 79.82 seconds; owned resources removed.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache uv run ty check` — passed.
- Focused Ruff check and format check — passed, 27 files already formatted.

- `rtk proxy graphify update .` — AST extraction and graph refresh completed without model calls.
- `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check` — all 15 stages passed:
  822 default tests, one doctest, 81 mandatory service-profile cases, zero mandatory skips.
  The default suite's 178 opt-in integration exclusions remain reported separately. The
  transfer profile passed nine cases, including all three real-service SSE cases. Hooks,
  types, formatter, lint, security and secret scans passed.

Result: PASS / VERIFIED_WITH_EXCEPTION. The full gate's start/end source fingerprints
matched, including untracked source; only completion documentation changed afterward.
The private complete report/logs are retained under temporary directory
`app-be-check-2gkwbjz0`; the sanitized durable summary is
[notification-push-verification.json](../delivery/notification-push-verification.json).
The two exact approved D07 SDK exceptions remain the only warning exceptions. No browser,
Node proxy, deployment or user acceptance is claimed.

## Backlog Impact

Enabled:

- APP-FE-012 can consume the separately documented live transport; APP-BE-016's existing
  report producer reuses it without another report/inbox implementation.

Blocked:

- Browser/Node/deployed acceptance remains with its frontend/operator owner, not this
  backend extension. No backend completion blocker remains for APP-BE-014.4.

Superseded:

- None. Existing APP/CONS IDs, decisions and historical evidence are preserved.

Conflicts:

- None requiring new approval. All unfinished delivery/follow-up/consistency tasks were
  reviewed for relationships; this concrete feature belongs to APP-BE-014, not a duplicate
  CONS task. D07 and DB-002 remain the current recorded decisions.

## References

Commit: None (uncommitted work)

Pull Request: None

Additional notes: [notification push handoff](../delivery/NOTIFICATION-PUSH-HANDOFF.md),
original completion, canonical backlog,
[approved decisions](../delivery/approved-decisions.json).
