# APP-BE-028.UX02 — Refresh internal event locks after concurrent process updates

Date: 2026-10-28. Status: DONE_SCOPED_LOCAL_WORK / VERIFIED_WITH_EXCEPTION (exact D07 SDK policy).

The mandatory transfer profile found a real seeded-review claim failing with
StaleDataError: the session cached process version 10 while the locked database
row had advanced to version 17. Work-item optimistic refs were current; this was
an internal ID-based event serialization read, not a stale client command.

A controlled real PostgreSQL two-session regression reproduces the same failure
with versions 10 and 11 before the repair. ProcessEventService.append now selects
the current process FOR UPDATE with populate_existing, through the existing
transaction. Normal autoflush and ORM write-version guards remain enabled. The
regression passes and requires consecutive unique event sequences after another
writer commits. Client work-item/process refs, authorization, outcomes, atomic
writes, locks and exact command replay are unchanged. No retry, swallowed error,
unlocked update or alternate event engine was introduced.

The regression is mandatory in the existing delivery-transfers profile. Its
controlled red/green, the original 60-pass/one-failure transfer evidence, complete
transfer rerun and final native gates are retained in the peer frontend
`artifacts/integration-2026-10-28/`. Current unchanged-source final acceptance is
exclusively that directory's completion.json and archived reports; a missing,
partial, stale or failing receipt is incomplete. The existing exact D07 SDK
policy remains VERIFIED_WITH_EXCEPTION, not strict exception-free/demo or
hosted/deployed/manual/user acceptance. Producer provenance and graph refresh
must match the repaired source. No private payloads or credentials are retained.

Pull Request: None

## Actual scoped closure

The complete preclosure backend mise run check passed all 16 unchanged stages: 1057 default tests, one doctest and 153 mandatory service cases, zero required skips and zero emitted diagnostics. The exact two D07 SDK exceptions remain; this is not strict exception-free/demo readiness. Source identity b6d34ad4de9689ea2b1711d6c6bec832aa8b36a4c5e3854d7ea5f3cdd6cc8ac1 matched the working files before closing these records. The peer archive is `artifacts/integration-2026-10-28/backend-preclosure-verified/`. All 63 current real-service Firefox scenarios separately passed (46 workflow/authoring, 8 Calendar, 9 Agent). Local source fingerprints and exact actual producer contracts matched; no live provider or human approval is substituted.

The unfinished-only backlog removes this completed child, retaining its ID/history here. Documentation closure requires a fresh complete final gate; the final current-source receipt and archived logs in the peer completion.json exclusively establish that final outcome. Parent hosted, immutable release-pair, deployed, live-provider, manual and product-owner acceptance remain open.
