# APP-BE-009 — Private saved views and canonical favorites

Backlog: APP-BE-009
Date: 2026-10-08
Area: users personal state / designer resource links

## Completion — 2026-10-08

Status: DONE. Result: VERIFIED_WITH_EXCEPTION. The complete thirteen-stage `mise run check` passed after D01 additive migration approval, D07 exact SDK exceptions and explicit approval of the ten exact non-secret baseline entries. The baseline update preserved all scanner rules and existing entries.

Observed commands, original failures, required service counts, tested source hash and private report are linked in [through-014-verification.md](../delivery/through-014-verification.md) and [through-014-gate.json](../delivery/through-014-gate.json). No required-profile test was skipped. This closes the backend task; later producers, frontend/browser acceptance and deployment retain their own task boundaries.

## Preparation history

The following original sections preserve earlier failures and pending-approval observations. Their PARTIAL/BLOCKED statements describe preparation and are superseded by the observed completion above.

## Summary

Private saved list presets preserve validated filters, order, columns and page size;
favorites persist canonical identity and resolve current authorized labels/refs.
Implementation, the default suite and required real-service profiles passed.
Final completion awaits specific secret-baseline approval and a passing full gate.

## Why

Finish the remaining implementation through APP-BE-009 while reusing existing query,
identity, work-item pin and domain authorization owners. Stored revision refs would
break bookmarks; unvalidated presets could broaden searches or leak authority.

## What Changed

- `users/domain/saved_views.py`, `personal_entity.py`,
  `users/application/saved_views.py`, `personal_collections.py` and
  `users/presentation/collections.py`: self-only CRUD, bounded search/metadata history,
  explicit defaults/apply, optimistic refs, replay and compatibility recovery.
- `g009_personal_items.py`: additive personal table/history and database invariants.
- Generic history denies tables marked self-only. Preferences and personal items
  use this flag; no private queries enter admin history output.
- C04 handoff: `docs/delivery/personal-collections-handoff.md` and generated en/fa
  snapshots plus `wave-four/personal-contracts.json`.

## Architecture

### Before

Self profile/settings and durable resource resolution existed, but reusable personal
list presets and generalized canonical favorites were absent. Work-item pins already
had an authoritative personal-state owner.

### After

Users own bounded personal state. Query validation delegates to actual list models;
favorite display delegates to ResourceLinkService and each existing target owner.
No new business query engine, shared cache, actor assignment or work-item favorite
store is added. User-row locks serialize bounds/replay/default selection and partial
unique indexes enforce invariants. Dedicated personal history exposes metadata only.

### Reason

Keep authority in existing domains and make schema drift an explicit repair state,
without storing stale references or silently altering a user's query.

## Compatibility

Additive endpoints and migration on the D01-approved linear chain. JSON uses BaseDTO,
snake_case and existing envelopes/public errors. PUT is complete replacement; unknown
fields/null contract values are rejected. Defaults are explicit and versioned.
Private generic history is deliberately inaccessible; retained rows are unchanged.
No dependency/lock, worker, deployment or shared-environment reset change.

## Validation

Commands and actual results: `docs/delivery/through-009-verification.md`.
Red-first tests captured missing module/routes and the private-history disclosure;
focused DTO/service/ordinary HTTP/replay/race tests then passed. Fresh/upgrade schema
verification runs in owned disposable PostgreSQL.

Result: VERIFIED_INTEGRATED for implementation; final closure remains blocked.
The full gate passed lock/format/lint/docstrings/type/Bandit and stopped on the nine
reviewed secret-scan findings. SDK exceptions remain the two
explicit D07 approvals; nine exact secret false positives await their own approval.

## Backlog Impact

Enabled:

- APP-BE-029 once final verification allows completion.

Blocked:

- APP-BE-009 and final closure through APP-BE-009: exact baseline approval/full gate.

Superseded:

- None; existing work-item pins remain authoritative.

Conflicts:

- None; D01 is approved and both applied migrations are preserved.

All unfinished APP tasks and existing dependency edges were reviewed. Later frontend,
connected workflow, reset, hosted verification and acceptance remain separate work.

## References

Commit: None (uncommitted work)

Pull Request: None

Additional notes: `docs/delivery/personal-collections-handoff.md`,
`docs/delivery/secret-baseline-review.json`, `docs/delivery/approved-decisions.json`.
