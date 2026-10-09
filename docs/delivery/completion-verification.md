# Completion work after APP-BE-020

Date: 2026-10-09. Requested scope: all remaining backend tasks through APP-BE-032.
APP-BE-001–020 and APP-BE-026 are DONE: 21 of 32 APP tasks. Eleven remain open.
This ledger records observed work, not an assertion that the whole scope is complete.

The final fifteen-stage gate passed as VERIFIED_WITH_EXCEPTION. See
[the sanitized gate report](completion-gate.json). It records 808 default passes,
173 documented opt-in exclusions, one doctest and 76 required service-profile passes
with zero required skips. Counts include repeated regressions across profiles.

Tested tree SHA256: `bc16621e53dc5ab3d341c2d44554052d8beb9374ac05df87996b92f0ec678748`.
Code/configuration/fixture SHA256: `fb9dce462944a3458f652b36e5bfb1c6db48b32183b48f0590c8f93179e352e0`.
Only documented closure/evidence files changed after the gate; tested source, tests,
configuration, lockfile and security controls retain that code digest. Original
applied migrations remain byte-identical. Migration head: `k026_workflow_restore`.
The private report is `/tmp/app-be-check-hvf419d0/report.json`.

APP-BE-026 now implements read-only exact-baseline previews, authorized atomic apply,
command replay and separate draft layout reset using existing workflow/workspace
owners. The additive migration preserves the established lineage. See
[restoration contract](workflow-defaults.md).

Focused checks: three contract tests pass; the final owned PostgreSQL restoration/
workspace/library profile passes twelve tests. It verifies concurrent
same-command apply, stale workspace rejection, published graph preservation, mixed
form/workflow reuse, unchanged actual case/submission/process pins, interrupted-write
rollback, explicit source requirement, safe dependency blockers and permission
revocation, retired baseline/target preservation and safe rejection of an oversized
published template before token issuance.

First strict gate `/tmp/app-be-check-r_9p1_fs/report.json` stopped on generated response
reference drift: 806 default tests passed, one failed and 172 documented opt-in tests
were excluded. The missing workflow-version reference has been regenerated along with
localized schema snapshots; scanner rules, exact accepted baseline tuples and warning
exceptions were not expanded. Subsequent regenerated references and the final gate pass.

Intermediate corrected gate `/tmp/app-be-check-z1s2gpa0/report.json` passed all fifteen
stages: 808 default passes, 172 documented opt-in exclusions, one doctest and 75
required service-profile passes with no required skips. A later actual HTTP probe
found that a valid 230-branch published graph could exceed workspace bounds yet
receive a plan token; `/tmp/app-be-026-bounds-red.log` records one failure / eleven
passes. That concrete defect has been repaired by checking WorkspaceDocument before
dependency validation/token issuance. The green probe passed twelve tests in an owned
database, and the fresh final gate passed all stages on the repaired tree. The earlier
passing tree is not substituted for this final implementation.

The localization regression now verifies all three new operation summaries and
descriptions plus bounded input field descriptions in en/fa. Three focused tests
pass, and generated artifact hashes/auth/private headers/localization were checked.
An intermediate pre-commit failure trimmed the two PO files' final blank lines;
the next standalone hook check passed. No hook/scanner rule was disabled.

The required `delivery-completion-test` stage adds restoration plus workspace/library
regressions to the unchanged earlier strict stages. Its selected integration tests
must actually run without skips. Default opt-in exclusions are not service evidence.

AST-only `graphify update .` refreshed 15,524 nodes and 36,645 edges; the sandboxed
attempt could not start its local multiprocessing, and the authorized local retry
succeeded. No semantic API was used.

Open scope:

- APP-BE-021/022: exact protected-operation/action mapping remains owner-review
  pending in [the concrete pilot policy](protected-effect-policy.md). The backlog
  requires a product decision for this mapping; no new authority model is assumed.
  APP-BE-023/024/025/028 and their downstream harness/release tasks retain dependencies.
- APP-BE-027: prior real worker/storage and paired Node boundary evidence is preserved.
  The known frontend streaming oversize connection reset still prevents a claim of
  graceful end-to-end recovery. Header-only preflight acceptance does not close it.
- APP-BE-030: inspected earlier repairs and restoration findings are verified by
  the passing gate. Final-scope review of the remaining protected-effect/demo/release
  capabilities is incomplete because those implementations are pending. Earlier
  warning/migration blockers are resolved by accepted decisions and additive repairs.
- APP-BE-029/031/032: no complete combined demo/reset rehearsal, final runtime image
  proof, hosted CI result, full new-table backup/restore or browser acceptance is
  claimed by this narrower restoration slice.

Live vendor effects and paid AI remain separate opt-ins. Accepted SDK exceptions
require the label VERIFIED_WITH_EXCEPTION. DEMO_READY and USER_ACCEPTED remain unclaimed.

Paired repository: `afe4bbe5f566c80e7eb45f6ef9f12c041d60139d` with nonignored working-tree hash
`ef348dd6349d43fed41cf3e794e753edde5f7a9ab8fdf9394102fc88f532038c`. Only the actual Node private transfer
boundary is verified. The peer is dirty and no peer source was changed by this work.
Full frontend/browser acceptance and its restoration screens remain separate.
