---
tags: [api, dto, examples]
---

# Response scenarios

These examples are validated against their Pydantic response DTOs with synthetic opaque references. They show different states a frontend must handle. They are wire-shape examples, not responses captured from a running process. The backend assigns the real `request_id`, refs and timestamps. See the [full response DTO reference](../reference/responses/index.md) for every field.

## A claimed human approval work item

```json
{
  "success": true,
  "request_id": "example-request-id",
  "error": null,
  "code": 200,
  "data": {
    "ref_id": "opaque-work-revision",
    "request_ref_id": "opaque-request-revision",
    "step_execution_ref_id": "opaque-execution-revision",
    "form_version_ref_id": "opaque-form-version",
    "submission_ref_id": "opaque-submission-revision",
    "item_identity": null,
    "design_snapshot": null,
    "status": "CLAIMED",
    "priority": 7,
    "claimant_ref_id": "opaque-user-revision",
    "outcome_key": null,
    "due_at": null,
    "claimed_at": "2026-10-02T12:00:00Z",
    "closed_at": null,
    "created_at": "2026-10-02T12:00:00Z",
    "read_at": null,
    "pinned_at": null,
    "archived_at": null,
    "watching_at": null
  }
}
```

The claimant may inspect the pinned form and available task actions; `outcome_key` is still null.

## Process waiting for one human decision

```json
{
  "success": true,
  "request_id": "example-request-id",
  "error": null,
  "code": 200,
  "data": {
    "ref_id": "opaque-process-revision",
    "business_request_ref_id": "opaque-request-revision",
    "workflow_version_ref_id": "opaque-workflow-version",
    "status": "WAITING",
    "current_positions": [
      {
        "step_key": "human_review",
        "token_status": "WAITING",
        "execution_status": "WAITING",
        "wait_kind": "HUMAN"
      }
    ],
    "last_error_code": null,
    "started_at": "2026-10-02T12:00:00Z",
    "ended_at": null
  }
}
```

The process is waiting; AI preparation does not complete the approval.

## Parallel approvals in flight

```json
{
  "success": true,
  "request_id": "example-request-id",
  "error": null,
  "code": 200,
  "data": {
    "ref_id": "opaque-process-revision",
    "business_request_ref_id": "opaque-request-revision",
    "workflow_version_ref_id": "opaque-workflow-version",
    "status": "WAITING",
    "current_positions": [
      {
        "step_key": "finance",
        "token_status": "WAITING",
        "execution_status": "WAITING",
        "wait_kind": "HUMAN"
      },
      {
        "step_key": "procurement",
        "token_status": "WAITING",
        "execution_status": "WAITING",
        "wait_kind": "HUMAN"
      }
    ],
    "last_error_code": null,
    "started_at": "2026-10-02T12:00:00Z",
    "ended_at": null
  }
}
```

Render both current positions. A single `current_step` control would lose one branch.

## Pending approved-source lookup

```json
{
  "success": true,
  "request_id": "example-request-id",
  "error": null,
  "code": 200,
  "data": {
    "work_item_ref": "opaque-tool-approval-work",
    "status": "PENDING",
    "tool_key": "lookup_saved_report",
    "tool_version": "1",
    "arguments": {
      "report_ref": "opaque-report-ref",
      "limit": 5
    },
    "expires_at": "2026-10-02T12:00:00Z",
    "decided_at": null
  }
}
```

An eligible claimant must decide the exact displayed read-only tool call before it can be consumed.

## Published form version selector

```json
{
  "success": true,
  "request_id": "example-request-id",
  "error": null,
  "code": 200,
  "result": {
    "items": [
      {
        "key": "opaque-form-version",
        "value": "Purchase form · v3"
      }
    ],
    "page": 1,
    "size": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

`response_format=items` returns only the `result.items` array from the same bounded page.
