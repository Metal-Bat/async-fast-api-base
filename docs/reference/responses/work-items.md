---
tags: [api, dto, work-items]
---

# work-items response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `CollectionIssue`

Used by: `POST /api/v1/work-items/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `code` | `string` | Yes | — |
| `item_keys` | `array[string]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CollectionState`

Used by: `POST /api/v1/work-items/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `data` | `object` | Yes | — |
| `item_identity` | `object` | Yes | — |
| `issues` | `array[CollectionIssue]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CorrectionFeedbackDTO`

Used by: `GET /api/v1/work-items/{ref_id}/view`, `POST /api/v1/work-items/{ref_id}/feedback/{feedback_key}/resolve`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `scope` | `string` | Yes | — |
| `item_key` | `string | null` | No | — |
| `message` | `string` | Yes | — |
| `key` | `string` | Yes | — |
| `actor_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `created_at` | `string` | Yes | — |
| `resolved_at` | `string | null` | No | — |
| `resolved_by_ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ManualOverrideState`

Used by: `POST /api/v1/work-items/{ref_id}/overrides`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `data` | `object` | Yes | — |
| `override_provenance` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `OptionResult`

Used by: `POST /api/v1/work-items/{ref_id}/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SelectOption_str_]` | Yes | — |
| `page` | `integer` | Yes | — |
| `size` | `integer` | Yes | — |
| `total` | `integer` | Yes | — |
| `dialect` | `string` | No |  Default: `bpms.options/1`. |
| `key_encoding` | `string` | No |  Default: `json-scalar/1`. |
| `state` | `string` | Yes | — |
| `generation` | `integer` | Yes | — |
| `locale` | `string` | Yes | — |
| `source_revision` | `string` | Yes | — |
| `dependency_fingerprint` | `string` | Yes | — |
| `dependencies` | `object` | Yes | — |
| `remote` | `RemoteSource | null` | No | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_OptionResult_`

Used by: `POST /api/v1/work-items/{ref_id}/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `OptionResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_WorkItemDTO__`

Used by: `POST /api/v1/work-items/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_WorkItemDTO_` | Yes | — |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "success": true,
  "request_id": "docs-purchase-001",
  "error": null,
  "code": 200,
  "result": {
    "items": [
      {
        "ref_id": "opaque-work-open",
        "request_ref_id": "opaque-request-running",
        "step_execution_ref_id": "opaque-step-execution",
        "form_version_ref_id": "opaque-form-version",
        "submission_ref_id": "opaque-submission",
        "item_identity": null,
        "design_snapshot": null,
        "status": "OPEN",
        "priority": 5,
        "claimant_ref_id": null,
        "outcome_key": null,
        "due_at": null,
        "claimed_at": null,
        "closed_at": null,
        "created_at": "2026-10-02T12:00:00Z",
        "read_at": null,
        "pinned_at": null,
        "archived_at": null,
        "watching_at": null
      }
    ],
    "page": 1,
    "size": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

### `Page_WorkItemDTO_`

Used by: `POST /api/v1/work-items/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[WorkItemDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "items": [
    {
      "ref_id": "opaque-work-open",
      "request_ref_id": "opaque-request-running",
      "step_execution_ref_id": "opaque-step-execution",
      "form_version_ref_id": "opaque-form-version",
      "submission_ref_id": "opaque-submission",
      "item_identity": null,
      "design_snapshot": null,
      "status": "OPEN",
      "priority": 5,
      "claimant_ref_id": null,
      "outcome_key": null,
      "due_at": null,
      "claimed_at": null,
      "closed_at": null,
      "created_at": "2026-10-02T12:00:00Z",
      "read_at": null,
      "pinned_at": null,
      "archived_at": null,
      "watching_at": null
    }
  ],
  "page": 1,
  "size": 20,
  "total": 1,
  "total_pages": 1
}
```

### `RemoteSource`

Used by: `POST /api/v1/work-items/{ref_id}/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `dialect` | `string` | No |  Default: `bpms.options/1`. |
| `dependencies` | `object` | No | Named schema-scope bindings. Missing/null parents block loading; changed parents invalidate previous results and selections. Repeated rows bind within the same item. |
| `enabled_when` | `string | null` | No | Optional typed boolean expression over request data. Controls option availability, never writes or clears data. |
| `parent_change` | `string` | No |  Default: `invalidate`. |
| `removed_value` | `string` | No |  Default: `reject`. |
| `kind` | `string` | No |  Default: `remote`. |
| `membership` | `string` | No |  Default: `snapshot`. |
| `url` | `string` | Yes | Exact HTTPS URL approved by FORM_CLIENT_OPTION_URLS. Client GET only; no server fetching, credentials, redirects, embedded query or fragment. Submitted keys must still belong to the pinned schema enum. |
| `method` | `string` | No |  Default: `GET`. |
| `credentials` | `string` | No |  Default: `omit`. |
| `redirects` | `string` | No |  Default: `error`. |
| `items_pointer` | `string` | No |  Default: `/result/items`. |
| `key_pointer` | `string` | No |  Default: `/key`. |
| `value_pointer` | `string` | No |  Default: `/value`. |
| `search_parameter` | `string` | No |  Default: `search`. |
| `page_parameter` | `string` | No |  Default: `page`. |
| `size_parameter` | `string` | No |  Default: `size`. |
| `selected_parameter` | `string` | No |  Default: `selected`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SelectOption_str_`

Used by: `POST /api/v1/work-items/{ref_id}/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubmissionAttachmentDTO`

Used by: `GET /api/v1/work-items/{ref_id}/attachments`, `POST /api/v1/work-items/{ref_id}/attachments`, `PUT /api/v1/work-items/{ref_id}/attachments/{attachment_ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `upload_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `field_path` | `string` | Yes | — |
| `position` | `integer` | Yes | — |
| `caption` | `string | null` | Yes | — |
| `kind` | `string` | Yes | — |
| `content_type` | `string` | Yes | — |
| `size_bytes` | `integer` | Yes | — |
| `contributing_group_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `created_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_CollectionState_`

Used by: `POST /api/v1/work-items/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `CollectionState` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ManualOverrideState_`

Used by: `POST /api/v1/work-items/{ref_id}/overrides`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ManualOverrideState` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_WorkItemAttachmentMutationDTO_`

Used by: `POST /api/v1/work-items/{ref_id}/attachments`, `PUT /api/v1/work-items/{ref_id}/attachments/{attachment_ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `WorkItemAttachmentMutationDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_WorkItemDTO_`

Used by: `DELETE /api/v1/work-items/{ref_id}/attachments/{attachment_ref_id}`, `GET /api/v1/work-items/{ref_id}`, `POST /api/v1/work-items/{ref_id}/archive`, `POST /api/v1/work-items/{ref_id}/cancel`, `POST /api/v1/work-items/{ref_id}/claim`, `POST /api/v1/work-items/{ref_id}/comment`, `POST /api/v1/work-items/{ref_id}/complete`, `POST /api/v1/work-items/{ref_id}/expire`, `POST /api/v1/work-items/{ref_id}/forward`, `POST /api/v1/work-items/{ref_id}/pin`, `POST /api/v1/work-items/{ref_id}/read`, `POST /api/v1/work-items/{ref_id}/reject`, `POST /api/v1/work-items/{ref_id}/release`, `POST /api/v1/work-items/{ref_id}/return`, `POST /api/v1/work-items/{ref_id}/save`, `POST /api/v1/work-items/{ref_id}/start`, `POST /api/v1/work-items/{ref_id}/watch`, `PUT /api/v1/work-items/{ref_id}/attachments`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `WorkItemDTO` | Yes | — |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "success": true,
  "request_id": "docs-purchase-001",
  "error": null,
  "code": 200,
  "data": {
    "ref_id": "opaque-work-claimed",
    "request_ref_id": "opaque-request-running",
    "step_execution_ref_id": "opaque-step-execution",
    "form_version_ref_id": "opaque-form-version",
    "submission_ref_id": "opaque-submission",
    "item_identity": null,
    "design_snapshot": null,
    "status": "CLAIMED",
    "priority": 5,
    "claimant_ref_id": "opaque-approver",
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

### `SuccessResponse_WorkItemViewDTO_`

Used by: `GET /api/v1/work-items/{ref_id}/view`, `POST /api/v1/work-items/{ref_id}/feedback/{feedback_key}/resolve`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `WorkItemViewDTO` | Yes | — |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "success": true,
  "request_id": "docs-purchase-001",
  "error": null,
  "code": 200,
  "data": {
    "work_item_ref_id": "opaque-work-claimed",
    "submission_ref_id": "opaque-submission",
    "view_key": "review",
    "purpose": "edit",
    "title": "Manager approval",
    "data": {
      "amount": "125.00"
    },
    "item_identity": null,
    "before_data": null,
    "render_schema": {
      "dialect": "bpms.render/1",
      "root": {
        "component": "vertical",
        "children": [
          {
            "component": "text",
            "scope": "/properties/amount",
            "label": "Amount"
          }
        ]
      },
      "outcomes": [
        "approve"
      ]
    },
    "actions": [
      {
        "key": "approve",
        "kind": "complete",
        "outcome_key": "approve",
        "title": "Approve",
        "confirmation": "Approve this purchase?",
        "required_scopes": [
          "/properties/amount"
        ],
        "require_comment": false,
        "validation": "complete"
      }
    ],
    "feedback": [],
    "autosave_conflict": "VERSION_CONFLICT",
    "unsaved_navigation": "warn_before_leave"
  }
}
```

### `SuccessResponse_list_SubmissionAttachmentDTO__`

Used by: `GET /api/v1/work-items/{ref_id}/attachments`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `array[SubmissionAttachmentDTO]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TaskActionViewDTO`

Used by: `GET /api/v1/work-items/{ref_id}/view`, `POST /api/v1/work-items/{ref_id}/feedback/{feedback_key}/resolve`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `kind` | `string` | Yes | — |
| `outcome_key` | `string` | Yes | — |
| `title` | `string` | Yes | — |
| `confirmation` | `string | null` | Yes | — |
| `required_scopes` | `array[string]` | Yes | — |
| `require_comment` | `boolean` | Yes | — |
| `validation` | `string` | Yes | — |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "key": "approve",
  "kind": "complete",
  "outcome_key": "approve",
  "title": "Approve",
  "confirmation": "Approve this purchase?",
  "required_scopes": [
    "/properties/amount"
  ],
  "require_comment": false,
  "validation": "complete"
}
```

### `WorkItemAttachmentMutationDTO`

Used by: `POST /api/v1/work-items/{ref_id}/attachments`, `PUT /api/v1/work-items/{ref_id}/attachments/{attachment_ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `work_item_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `attachment` | `SubmissionAttachmentDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkItemDTO`

Used by: `DELETE /api/v1/work-items/{ref_id}/attachments/{attachment_ref_id}`, `GET /api/v1/work-items/{ref_id}`, `POST /api/v1/work-items/search`, `POST /api/v1/work-items/{ref_id}/archive`, `POST /api/v1/work-items/{ref_id}/cancel`, `POST /api/v1/work-items/{ref_id}/claim`, `POST /api/v1/work-items/{ref_id}/comment`, `POST /api/v1/work-items/{ref_id}/complete`, `POST /api/v1/work-items/{ref_id}/expire`, `POST /api/v1/work-items/{ref_id}/forward`, `POST /api/v1/work-items/{ref_id}/pin`, `POST /api/v1/work-items/{ref_id}/read`, `POST /api/v1/work-items/{ref_id}/reject`, `POST /api/v1/work-items/{ref_id}/release`, `POST /api/v1/work-items/{ref_id}/return`, `POST /api/v1/work-items/{ref_id}/save`, `POST /api/v1/work-items/{ref_id}/start`, `POST /api/v1/work-items/{ref_id}/watch`, `PUT /api/v1/work-items/{ref_id}/attachments`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `request_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `step_execution_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `form_version_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `submission_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `item_identity` | `object | null` | No | — |
| `design_snapshot` | `object | null` | No | Pinned client variant and interaction revision with locale-resolved presentation text. Reads resolve the exact pinned form catalog using Accept-Language without rewriting audit snapshots or canonical data. localization reports resolved_locale, direction, catalog_revision and per-message locale/source_revision. Option values and outcomes remain canonical. Authorized responses are private, no-store; locale changes never select a different variant. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `priority` | `integer` | Yes | — |
| `claimant_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `outcome_key` | `string | null` | Yes | — |
| `due_at` | `string | null` | Yes | — |
| `claimed_at` | `string | null` | Yes | — |
| `closed_at` | `string | null` | Yes | — |
| `created_at` | `string` | Yes | — |
| `read_at` | `string | null` | No | — |
| `pinned_at` | `string | null` | No | — |
| `archived_at` | `string | null` | No | — |
| `watching_at` | `string | null` | No | — |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "ref_id": "opaque-work-open",
  "request_ref_id": "opaque-request-running",
  "step_execution_ref_id": "opaque-step-execution",
  "form_version_ref_id": "opaque-form-version",
  "submission_ref_id": "opaque-submission",
  "item_identity": null,
  "design_snapshot": null,
  "status": "OPEN",
  "priority": 5,
  "claimant_ref_id": null,
  "outcome_key": null,
  "due_at": null,
  "claimed_at": null,
  "closed_at": null,
  "created_at": "2026-10-02T12:00:00Z",
  "read_at": null,
  "pinned_at": null,
  "archived_at": null,
  "watching_at": null
}
```

### `WorkItemViewDTO`

Used by: `GET /api/v1/work-items/{ref_id}/view`, `POST /api/v1/work-items/{ref_id}/feedback/{feedback_key}/resolve`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `work_item_ref_id` | `string` | Yes | Current revision-bearing ref for autosave and actions. |
| `submission_ref_id` | `string` | Yes | Pinned draft/submitted form revision ref. |
| `view_key` | `string` | Yes | Named task view selected from the pinned workflow step. |
| `purpose` | `string` | Yes | — |
| `title` | `string` | Yes | Localized plain-text task-view title. |
| `data` | `object` | Yes | Current canonical data filtered by the task read policy and named view. |
| `item_identity` | `object | null` | Yes | Stable row keys only for readable collection paths. |
| `before_data` | `object | null` | Yes | Prior submitted canonical data through the same read filter, or null. |
| `render_schema` | `object` | Yes | Pinned client variant's bpms.render/1 document with unreadable nodes removed and messages localized. |
| `actions` | `array[TaskActionViewDTO]` | Yes | Available declared actions for the current claimant; empty for observers or closed work. |
| `feedback` | `array[CorrectionFeedbackDTO]` | Yes | Visible feedback keyed by stable field scope and optional collection item key. |
| `autosave_conflict` | `string` | No |  Default: `VERSION_CONFLICT`. |
| `unsaved_navigation` | `string` | No |  Default: `warn_before_leave`. |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "work_item_ref_id": "opaque-work-claimed",
  "submission_ref_id": "opaque-submission",
  "view_key": "review",
  "purpose": "edit",
  "title": "Manager approval",
  "data": {
    "amount": "125.00"
  },
  "item_identity": null,
  "before_data": null,
  "render_schema": {
    "dialect": "bpms.render/1",
    "root": {
      "component": "vertical",
      "children": [
        {
          "component": "text",
          "scope": "/properties/amount",
          "label": "Amount"
        }
      ]
    },
    "outcomes": [
      "approve"
    ]
  },
  "actions": [
    {
      "key": "approve",
      "kind": "complete",
      "outcome_key": "approve",
      "title": "Approve",
      "confirmation": "Approve this purchase?",
      "required_scopes": [
        "/properties/amount"
      ],
      "require_comment": false,
      "validation": "complete"
    }
  ],
  "feedback": [],
  "autosave_conflict": "VERSION_CONFLICT",
  "unsaved_navigation": "warn_before_leave"
}
```
