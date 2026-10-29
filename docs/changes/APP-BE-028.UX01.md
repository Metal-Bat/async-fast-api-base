# APP-BE-028.UX01 — Notification fanout and human claim lock compatibility

Backlog: APP-BE-028.UX01
Date: 2026-10-25
Area: notifications/application and connected workflow acceptance

## Summary

Notification fanout retains recipient serialization while allowing concurrent
human commands to hold foreign-key key-share locks. Atomic claim, current refs,
recipient authorization and exact command replay remain unchanged.

## Why

The complete backend gate retained 58 transfer passes and a Persian two-reviewer
race returning 200/503 instead of 200/409. Safe PostgreSQL diagnostics identify a
USER/PROCESS_INSTANCE deadlock. One fanout transaction can already hold a process
foreign-key lock when it locks the next recipient. A claim holds that recipient's
foreign-key lock before appending its serialized process event.

## What Changed

- Existing stage_notice uses PostgreSQL FOR NO KEY UPDATE for its recipient,
  serializing notices and identity/preferences changes without blocking FK reads.
- A controlled real PostgreSQL overlap holds the first notice's process FK lock,
  waits for the claim to block, then stages its claimant's notice. It requires two
  persisted notices, one claim, stale loser rejection and unchanged exact replay.
- The existing authenticated en/fa race remains unchanged, and the new regression
  belongs to the existing required transfer profile. No retries or error remapping.

## Architecture

### Before

An exclusive recipient key lock formed a cycle with a claim's process event lock.

### After

The existing transaction owners use compatible FK/recipient lock modes.

### Reason

Remove the demonstrated lock cycle without a new queue, claim engine or policy.

## Compatibility

No database migration, public fields, routes, error codes, permissions, current refs
or replay payloads change. Existing user and published workflow data are preserved.
The authoritative producer identity and consumer intake must qualify this source.

## Validation

The controlled regression fails with DeadlockDetectedError before the production
change. After it, the controlled case and unchanged en/fa authenticated race pass
(three cases, 63.66 seconds) on owned services. New persistence assertions are also
required in the final transfer profile. Touched Ruff and types pass.

The final paired/browser receipt, complete backend/frontend gates, native exits,
source comparisons and retained failures belong to the frontend receipt
artifacts/remaining-2026-10-25/completion.json. An absent/partial/failing receipt is
incomplete. D07 remains VERIFIED_WITH_EXCEPTION, never strict or demo readiness.

## Backlog Impact

Enables the current APP-BE-019.UX02 / APP-FE-024 full verification. APP-BE-028's
historical completion is preserved. No broader parent or hosted/deployed/manual/
user acceptance closes through this bounded repair.

## References

Commit: None
Pull Request: None
Safe failure categories and relation names only are retained; no private business
payloads, credentials or provider requests were collected for this diagnosis.


## Scoped backend completion — 2026-10-25

The bounded backend repair is DONE under VERIFIED_WITH_EXCEPTION (the exact two
D07 SDK exceptions). The complete backend mise run check passes all sixteen
stages: 1,032 default tests, one doctest and 142 mandatory service cases; zero
mandatory skips and emitted diagnostics. The 233 documented default opt-in
exclusions remain listed separately. Start/end maintained-source identity is
unchanged and matches the native report's file inventory.

The corrected source pair separately passes all 44 actual browser/service
scenarios, exact live API agreement and zero browser/service diagnostics. Producer
contracts and immutable pins retain their recorded boundaries. The controlled
notification overlap additionally verifies both persisted recipient notices.

Evidence: frontend artifacts/remaining-2026-10-25/backend-check-third/,
backend-third-source-comparison.json and paired-workflows-lock-final/. Failed
first/second gates and controlled deadlock red are retained. Final documentation
closure receives a fresh complete gate before final acceptance; its actual result
and the still-separate final frontend gate belong to completion.json. Missing,
partial or failing final evidence is incomplete. This is neither strict
exception-free/demo readiness nor hosted/deployed/manual/user acceptance.

The unfinished-only backend backlog removes this completed child, retaining its
stable ID and history here. Parent APP-BE-019/APP-FE-024 and other unresolved
feature/assistant/consistency owners retain their current status.
