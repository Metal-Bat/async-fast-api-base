# C07 / APP-BE-014 unified inbox and delivery

The additive `h014_unified_notifications` revision follows `g009_personal_items`.
It preserves existing notification IDs, content, read timestamps and all delivery rows;
case FKs become nullable for non-case notices, and target_kind/target_id/event_id plus
kind/shape and unique event/recipient/template/version constraints are added. Previously
applied initial/workspace migrations are unchanged. Downgrade refuses retained non-case
rows rather than silently discard them; operational archival needs a separate decision.

Legacy `/api/v1/notifications/search`, report, detail and read keep NotificationDTO's
required request_ref_id/process_ref_id and existing envelopes. Search/report exclude
non-case rows. Non-case detail through the legacy serializer is 404. Revoked/unavailable
case destinations redact subject/content while preserving the valid old case shape.
Legacy report remains paginated search, not a background export.

New `/api/v1/inbox` exposes POST search/report, GET unread, GET /{ref_id}, and POST
/{ref_id}/read with `{}`. All require a live authenticated recipient and private,
no-store responses. Other recipients fail 403; missing/deleted notices fail 404;
read requires a current ref and stale writes fail 409. A read never executes a workflow
command. Query reuses the existing typed search/filter/order/page/size contract plus
unread (true unread, false read, missing/null both). Unread total counts live ACTIVE
unread rows, including unavailable redacted destinations. Page ties use ID ordering.

Inbox schema_version=1 discriminates case, work_item, ai_approval, report and account.
Every opening resolves current refs through existing request/work-item/report/self
owners and current capability checks. Unavailable/cancelled/expired/deleted/revoked
objects expose no content or target ref. Route keys are fixed; URLs, raw credentials,
case bodies and expiring public refs are never persisted as the canonical target.
Calendar and support variants resolve their live producers under C08/C09; operation
remains unavailable until its separate producer exists. The new endpoint/version signal permits feature negotiation without widening
legacy required fields. The frontend repository has not been modified or verified.

Production slices:

1. Schema and projection extend the existing notification owner, not a parallel inbox
   or delivery store. Retention reuses existing content-expiry policy and cancels later
   external sends for unavailable targets. Retained notice identity remains auditable.
2. Existing ProcessEventService appends MAP-01–06 intents in the business transaction.
   Only opaque event IDs enter the existing TASK_OUTBOX. The registered fanout task
   resolves at most 100 recipients per invocation with stable UUID cursors, current
   candidate/group membership and owner authorization. Duplicate invocation converges
   on the same notification; continuation outbox messages are also deduped. Correction
   notices resolve the engine-created correction task, not the reviewer’s old task.
   Closed availability occurrences do not generate stale actionable notices.
3. Account audits (MAP-14), report READY/FAILED commits (MAP-09), and AI approval
   staging (MAP-12) stage recipient rows in their owning transactions. Admin password
   resets notify the affected account, retaining the actor in security audit. A dedicated
   AI approval notice owns its occurrence instead of also issuing generic human work.

MAP-10/11 now stage source-owned calendar/work reminders through APP-BE-017; MAP-13
stages one bounded authorized support fanout per episode through APP-BE-015. MAP-07/08
still await their APP-BE-024/023 producers. New next human participants receive actual MAP-02
availability rather than invented recipient lists. Notification-created audit events
are not notification triggers, so no incident/delivery feedback loop is introduced.

Templates are code-owned in notifications/data/application_map.json and synchronized
with notification-map.json. Version 1 renders en/fa, 120-character allowlisted labels,
HTML escaping and fixed bounded subjects. Generic localized resource labels minimize
private snapshots. Locale follows self preferences at staging, with existing en defaults.
New notifications.email_enabled defaults false; missing groups preserve settings and
explicit null resets this group. Mandatory security/AI approval ignores optional opt-out;
in-app rows remain enabled. Both optional preferences and target authority are rechecked
before external send.

External channel uses the existing EMAIL/https_notification gateway provider and
bpms.deliver_notification worker. APPLICATION_NOTIFICATION_CONNECTION_REF is an explicit
operator-selected verified active connection; no eligible address/connection means no
email delivery row, not a false receipt. INTEGRATION_TLS_CA_FILE optionally supplies a
trusted CA bundle; otherwise normal system trust applies. TLS verification stays enabled.
Delivery has existing bounded retries, destination fingerprints, provider idempotency
keys and terminal states; provider uncertainty is retained as RETRY with safe codes.
The owned real-worker test verifies a local HTTPS gateway receipt and duplicate handling.
It does not attest downstream SMTP, a paid provider, external delivery or deployment.

Generated en/fa OpenAPI and inbox-contracts.json in wave-four freeze methods, discriminated
schemas, authorization, private headers and mapped producer limits. Actual verification
is recorded in through-014-verification.md. D01 and the two D07 SDK exceptions are approved;
the exact ten-entry secret-baseline review is owner-approved. See through-020-verification.md
for the additional actual reminder worker checks.
