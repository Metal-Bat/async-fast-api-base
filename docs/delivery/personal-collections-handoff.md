# APP-BE-009 / C04 personal collections

This extends the existing users owner and C03 resource resolver. The generated
`wave-four/personal-contracts.json` freezes the four supported view scopes, exact list
query schemas, required permissions, allowed columns and create contracts. Full en/fa
OpenAPI and artifact hashes are in `wave-four/manifest.json`. These are backend
contracts; they do not claim frontend integration or deployment.

## Saved views

`/api/v1/me/saved-views` exposes POST create, POST `/search`, GET `/{ref_id}`,
PUT `/{ref_id}`, DELETE `/{ref_id}`, POST `/{ref_id}/history` and POST `/report`
(the existing paginated search alias, not an archive job). POST `/{ref_id}/default`
and `/apply` accept `{}`. All endpoints authenticate the live actor and return
private, no-store responses with the existing envelopes.

Scopes are forms, workflows, business_requests and work_items. Form/workflow views
require forms.manage/workflows.manage; request/cartable views require requests.start.
Reading/applying a preset repeats current permissions and never grants list access.
The eventual list search still applies its own live-record and owner/group predicates.

```json
{
  "name": "My active requests",
  "resource_kind": "business_requests",
  "schema_version": 1,
  "command_key": "preset-create-1",
  "query": {
    "scope": "mine",
    "filters": [{"field_name": "status", "operation": "equal", "value": "RUNNING"}]
  },
  "column_keys": ["title", "status"],
  "page_size": 20
}
```

Name length is 1–120 (whitespace-only names rejected); command key 1–128. Query is
at most 8 KiB with 20 filters/10 sort orders. Columns are distinct and allowlisted;
page size is 1–100. The same existing domain query models validate field names,
operators, values and time bounds. Cartables retain their actual typed fields;
unsupported generic filter/sort features are rejected. No page/size is stored inside
the query, and no result body, actor assignment, privilege, arbitrary SQL or reference
filter is accepted. Search chips use non-reference scalar fields only.

Maximum 100 live views per scope; names are unique within self/scope. Creation is
installation-independent and keyed by actor plus command_key, storing the original
payload for replay comparison. An identical replay returns the existing current view;
changed payload with the same key returns 409. A removed creation key cannot recreate
its item; deliberate new creation uses a new key. PUT is a complete replacement, with
defaults for omitted optional fields and no null-reset semantics. Scope cannot change.
It requires the current path reference, except an identical last update-key replay;
changed replay or stale reference returns 409. No user reassignment exists.

Default selection is explicit. A live user-row lock serializes updates, and a partial
unique database index permits one live default per user/scope. Switching defaults
increments affected refs; repeated selection of the current default is idempotent.
Deletion clears the default. Search order is deterministic with ID tie breaking.

If a stored schema version/filter/column becomes unsupported, GET/search preserves the
original preset and returns compatible=false, reason=schema_changed. Apply returns no
query or columns; it does not silently remove filters or broaden scope. Compatible
apply returns the validated query with page=1 and the stored size, without executing
it. Deliberate repair uses PUT and the current ref. Private free-text never enters
seed data, diagnostics or metrics. History returns only safe changed_at/operation
metadata and supports its own typed bounded filter/order query.

## Favorites

`/api/v1/me/favorites` exposes create, search, detail, delete, metadata history and
the paginated report alias. Create accepts the existing `{kind, ref_id}` C03 shape.
It authorizes through the owning resource service, stores canonical kind+UUID, and
returns the current label/ref, stable locator and route key. No target label or
revision-sensitive reference is persisted. Version favorites keep the exact selected
version identity. The resource-link allowlist excludes work items: existing
work-item personal `pinned_at` remains their single favorite state.

Creation is idempotent per user/kind/target, including concurrent requests. Recreating
an explicitly removed favorite restores only that personal item. Maximum 100 per
kind and 500 live favorites overall. Existing owner authorization is repeated before
display; missing/deleted/revoked targets are omitted before pagination/count and do
not expose titles. Inactive readable targets retain explicit available=false. Search
resolves at most the bounded stored candidate set; no shared cache is introduced.

Delete identifies the favorite, never its target. It remains available to its owner
after target revocation, requires a current ref for the first deletion and is safe to
repeat. Target mutation/deletion is never a favorite side effect. Sharing remains out
of scope. Core history marks PERSONAL_ITEM and USER_PREFERENCES histories self-only,
so the generic admin history reader cannot expose private documents. Dedicated
personal history reads return only metadata after ownership/current permission checks.

## Schema and verification

Owner-approved additive revision `g009_personal_items` follows the current head and
adds PERSONAL_ITEM plus history, FK, shape/size checks and unique live name/default/
favorite identity indexes. Both previously applied migrations remain unchanged.
Rollback removes only personal state, never targets; destructive verification uses
the exact owned disposable harness, not shared data.

Observed results and the final gate are tracked in `through-009-verification.md`.
The new parent revision reference adds one public identifier finding to the existing
eight secret-scanner false positives. The nine-entry review remains pending; the
security baseline is unchanged until explicit approval.
