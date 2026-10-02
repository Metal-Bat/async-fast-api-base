---
tags: [api]
---

# Pinned human-task views, actions and correction rounds

BPMS-030 adds an optional `task_contract` to each authored `HUMAN_TASK` workflow graph step. The contract is stored on the exact published workflow step. Existing steps without it retain their historical action and data behavior. A task contract declares named `edit`, `summary` and `print` views, localized plain-text titles, a default view, action profiles, and optional `correction_entry` / `inherit_previous` data handoff. The step's existing `field_policy` remains the server authorization source; render visibility and action labels never grant access.

A contract requires at least one edit view. Each view's `scopes` must name readable or writable leaf fields in the pinned form schema. The published form's client variant is selected from the persisted origin/interaction context before the named task view filters its render nodes. Locale resolves only text. Changing device or locale does not reroute the process or change the pinned task contract. `inherit_previous` copies the latest submitted canonical data and governed attachment links into a new task draft. `correction_entry` consumes the latest returned submission once and links a new draft to it. Earlier submitted forms remain immutable. Published workflow validation rejects missing action transitions, unknown outcomes, unreadable view scopes, broad object scopes, or an object-array scope that would contain hidden children.

Example authored step excerpt:

```json
{
  "key": "review",
  "type_code": "HUMAN_TASK",
  "form_ref": "<published-form-version-ref>",
  "field_policy": {
    "read": ["/properties/amount"],
    "write": ["/properties/note"],
    "required": [],
    "hidden": ["/properties/secret"]
  },
  "task_contract": {
    "default_view": "review",
    "inherit_previous": true,
    "correction_entry": false,
    "views": [
      {"key": "review", "purpose": "edit", "title": {"en": "Review", "fa": "بررسی"}, "scopes": ["/properties/amount", "/properties/note"]},
      {"key": "print", "purpose": "print", "title": {"en": "Print"}, "scopes": ["/properties/amount"]}
    ],
    "actions": [
      {"key": "return", "kind": "return", "outcome_key": "return", "title": {"en": "Return"}, "confirmation": {"en": "Send back for correction?"}, "required_scopes": [], "require_comment": true, "validation": "partial"}
    ]
  }
}
```

## Read a named view

`GET /api/v1/work-items/{ref_id}/view?key=review` requires authentication, `requests.start`, and current work-item visibility. Omit `key` for the pinned default view. The response is `200` in the standard success envelope, with `Cache-Control: private, no-store`. `data`, `before_data`, `item_identity`, feedback and `render_schema` are filtered by the step read policy and named view. `before_data` is the prior submitted snapshot when one exists. The only actions returned are those declared for the current claimant while the item is editable; an observer gets `actions: []`. `print` is metadata and canonical filtered data for a client-generated print view; it never bypasses the read policy.

Example `data` portion of the success envelope:

```json
{
  "work_item_ref_id": "<current-ref>",
  "submission_ref_id": "<pinned-submission-ref>",
  "view_key": "review",
  "purpose": "edit",
  "title": "Review",
  "data": {"amount": 7, "note": "Check receipt"},
  "item_identity": null,
  "before_data": {"amount": 7},
  "render_schema": {"root": {"component": "vertical", "children": [
    {"component": "integer", "scope": "/properties/amount"},
    {"component": "text", "scope": "/properties/note"}
  ]}, "outcomes": ["approve", "return"]},
  "actions": [{"key": "return", "kind": "return", "outcome_key": "return", "title": "Return", "confirmation": "Send back for correction?", "required_scopes": [], "require_comment": true, "validation": "partial"}],
  "feedback": [],
  "autosave_conflict": "VERSION_CONFLICT",
  "unsaved_navigation": "warn_before_leave"
}
```

Clients must warn before leaving an unsaved edit. Autosave uses the latest revision-bearing work-item `ref_id`; conflicting drafts fail with `VERSION_CONFLICT`. The server never merges conflicting edits. A successful save returns a new ref. `POST /api/v1/work-items/{ref_id}/save` accepts `command_key` and complete draft `data`. Missing required fields are allowed while editing, but any supplied value must have a valid type and all changed paths must be writable. Array structure uses the collection edit endpoint. A guessed hidden/read-only path fails with a pointer issue (`task.field.read_only`).

## Action validation and correction feedback

`POST /api/v1/work-items/{ref_id}/complete`, `/reject` and `/return` accept `command_key`, `outcome_key`, `data`, optional `comment`, and optional `feedback`. The pinned contract must declare the matching action kind/outcome; the pinned form and workflow must also declare that outcome. A full profile runs all form and behavior requirements. A partial profile relaxes missing-field requirements only; supplied types, formats, calculated-value integrity, governed options, step `field_policy.required` and action `required_scopes` remain enforced. A declared `require_comment` requires a nonblank reason. A new-contract return requires at least one feedback entry and a reason. The server validates claim, version, policy, action and data before the submission, action history and process resume commit atomically. An identical command-key/payload replay returns the completed item; a changed payload conflicts.

Return request example:

```json
{
  "command_key": "return-review-1",
  "outcome_key": "return",
  "data": {"amount": 7, "note": "Needs correction"},
  "comment": "Please correct the amount",
  "feedback": [{"scope": "/properties/amount", "item_key": null, "message": "Use the invoice total"}]
}
```

Feedback is stored outside canonical business data with a server-generated UUIDv7 `key`, author ref, status `OPEN`, and UTC time. Repeated-row feedback requires the exact UUIDv7 `item_key` from `item_identity`; a guessed or misplaced key fails. Reordering keeps that key with the row. The linked correction draft copies feedback, canonical data, item identities, and active attachment links. `POST /api/v1/work-items/{ref_id}/feedback/{feedback_key}/resolve` requires the current claimant of that editable correction task; it records `RESOLVED`, actor and UTC time. The old submitted snapshot and its feedback remain intact. Further return/correction rounds append feedback and retain the prior statuses.

Typical errors use the project's standard envelope: `VALIDATION_FAILED` with pointer issues such as `task.action.unavailable`, `task.action.reason_required`, `task.feedback.required`, `task.feedback.scope`, `task.feedback.item_key`, and `task.field.read_only`; `VERSION_CONFLICT` for stale work-item refs or already resolved feedback; and `NOT_FOUND` when the actor cannot see the item, view, or attachment. Resource reads and option/attachment routes use the same policy filter for task-only actors. Users with an independent workflow/request grant retain that independent access.

Alembic revision `7f42c641ab30` adds nullable `WORKFLOW_STEP.TASK_CONTRACT`, a nullable correction-source foreign key and nullable feedback JSONB to `FORM_SUBMISSION`, plus audited submission history columns and a unique correction-source index. No new environment variables or dependencies are required.
