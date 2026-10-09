# Backend handoff through APP-BE-020

## C08 — Safe support episodes

`/api/v1/support` adds authenticated `POST /client-failures`, incident search/report,
GET detail and `GET /incidents/by-support/{support_ref}`, POST history and
POST acknowledge/resolve with `{}`. Incident inspection requires current
`support.incidents.manage` or superuser authority. Reconciliation creates the permission
without granting it to existing roles. Operators explicitly assign reviewed access.
A correlation UUID grants no access; detail returns a fresh revision reference for writes.
All responses use existing snake_case success/page/error envelopes and private no-store.

Client input permits only screen_key, build, error_code and request_id. See generated
`wave-four/support-contracts.json` for the exact enums, ASCII pattern and sizes.
Ten new occurrences per actor per UTC calendar minute are serialized using the user lock.
Repeated correlations among the last 100 episode IDs do not increment the counter;
excess returns 429 (1006). Unexpected/technical 5xx failures record through an independent
transaction with a two-second bound. Expected validation, authorization and stale-write
errors do not create incidents. Failure response data contains support_persisted and
nullable support_ref; request_id remains the response correlation. Client receipts use
persisted/support_ref. An unavailable sink reports false rather than claiming durability.

Fingerprint is category/code/registered operation/actor/build. One-day episodes coalesce,
counts cap at 1000000, and resolved recurrence starts a new episode. Retention is 30 days
from episode creation; expired rows are excluded immediately and existing system cleanup
prunes batches with cascading history. Transition history contains state metadata only.
OPEN may become ACKNOWLEDGED or RESOLVED; ACKNOWLEDGED may become RESOLVED. Current-ref
conflicts return 409; missing/expired rows return 404; unauthorized inspection returns 403.
MAP-13 stages once per episode and fans out in batches of 100 to current capable operators.
Notification failures never generate MAP-13, preventing a delivery feedback loop.

New task-execution failures retain safe class/code metadata, without exception text,
tracebacks or raw task input copies. Historical rows are not retroactively rewritten.
Existing framework logs are separate from this projection. Support records never store
business fields, provider messages, credentials, prompts, attachments or exception stacks.

## C09 — Calendar and one-off reminders

`/api/v1/calendar/events`: POST create/search/report, GET detail, PUT update, DELETE,
POST history and GET reminders. `/api/v1/calendar/work-reminders/{ref_id}`: GET, PUT,
DELETE. Generated `wave-four/calendar-contracts.json` and localized OpenAPI are canonical.
Creation/update uses a bounded command_key and binds exact intent; identical replay returns
current state, changed intent conflicts. Creator-only writes require current revisions.
Personal visibility belongs to the creator; team events require current active membership
of the explicitly selected active group. There is no superuser calendar bypass. Revoked
members lose visibility; creator deletion can cancel their own inaccessible source.

Timed schedules use aware ISO instants normalized to UTC and an IANA presentation zone.
Non-UTC input offsets must match the named wall time; DST gaps are rejected and explicit
offsets resolve folds. All-day schedules retain Gregorian dates with exclusive end dates.
Nonexistent local date boundaries are rejected. Events span at most 366 days. Search uses
half-open date ranges of 1–93 days, size 1–100, at most 20 filters/10 sorts. Live authority
and overlap precede count and paging. Optional work deadlines project actual live due_at
points under requests.start and available/claimed cartable responsibility; they are
read-only and link to work_items. Manual sources link to calendar_events. History is
metadata only, bounded at 1000 transitions. Gregorian en/fa is supported; Jalali, recurrence,
invitations, provider synchronization and business-day policies retain separate scope.

Manual create/update accepts zero to three distinct offsets, 0–2592000 seconds before
start (empty disables). Work configuration accepts one to three offsets for an actual
current due_at; DELETE cancels only this actor's reminders and never changes deadlines.
Manual reminders belong to the creator; work reminders require current responsibility.
Latest 100 owned states are exposed: PENDING, SENT, CANCELLED, EXPIRED. SENT means the
in-app intent was staged, not a provider receipt. External delivery keeps the existing
notification delivery state and gateway policy.

The existing database scheduler owns clocked one-off PeriodicTask rows and durable outbox
messages for bpms.fire_calendar_reminder. Source edits/deletes/terminal or forwarded work
cancel old reminders and disable schedules in the source transaction. Fire and later
notice delivery recheck source revision/deadline, active state and recipient authority.
Retries and duplicate messages retain the same occurrence identity. Relevant occurrences
up to 24 hours late deliver once; older ones expire and record bounded non-alerting lag.
Owned PostgreSQL/Redis broker/Celery tests cover scheduler replacement, broker outage and
recovery, cancellation after enqueue and duplicate handling. No second timer loop exists.

## C10/C11 — Analytics and runtime conformance

Analytics dictionary/populations and drilldown are documented in docs/reference/responses/analytics.md and
wave-four/metric-dictionary.json. Additional real-database evidence covers the 23-hour
New York DST window, inclusive/exclusive boundaries, per-status drilldown equality,
cancelled unsubmitted unknown duration, deleted records and inactive actor rejection.
The controlled query plan remains a four-row fixture; production performance certification
belongs to APP-BE-028/031. Unavailable outcomes/receipts are not inferred as zero/success.

`tests/fixtures/delivery/runtime-controls-v1.json` and its exported identical fixture cover
all twenty supported primitive/layout kinds across create/read/edit/summary/print/correction.
The existing bpms.render/1, bpms.behavior/1 and schema dialects remain authoritative.
Pure and actual published-form/request/review/correction tests preserve false/zero/empty,
null versus missing, typed choice keys, exact canonical decimal strings, Gregorian dates,
UTC instants, nested row identities, hidden values and active-version checksums. Attachment
add/reorder/replace/remove now immediately update the canonical runtime data and current
upload references. Partial action validation now supplies schema/data in the correct order,
so formatted decimal controls can return for correction with safe pointer diagnostics.
This is backend conformance; browser rendering and peer implementation are not attested.

## Upgrade and evidence

Apply approved additive revisions i015_support_incidents and j016_calendar_events after
h014_unified_notifications. Initial/workspace migrations remain byte-identical. New support
and calendar history are private through existing generic-admin exclusion. No dependency,
lockfile or new environment setting is required. Existing scheduler/worker must load the
new registered tasks. The new delivery-through-020-test profile is a mandatory no-skip
stage in the complete fourteen-stage check; existing stages remain required.

See through-020-verification.md for actual final status. D07 permits exactly two SDK
exceptions; this work must be labeled VERIFIED_WITH_EXCEPTION after a successful gate.
The prior exact ten-entry secret baseline approval remains unchanged. Frontend, deployed
images, live vendors, paid AI, reset and full-demo acceptance remain later task boundaries.

Paired transfer limitation: complete maximum-size uploads/downloads and declared-size
preflight rejection are verified. The peer can reset an oversized sender still writing
its body after an early 413; graceful streaming rejection remains frontend acceptance
work. No peer source was modified. The real owned reminder worker uses Redis transport;
outage evidence is a refused connection followed by retained dispatch to the live broker.
