---
tags: [api]
---

# Reusable subprocess authoring and execution (BPMS-031/032)

A published workflow version may expose an immutable `interface` in its graph. Interface metadata may include `category`, English/Persian `help_messages`, bounded `sample_inputs` validated against declared input ports, and `required_capabilities`. The [definition library API](definition-library.md) exposes version discovery, where-used, templates, and draft call upgrades. Another workflow may pin that exact version on a `SUBPROCESS` step. The published call is a reference, not an editable copy template. `GET /workflow-versions/{ref_id}/graph` returns the saved interface and call. Existing graphs with no interface or calls retain their prior checksum.

**Execution capability:** `SUBPROCESS` is available for authoring, publication and execution. `POST /designer/catalog` reports `runtime_available: true` for authorized published interfaces and the registered step type. A request starts a pinned child when its call step is reached.

## Child interface

`GraphSnapshot.interface` is nullable. When present, it has `inputs` (up to 64 named `SubprocessPort` entries), `outputs` (up to 64 named `SubprocessOutput` entries), and `outcomes` (1–16 business names mapped to distinct `FINISH` step keys). Names are unique within inputs and within outputs. Each `value_schema` is a JSON Schema Draft 2020-12 document. An output names a child step and declared output port with a matching schema. An input with `assignment: "user"` or `"work_group"` carries a string reference for future child assignment; it does not grant permission by itself.

For example, a **ManagerApproval** version can declare a required `manager_ref` string with `assignment: "user"`, a required integer `amount`, an output `decision` from a review step, and `approved`/`rejected` outcomes mapped to separate `FINISH` steps. A **DocumentReview** version can declare `review_group_ref` with `assignment: "work_group"`, `document_ref` as a string, and `accepted`/`changes_requested` outcomes. These are authoring examples; the child graph must contain the named finish and output steps, compatible port schemas, a valid start, and reachable transitions before publication.

```json
{
  "interface": {
    "inputs": [
      {"name": "manager_ref", "value_schema": {"type": "string"}, "required": true, "assignment": "user"},
      {"name": "amount", "value_schema": {"type": "integer"}, "required": true, "assignment": null}
    ],
    "outputs": [],
    "outcomes": {"approved": "finish_approved", "rejected": "finish_rejected"}
  }
}
```

## Parent call

Add a graph step with `type_code: "SUBPROCESS"`, the published `SUBPROCESS` step-type version reference from the step-type catalog, empty `config`, and a `subprocess` object. The `workflow_version_ref` must be the exact published child version returned by the API. Map every required child input explicitly. Mapping source kinds are `REQUEST`, `CONTEXT`, `CONSTANT`, and `STEP_OUTPUT`. A step-output mapping names a predecessor step and output port; publication verifies its stored schema and that the source dominates the call. A constant is checked against the target JSON Schema. Source and target schema mismatches are rejected; no implicit conversion is performed. Add at least one declared business-outcome transition and an explicit `failure` transition. `failure` is reserved for technical child failure and cannot be declared as a business outcome.

```json
{
  "key": "manager_approval",
  "type_code": "SUBPROCESS",
  "type_version_ref": "<SUBPROCESS step-type ref_id from catalog>",
  "config": {},
  "subprocess": {
    "workflow_version_ref": "<published ManagerApproval workflow-version ref_id>",
    "inputs": [
      {"name": "manager_ref", "source_kind": "CONSTANT", "source_schema": {"type": "string"}, "constant_value": "<authorized user ref_id>"},
      {"name": "amount", "source_kind": "CONSTANT", "source_schema": {"type": "integer"}, "constant_value": 100}
    ]
  }
}
```

The angle-bracket values in these examples must be replaced with references returned by the API. They are not reusable tokens. `POST /workflows/validate` checks graph dependencies without a parent version identity. `PUT /workflow-versions/{ref_id}/graph` and `POST /workflow-versions/{ref_id}/publish` also check the parent version and reject self-reference. The caller needs `workflows.manage` for these routes and start access to the child workflow. A view grant alone does not authorize a call. Designer catalogs show only viewable published interfaces, but publication performs its own start-access check.

Publication rejects draft, retired, deleted, inactive, stale or inaccessible child versions; missing ports and mappings; type mismatches; invalid finish/output mappings; unsupported per-call timeout, retry or compensation flow options; and more than four nested levels or 32 distinct transitive dependencies. New calls cannot pin a retired version. Existing published callers keep their exact pins after retirement. Published graphs and interface records are protected by existing database immutability checks.

Validation issues use the existing pointer/code array, such as `{"pointer":"/steps/1/subprocess/inputs/0/source_schema","code":"subprocess.input.type_mismatch"}`. The existing success/page envelopes and public error handling apply. Malformed JSON and authoring rule failures return HTTP 422 with the existing `VALIDATION_FAILED` envelope; rule failures include pointer/code issues. A stale draft or unavailable runtime returns HTTP 409 `VERSION_CONFLICT`. No new error envelope or header is introduced.

## Execution and recovery

A `SUBPROCESS` call starts one child `PROCESS_INSTANCE` for the exact parent `STEP_EXECUTION` visit. The child keeps the same business request as its authorization root, pins its own published workflow version, and stores only the mapped inputs in `INPUT_CONTEXT`. A unique parent-execution index prevents a second child for the same visit. The parent call and token wait with `wait_kind: "SUBPROCESS"`; child creation, input snapshot, token and correlation events share the parent transaction. Child human tasks and timers use the existing work-item and scheduler paths. A retired child version remains executable for an already published call pin.

The child terminal transaction writes its status and an opaque `bpms.settle_subprocess` outbox message. The worker locks the parent, checks that the exact call is still waiting, reads the committed child result, validates each declared output against the pinned child interface, and takes the matching business outcome or explicit `failure` edge. Repeated worker delivery sees the completed call and does nothing. A result arriving after a terminal parent is ignored. A missing finish mapping or invalid output uses the `failure` edge with a stable operational code; no private input, form submission or output value is copied into generic process events.

The request remains the root of authorization. `POST /processes/{ref_id}/timeline` accepts the existing `{"page":1,"size":20}` query DTO and returns `children` alongside the root steps, transitions, events and current positions. Each child summary has `process_ref_id`, `parent_execution_ref_id`, `workflow_version_ref_id`, `status`, `current_positions` and recursively nested `children`. Traversal stops at the published four-level depth, tracks visited process IDs, and refuses an overlarge direct-child result. A child process can also be inspected by its opaque reference under the same request-view rule. These summaries contain references and positions, not context or output snapshots.

For a two-approval request, the first call can map `manager_ref` to one user and `amount` to `"10"`; the second call maps a different user and `"20"`. Each child creates its own work item and returns its own `decision` output. The first result advances to the second call only after worker settlement. An illustrative timeline fragment is:

```json
{
  "success": true,
  "request_id": "example-request-id",
  "error": null,
  "code": 200,
  "data": {
    "process_ref_id": "<opaque parent ref_id>",
    "business_request_ref_id": "<opaque request ref_id>",
    "status": "WAITING",
    "coverage_started_at": "2026-10-01T10:00:00Z",
    "current_positions": [{"token_ref_id":"<parent token>","step_key":"manager_two","execution_ref_id":"<parent call>","status":"WAITING","wait_kind":"SUBPROCESS"}],
    "children": [
      {"process_ref_id":"<first child>","parent_execution_ref_id":"<first call>","workflow_version_ref_id":"<pinned ManagerApproval version>","status":"COMPLETED","current_positions":[],"children":[]},
      {"process_ref_id":"<second child>","parent_execution_ref_id":"<second call>","workflow_version_ref_id":"<same pinned version>","status":"WAITING","current_positions":[{"token_ref_id":"<child token>","step_key":"review","execution_ref_id":"<review execution>","status":"WAITING","wait_kind":"HUMAN"}],"children":[]}
    ],
    "steps": [],
    "transitions": [],
    "events": {"items": [], "page": 1, "size": 20, "total": 0}
  }
}
```

The angle-bracket references are placeholders. Actual responses contain signed opaque `ref_id` values, actual root steps/history and paginated events. A requester or authorized observer needs the existing `requests.start` permission and request-view access; control remains limited to the requester or administrator. Parent `resume`, `pause`, `cancel`, `retry`, `timeout` and `compensate` are rejected with the existing HTTP 409 `VERSION_CONFLICT` while a child is active. Direct child control is unsupported; human claim/finish and timer delivery remain available through their existing endpoints. Advanced business cancellation, timeout, retry and compensation propagation across parent and child have no policy yet. Operators should inspect the child timeline and outbox/task history; a failed broker delivery may be retried using its existing task mechanism, while a failed child follows the explicit parent failure edge. Do not restart a completed call or replay ambiguous external effects.
