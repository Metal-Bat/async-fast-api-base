# Notification live delivery — APP-BE-014.4

Contract frozen before implementation: 2026-10-09. Backend verification: VERIFIED_WITH_EXCEPTION.
The original APP-BE-014 completion and historical evidence remain unchanged.

## Endpoint and authentication

`GET /api/v1/inbox/events`, declared before `/inbox/{ref_id}`. Requires the existing
`Authorization: Bearer <access_token>` and active user, session and client authorization.
No query parameters, user_id, body or token-in-URL authentication. Optional `Last-Event-ID`
is bounded to 256 characters and is a reconnect hint only; it grants no access and is not
a replay cursor. Native browser EventSource cannot supply the required bearer header:
use an authenticated streaming fetch or an authenticated Node proxy using the existing
session/token boundary. Do not invent cookie authentication on this backend endpoint.

Success is `text/event-stream`, outside normal JSON envelopes. Headers: `Cache-Control:
private, no-store, no-transform`, `X-Accel-Buffering: no`, `X-Content-Type-Options: nosniff`,
plus existing request correlation and language headers. Authentication, validation, rate-limit
and service errors before streaming use existing JSON error envelopes. After headers, an
authorization or service failure closes the stream; no raw error or private data is emitted.

## Events and resynchronization

- `inbox.changed`: `{"schema_version":1,"notification_ref_id":"<current opaque ref>"}`.
  SSE id is the same notification reference. No subject, business payload, user identifier,
  report password, private file URL or exception is included.
- `inbox.resync`: `{"schema_version":1,"reason":"connected"}`. Reasons are `connected`,
  `reconnected`, `periodic`, `event_limit` and `lifetime`. No id, so it does not replace the
  last notification event id. Retry hint: 3000 ms on the initial resync.
- Heartbeat is a comment (`: heartbeat`), not a notification or JSON envelope.

Subscribe before the initial resync, then use existing `POST /api/v1/inbox/search` and
`GET /api/v1/inbox/unread` to refresh the persisted source of truth. Resync every 60 seconds
and on every reconnect, including when Last-Event-ID is present. There is no guaranteed
live replay, ordering or exactly-once delivery. Missed Redis signals never remove inbox rows.
Coalesce refreshes; deduplicate notification references within a connection and in the client.
An id is not a read command: viewing a signal does not mark the notification read. Fetching
details continues to apply current recipient and target authorization.

## Bounds and transaction boundary

Heartbeat and authentication use a nominal 15-second cadence; also recheck before emitting
a notification. Authentication probes time out after 3 seconds; an in-flight send is bounded
to 5 seconds. Revocation is checked periodically, not instantaneously. Normal renewal emits
`inbox.resync` with reason `lifetime` around 290 seconds, reserving time for authorization,
send and EOF before the hard 300-second transport deadline. Maximum 256 received signals and
3 simultaneous streams per recipient / 200 per cache namespace across API processes.
Admission uses atomic Redis leases with a 330-second crash expiry. Slow sends time out
after 5 seconds. Individual signal payloads are bounded to 1024 bytes; malformed signals
and duplicates count toward the connection event limit. References are bounded URL-safe
strings; unexpected payload fields are rejected. No unbounded application queue or database
session/transaction lives with the connection. Cleanup releases subscriptions, clients and
leases on disconnect, timeout, lifetime expiry or cancellation, with a shielded 3-second
cleanup budget; unreachable/crashed leases expire. Deduplication memory is bounded by
the 256-signal limit. The existing standalone cache is required; this two-key admission
script is not a Redis Cluster deployment contract.

The same transaction that creates a notification stages `bpms.push_inbox_notification`
through the existing TaskOutboxEntity. The existing dispatcher/worker reads committed rows
and publishes only a minimal reference to a recipient-specific channel in the configured
cache. Rolled-back rows/outbox commands cannot publish. Optional email delivery and existing
process fanout remain independent. Duplicate worker publication is harmless invalidation.
Cache failures retry through the existing task policy; the durable inbox remains usable.
The new task uses the existing automation queue and five bounded retries for Redis/network
failures. Creation is signaled; read, cancellation, retention and other later state changes
are reconciled by persisted queries and periodic resync. There is no second inbox or store.

## Node proxy requirements

Authenticate through the existing frontend boundary and forward its server-held access token;
never accept a caller recipient override. Forward Last-Event-ID and Accept-Language. Stream
chunks immediately without collecting the body, JSON parsing, compression or proxy buffering.
Preserve text/event-stream, cache and buffering headers; flush headers. Propagate downstream
abort to the upstream fetch, honor backpressure and bound proxy connections. Proxy/read/idle
timeouts should allow at least 30 seconds of idle time and the 300-second bounded lifetime;
reconnect with backoff
and resync rather than treating EOF as lost notifications. Never log tokens or stream bodies.
No frontend or Node code is changed by this backend task.

## Errors and client examples

Before headers, existing JSON envelopes and public error values apply: 401 for invalid,
expired or revoked credentials or an inactive user; 403 for denied client authorization;
404 for a missing user; 422 for any query parameter or an
oversized Last-Event-ID; 429/code 1006 for connection limits; 503/code 1098 for unavailable
signaling or an authorization probe timeout. Existing unexpected-service errors retain
their safe 500 behavior. After headers, errors or authorization loss close the stream.
OpenAPI documents JSON errors separately from the SSE success body and exposes typed event
schemas through `x-sse-event-schemas`. English/Farsi descriptions retain the same machine keys.

Illustrative wire output (the reference below is a placeholder, not a valid resource):

```text
event: inbox.resync
retry: 3000
data: {"schema_version":1,"reason":"connected"}

event: inbox.changed
id: opaque_reference
data: {"schema_version":1,"notification_ref_id":"opaque_reference"}

: heartbeat

```

An authenticated local diagnostic client may use `curl -N` with the bearer header. Tokens
belong in headers, never URL parameters. On each resync, replace the inbox query results
and unread total; do not append the small invalidation as if it were a complete inbox row.
Current opaque references can change when row versions change. Deduplicate signals without
promising one signal per logical notification across reconnects.

## Evidence and limitations

Focused verification passed: 33 unit tests (nine new live-transport cases) and three
real-service SSE integration tests, with zero integration skips. The latter completed in
79.82 seconds and removed its owned database/services. Report and cartable completions,
rollback, duplicate dispatch, offline/reconnect resync, outsider denial, disconnect cleanup,
revocation, expired tokens, in-stream expiry/inactive users, global/recipient leases and
heartbeat/lifetime renewal were exercised.

Full final `rtk proxy env UV_CACHE_DIR=/tmp/app-be-uv-cache mise run check` passed all
15 stages: 822 default tests, one doctest and 81 mandatory service-profile cases. The
default suite reports 178 opt-in integration exclusions; every mandatory profile had
zero skips. The mandatory worker/transfer profile passed all nine cases, including
the three SSE service cases. Formatter, lint, types, security, secrets and hooks passed.
The two existing D07 SDK exceptions remain explicitly VERIFIED_WITH_EXCEPTION; there
are no new warning filters, scanner exceptions or mandatory test exclusions.
Start/end source identity matched, including tracked and untracked files; only completion
documentation changed afterward. Sanitized evidence is in
[notification-push-verification.json](notification-push-verification.json), with the
[change record](../changes/APP-BE-014.4.md). Failed/partial preparation is retained there
and in the change record. AST graph refresh completed without model calls.
Backend tests are not browser, Node proxy, deployed or user acceptance.

The service profile runs a separate real HTTP API, Celery worker, cache and private storage
against a freshly migrated, harness-owned PostgreSQL database. Test API heartbeat/resync
timers are accelerated; the production bounds also have deterministic transport tests.
API lifespan is disabled in this focused subprocess after the harness initializes its
owned services; production startup/deployment acceptance is not inferred from this profile.
Shared/production data, migrations, dependencies, environment and frontend files are unchanged.
