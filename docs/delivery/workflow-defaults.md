# C13 workflow definition restoration

The immutable baseline is an exact published or retired workflow version, its stored
graph checksum and installation binding map. Retirement changes a reference revision,
but does not change baseline content. Recorded provenance resolves that identity to a
current reference only after checking the original content hash. An explicitly selected
source requires its current reference. Custom workflows require explicit selection.

All three operations are authenticated POST members of
`/api/v1/workflow-versions/{ref_id}` and require current `workflows.manage`, a live
actor and target access. JSON uses existing snake_case success/error envelopes and
responses are private, no-store. The generated en/fa OpenAPI snapshots in `wave-four/`
and the workflow-version response reference contain the nested wire schemas.

1. `default-preview`: send `source_ref_id` when unassociated, `mode` of
   `replace_draft` or `successor`, the saved `workspace_ref_id` when present, and
   optional symbolic dependency `bindings`. This operation writes nothing. The
   response contains the template reference/checksum, exact dependency manifest,
   changed step keys and top-level paths, and publication-validation blockers.
   Blockers prevent token issuance. The signed plan expires after 600 seconds.
   The restored graph must also fit the existing workspace contract: at most
   256 KiB, depth 32 and the existing structural bounds, with a one-MiB document
   ceiling. Oversized published templates return `workspace.graph.invalid` and
   no token before dependency validation or writes.
2. `default-apply`: send the identical `plan_token` and a client-generated
   `command_key`. Current authorization, target/workspace revisions, source content
   and bound dependencies are rechecked. DRAFT replacement changes its graph and
   workspace together; successor creates a new DRAFT, including for retired targets.
   The new workspace is already promoted to the restored executable graph.
   Publication remains an explicit separate action.
3. `layout-reset`: send the current workspace reference for a DRAFT. This clears
   positions, routing, collapsed nodes and viewport; it preserves the authored
   graph, executable version and promotion checksum. Unsaved local-edit discard
   is a separate client action.

Symbolic keys are `form:step`, `step_type:step`, `subprocess:step`, `connection:step`,
`agent:step`, or `user:step:target_index` / `work_group:step:target_index`.
At most 128 replacements are accepted. Existing dependency owners enforce type,
publication, current-reference and visibility rules. Published forms and child
workflows are immutable dependencies reused by reference; restoring the parent
does not overwrite or publish them. A failed mixed-definition validation or later
workspace write rolls back the entire command. No separate template engine is added.

The unique actor/target/command receipt and root lock serialize concurrent retries.
Identical committed intent returns its existing result even after preview expiry;
another token using the same key conflicts. Replay rechecks live permissions and
target access. Result references reflect current result/workspace revisions, so a
client must still reconcile later edits. Receipts contain identifiers and a plan
hash, not the token, graph, form values or credentials. They are retained with the
workflow and do not have a generic CRUD or purge endpoint.

Unavailable sources fail 404, forbidden actors 403, stale references/expired plans
and changed command intent 409, and invalid symbolic bindings 422. Dependency
validation failures appear as safe preview blockers without an applicable token.
The existing public error catalog remains unchanged.

No active process, submission, request-type route, published payload, secret, user,
role, integration principal or effect changes as a side effect. Database revision
`k026_workflow_restore`, after `j016_calendar_events`, adds only the receipt table.
Both originally applied migration files remain untouched.

Verification is tracked in `completion-verification.md`. Browser default-restoration
screens and destructive demo-environment reset are separate APP-FE-027 / APP-BE-029
work; the HTTP contract alone is not their acceptance.
