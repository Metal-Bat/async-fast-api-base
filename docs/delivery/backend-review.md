# APP-BE-030 review of waves one through three

Current verdict: PARTIAL, final delivery review IN_PROGRESS. The original wave-three
warning and migration blockers were resolved by explicit owner acceptance of the two
exact SDK exceptions and additive comment repair, then verified by the through-020
gate. The dated table below preserves the historical findings rather than claiming
they remain unresolved. This is not approval of unimplemented later-wave features.

Reviewed 2026-10-08 against baseline `995829eebd9483ac6b589c1648fc799c650ad464`, including the new/untracked scripts, DTO, manifests and tests. Scope: shared pagination/BaseCrudRepository, user cache identity, form/workflow child search, protected selectors, permission reconciliation, strict gate and disposable runner. Context inspected: workspace save/promotion, workflow publication/dependencies/current grants, structural graph validator, registered automation operations, integration provider and background dispatcher (B09–B14).

| Severity/status | File/function | Evidence and impact | Repair/verification |
| --- | --- | --- | --- |
| High, OPEN | `src/migrations/versions/c24f913ab601_workflow_workspace.py`, workspace upgrade | Populated upgrade retains data but Alembic reports five missing inherited column comments | Proposed additive repair in migration-verification.md; D01 approval required; no existing revision edited |
| High, OPEN | `src/apps/ai/application/providers.py`, native SDK construction | Five native provider tests fail under warnings-as-errors because Cohere/Google SDKs invoke deprecated Python APIs | Targeted upgrade resolves same versions; D07 owner decision pending; no monkeypatch or blanket filter introduced |
| High, FIXED | `scripts/run_check.py:58`, permitted_default_exclusions | Original draft could classify any default-suite skip/xfail as passing | Restrict to exact documented integration exclusions; reject unit skips and xfail; dedicated regression passes |
| High, FIXED | `src/utils/pagination.py:217`, live_record_criteria and BaseCrudRepository list/count | Deleted rows previously appeared in ordinary results/counts; user filters could request deleted state | Apply immutable base predicate to both queries; conflicting-filter unit regression and six PostgreSQL cases |
| High, FIXED | `src/apps/forms/presentation/routes.py:161` and workflows route `:215`, search_versions | Live child search did not resolve whether its parent was deleted | Resolve parent at its existing service before pagination; failing-before-fix regression for both domains |
| Medium, FIXED | `tests/core/test_cache_session.py:60`, SQLite engine cleanup | Strict suite exposed an unclosed SQLite connection later during localized schema generation | Dispose engine in finally; 16 focused tests pass with -W error |
| Medium, FIXED | `tests/integration/test_migrations.py:19`, require_disposable_database; runner profile ordering | Original migration test had no explicit ownership check; runtime data intentionally forbids downgrade | Verify exact UUID database ownership/local host; run empty round trip before runtime fixtures; preserve existing refusal |
| Medium, FIXED | `tests/integration/test_migrations.py`, async fixture | Draft fixture used blocking subprocess calls and SQLModel exec overloads unsuitable for raw SQL | AnyIO process execution; AsyncConnection raw SQL; Ruff/ty clean |
| Medium, FIXED acceptance gap | User cache/restore integration | Real public pages must refresh after commit, not merely call a mocked invalidator | Owned Dragonfly/PostgreSQL test passes for delete, restore and fresh references; direct ordinary-role restore denial also tested |

New permission summaries inherit BaseDTO and use snake_case. No entity declaration or applied migration changed. Seed writes retain existing permission/role revocations, published snapshots and grants; optional roles do not grant superuser. PostgreSQL transaction locks serialize seed creation and real concurrent invocations use separate sessions. Queries remain bounded by fixed manifest size and page size. No network effect executes inside seed reconciliation.

The inspected background dispatcher stages outbox work transactionally, performs provider calls with a separate session, then applies the idempotent callback in a new transaction. The status provider uses a ten-second timeout, disables redirects and environment proxies, and returns bounded status data without response bodies or credentials. It currently supports connection.status, not a business-effect receipt. Existing workspace publication and publisher-bound execution authority remain intact. Their later product requirements belong to APP-BE-019/021/022/023/024/026; this review does not certify those pending features.

No session-sharing, broad cancellation catch, new unbounded business query, public serialization alias or credential emission was introduced in this diff. Existing untyped workspace service boundaries are later maintainability scope; changing them is unnecessary for this repair. End-to-end worker cancellation, live providers, rebuilt images and frontend/browser acceptance remain outside the observed wave-three evidence.

## Restoration review — 2026-10-09

Inspected scope: `workflows/application/defaults.py`, the three new member routes and
DTOs, receipt entity/migration, existing workspace save/promotion, publication graph
validation and the new required PostgreSQL profile. The review includes untracked
files; it is not limited to the staged Git diff.

| Severity/status | Finding | Minimal repair and evidence |
| --- | --- | --- |
| High, FIXED | Apply originally checked permissions before acquiring actor/root locks, then reused the unlocked decision | Reload actor/root and recheck current capability under the same locks before receipt lookup; ordinary role revocation between preview and apply is denied in actual PostgreSQL HTTP tests |
| High, FIXED | Repeated or racing successor commands could otherwise create multiple drafts | Unique actor/target/command receipt plus root serialization; concurrent real HTTP calls return one result, and different-token key reuse conflicts |
| High, FIXED | Workspace edit after preview could overwrite newer author work | Freeze independent workspace reference and target revision; stale apply returns 409; graph, workspace and receipt share the API transaction |
| High, FIXED | Baseline retirement increments metadata revision and could break unchanged immutable provenance | Resolve recorded identity to current reference only after verifying the immutable hash; explicit sources still require exact current refs; final retired-baseline regression belongs to required profile |
| Medium, FIXED | Publication validation can raise safe dependency issues before returning a GraphValidationResult | Convert only ValidationDetailsException into preview blockers with no token; unexpected/authorization errors remain failures |
| Medium, FIXED | New service/slot boundaries were untyped or returned unknown values | AsyncSession and explicit actor/version/root/source/result boundaries; runtime string checks for reference slots; ty passes without new suppressions |
| Medium, FIXED | New integration tests retained pool connections across independent event loops | Local fixture disposes engine in finally; initial cross-loop failure retained in private logs; subsequent owned profiles passed |
| High, FIXED; final gate pending | A valid published graph can exceed independent workspace structural/size bounds, so the initial preview could issue an unapplicable plan | A genuine 230-branch published graph reproduces the defect over authenticated HTTP; preview validates the existing WorkspaceDocument contract before issuing a token or performing dependency work and returns workspace.graph.invalid without raw values |

Receipts store identity/hash only and have no generic public history or CRUD endpoint.
Their indexes and unique/FK constraints are explicit. No effect, external call, secret,
runtime-data rewrite or shared AsyncSession is introduced. Signed plans contain
authorized dependency references, not raw graphs or form submission values. Published
dependencies are reused rather than reset. Partial-write injection proves no draft or
receipt leaks after rollback; actual mixed templates preserve process/submission/type
pins and published form contents.

Remaining capability blockers: the exact protected-operation policy in
`protected-effect-policy.md`, the paired frontend oversized streaming recovery gap
recorded under APP-BE-027, and unimplemented APP-BE-021–025/028–029/031–032 acceptance.
Those are explicit blockers, not findings declared repaired by a passing unit suite.
The final full gate remains required for this slice.
