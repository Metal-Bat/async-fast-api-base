# Delivery record templates

These are blank templates, not evidence. Fill from actual actions. Store detailed completion at docs/changes/TASK-ID.md; keep private raw logs/credentials out of Git. Preserve the existing change-journal headings when used in the backend.

## Task intake

```text
Task ID:
Current repository SHA / dirty-tree digest:
Peer SHA / contract hash (if relevant):
Existing instructions/skills read:
Existing code and tests reused:
Exact uncovered delta:
Dependencies verified:
Decision blockers:
Proposed files to edit/add:
Relevant C contracts / A scenarios:
Initial check command/result/warnings/skips:
Estimate before / after intake:
```

## Producer-to-consumer contract handoff

```text
Producer task / SHA:
Consumer task / expected minimum version:
Contract IDs and ledger version/hash:
Existing endpoint reused or new additive endpoint:
Exact path / method / operation ID:
Request / response / envelope / headers:
Required vs optional / missing vs null semantics:
Permission and resource/client/actor checks:
Current refs after mutation:
Command key scope / unchanged replay / different-payload conflict:
Safe error codes, JSON pointers, forbidden/stale/uncertain behavior:
Binary, queued, streaming or paginated behavior:
Schema migration/head and old-client compatibility:
Localized examples and fixture locations:
Actual verification commands/results:
Required services/seed/template/client versions:
Open limitations and consumer action:
```

## Verification evidence

```text
Task / capability:
Evidence level (implemented / verified_local / verified_integrated / demo_ready):
Exact repository pair and dirty state:
Tool versions / lock hashes / OpenAPI hash:
Environment identity (non-secret; disposable or deployed):
Seed/default/notification/help-manifest version:
Commands with start/end and exit code:
Warning count by tool / browser / service:
Expected negative-test diagnostics asserted:
Passed / failed / skipped / xfailed / not-run:
Required scenario IDs and exact tests:
Actual service/browser/manual checks:
Observed state/receipt/pin assertions:
Sanitized artifact paths and checksums:
Unavailable tooling / limitations:
```

## Risk register row

```text
Risk ID | Description | Affected task/capability | Trigger
Likelihood/confidence rationale | Impact | Mitigation | Contingency
Owner role/name (TBD when unknown) | Status | Evidence/next review
```

Initial risks to track: D01 migration incompatibility; schema/UI drift; seeded privilege escalation; stale locator/ref misuse; raw-JSON scope reappearing; lost external acknowledgment; defaults touching active pins; duplicate notifications/reminders; privacy in support records; clock/calendar ambiguity; zero-warning suppression; library-version/license drift; missing manual accessibility evidence; insufficient review capacity.

## Decision record

```text
Decision ID / date:
Question:
Existing contract or instruction:
Alternatives:
Recommendation and tradeoffs:
Affected task IDs:
Proposed vs accepted (not inferred):
Actual decision maker / approval evidence:
Migration/compatibility/rollout consequences:
Validation and revisit condition:
```

## Demonstration acceptance record

```text
Demo ID / date / operator:
Exact code pair / environment / client release:
Scenario and template/default versions:
Actors/roles used (no credentials):
Actual services and system endpoints by safe alias:
AI: deterministic simulator or named approved live provider:
Integration: local HTTP sandbox or named verified vendor sandbox:
Scenario evidence A01–A26:
Browser/manual/performance evidence and supported profile:
Unexpected warnings/errors:
Default restore and demo-reset runs:
Final outcome/receipt and pinned-version assertions:
Support incident/reconciliation evidence:
Known limits / unresolved gates:
Demo-ready decision:
Deployment evidence (only if deployed):
Actual user acceptance/signoff (only if obtained):
```

## Backlog update discipline

For an APP task, keep the status in its main backlog authoritative. Root backlog entries link to the supplement rather than duplicate the whole task. Keep old task IDs and old completion evidence intact. Common ledger/rules/timing companions and embedded appendices carry a shared version; if changed, synchronize their exact content and hand off the new hash to the peer. Never add a completion claim simply because a file was created.
