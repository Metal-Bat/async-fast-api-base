# Live query matrix

Normal pagination applies `deleted_at IS NULL` before both item and count queries when the entity supports that marker. Caller filters are combined with this base predicate; they cannot remove it. `apply_query` remains lifecycle-neutral for explicit history and audit use.

| Owner/result | Policy | Evidence |
| --- | --- | --- |
| BaseCrudRepository user/role lists and totals | Shared live predicate | Repository regression and real PostgreSQL pages |
| paginate_entities roots: users, roles, groups, forms, workflows, request types | Shared live predicate, identical count | Six PostgreSQL cases, deep page and retained direct lookup |
| Form/workflow version authoring search/report | Resolve live parent before paging; exclude deleted children | Parent guard regression; report delegates to search |
| Work-group user/group selectors | Live by default; explicit include_deleted remains admin.work_groups.manage protected | Existing selector tests; ordinary seeded role gets HTTP 403 |
| Designer selectors and request eligibility | Existing current/live parent and eligibility joins | Existing designer/request service tests and HTTP journey |
| Workflow grants | Existing live parent, current principals and live grant predicates | Existing authorization tests |
| Report ownership/search | Existing live report/owner predicates retained | Existing reporting tests |
| User cached pages | New live-page namespace prevents pre-change cached results | Shared cache invalidation remains commit-owned |
| Administrative history, work-item history and pinned execution snapshots | Lifecycle-neutral historical resolution retained | Existing history/pin tests and disposable workflow acceptance |
| User audit export | Existing deleted-state evidence retained | Explicit audit behavior; no silent live-only conversion |

Historical direct lookup is deliberately separate from ordinary lists. This change adds no global ORM filter. Published pins, canceled processes, retired versions and inactive definitions retain their domain lifecycle semantics. Existing restore authorization, version checks and uniqueness conflicts remain owned by the original services. No unrestricted include_deleted option is added.

The inventory above bounds this wave's implementation and evidence. End-to-end cache deletion/restore was verified against the project's Dragonfly image in an owned ephemeral container/namespace: deletion invalidated the public page after commit, restore refreshed the reference and returned the row. Real database user/group selectors and restored counts ran separately from shared predicate unit tests. Direct ordinary-user restore denial is included in seeded-role acceptance. APP-BE-006 remains open because its strict-gate prerequisite APP-BE-002 is blocked; wider future feature projections still need their owning task acceptance.
