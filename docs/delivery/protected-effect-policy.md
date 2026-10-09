# C12 pilot protected-effect policy for owner review

Policy key: purchase-human-approval/1. Applies only to newly published workflows that
select registered sandbox.order.create/1; existing diagnostic connection.status and old
published pins retain their declared behavior.

Protected operation: sandbox.order.create/1. Its canonical typed order payload must be
approved by a declared HUMAN_TASK completion action with outcome approve. Evidence binds
workflow version/checksum, named approval step, completed work item/actor and payload hash.
An AI result, read-only tool approval, generic task completion or another outcome cannot
satisfy this requirement. Correction or changed relevant payload requires fresh approval.
Exact committed-action replay remains idempotent.

Publication rejects every conditional/default/normal/review bypass and parallel route
that lacks the declared approval fence. Cross-subprocess approval composition is rejected
until explicit child policy/evidence is supported; it must never be inferred. Runtime
checks current process state and matching committed evidence before staging and before
protected provider dispatch. No self-approval prohibition or quorum is added.

Execution authority: retain existing publisher-bound authority with a dedicated ordinary
(non-superuser) demo publisher. Current capability, exact connection/version and secret
pins are rechecked at dispatch. Offboarding/revocation/rotation fails closed; no substitute
principal, current credential fallback or durable service identity is introduced.

Sandbox order creation and explicitly registered cancellation are local disposable HTTP
operations with real receipts. Named vendors, production purchases and paid/live AI are
separate opt-in approvals. This proposal does not authorize those actions.

Owner approval: PENDING. APP-BE-021 requires the exact mapping to be frozen; APP-BE-022
requires the explicit D04 principal decision. Independent template/review work proceeds
while this decision is pending.
