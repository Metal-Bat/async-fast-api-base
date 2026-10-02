---
tags: [api, dto, business-requests]
---

# business-requests response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `AttachmentMutationDTO`

Used by: `POST /api/v1/business-requests/{ref_id}/attachments`, `PUT /api/v1/business-requests/{ref_id}/attachments/{attachment_ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `request_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `attachment` | `SubmissionAttachmentDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `BusinessRequestDTO`

Used by: `DELETE /api/v1/business-requests/{ref_id}/attachments/{attachment_ref_id}`, `GET /api/v1/business-requests/{ref_id}`, `POST /api/v1/business-requests`, `POST /api/v1/business-requests/report`, `POST /api/v1/business-requests/search`, `POST /api/v1/business-requests/{ref_id}/cancel`, `POST /api/v1/business-requests/{ref_id}/resume-presentation`, `POST /api/v1/business-requests/{ref_id}/submit`, `PUT /api/v1/business-requests/{ref_id}`, `PUT /api/v1/business-requests/{ref_id}/attachments`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `request_type_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `requester_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `workflow_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `form_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `priority` | `integer` | Yes | — |
| `data` | `object` | Yes | — |
| `item_identity` | `object | null` | No | — |
| `submitted_at` | `string | null` | Yes | — |
| `closed_at` | `string | null` | Yes | — |
| `created_at` | `string` | Yes | — |
| `origin_client` | `object | null` | No | — |
| `design_snapshot` | `object | null` | No | Pinned client variant and interaction revision with locale-resolved presentation text. Reads resolve the exact pinned form catalog using Accept-Language without rewriting audit snapshots or canonical data. localization reports resolved_locale, direction, catalog_revision and per-message locale/source_revision. Option values and outcomes remain canonical. Authorized responses are private, no-store; locale changes never select a different variant. |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "ref_id": "opaque-request-draft",
  "request_type_ref_id": "opaque-request-type",
  "requester_ref_id": "opaque-requester",
  "workflow_version_ref_id": "opaque-workflow-version",
  "form_version_ref_id": "opaque-form-version",
  "status": "DRAFT",
  "priority": 5,
  "data": {
    "amount": "125.00"
  },
  "item_identity": null,
  "submitted_at": null,
  "closed_at": null,
  "created_at": "2026-10-02T12:00:00Z",
  "origin_client": null,
  "design_snapshot": null
}
```

### `CollectionIssue`

Used by: `POST /api/v1/business-requests/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `code` | `string` | Yes | — |
| `item_keys` | `array[string]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CollectionState`

Used by: `POST /api/v1/business-requests/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `data` | `object` | Yes | — |
| `item_identity` | `object` | Yes | — |
| `issues` | `array[CollectionIssue]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ManualOverrideState`

Used by: `POST /api/v1/business-requests/{ref_id}/overrides`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `data` | `object` | Yes | — |
| `override_provenance` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `OptionResult`

Used by: `POST /api/v1/business-requests/{ref_id}/options`

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

Used by: `POST /api/v1/business-requests/{ref_id}/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `OptionResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_BusinessRequestDTO__`

Used by: `POST /api/v1/business-requests/report`, `POST /api/v1/business-requests/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_BusinessRequestDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_BusinessRequestDTO_`

Used by: `POST /api/v1/business-requests/report`, `POST /api/v1/business-requests/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[BusinessRequestDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RemoteSource`

Used by: `POST /api/v1/business-requests/{ref_id}/options`

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

Used by: `POST /api/v1/business-requests/{ref_id}/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubmissionAttachmentDTO`

Used by: `GET /api/v1/business-requests/{ref_id}/attachments`, `POST /api/v1/business-requests/{ref_id}/attachments`, `PUT /api/v1/business-requests/{ref_id}/attachments/{attachment_ref_id}`

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

### `SuccessResponse_AttachmentMutationDTO_`

Used by: `POST /api/v1/business-requests/{ref_id}/attachments`, `PUT /api/v1/business-requests/{ref_id}/attachments/{attachment_ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `AttachmentMutationDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_BusinessRequestDTO_`

Used by: `DELETE /api/v1/business-requests/{ref_id}/attachments/{attachment_ref_id}`, `GET /api/v1/business-requests/{ref_id}`, `POST /api/v1/business-requests`, `POST /api/v1/business-requests/{ref_id}/cancel`, `POST /api/v1/business-requests/{ref_id}/resume-presentation`, `POST /api/v1/business-requests/{ref_id}/submit`, `PUT /api/v1/business-requests/{ref_id}`, `PUT /api/v1/business-requests/{ref_id}/attachments`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `BusinessRequestDTO` | Yes | — |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "success": true,
  "request_id": "docs-purchase-001",
  "error": null,
  "code": 201,
  "data": {
    "ref_id": "opaque-request-draft",
    "request_type_ref_id": "opaque-request-type",
    "requester_ref_id": "opaque-requester",
    "workflow_version_ref_id": "opaque-workflow-version",
    "form_version_ref_id": "opaque-form-version",
    "status": "DRAFT",
    "priority": 5,
    "data": {
      "amount": "125.00"
    },
    "item_identity": null,
    "submitted_at": null,
    "closed_at": null,
    "created_at": "2026-10-02T12:00:00Z",
    "origin_client": null,
    "design_snapshot": null
  }
}
```

### `SuccessResponse_CollectionState_`

Used by: `POST /api/v1/business-requests/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `CollectionState` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ManualOverrideState_`

Used by: `POST /api/v1/business-requests/{ref_id}/overrides`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ManualOverrideState` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_list_SubmissionAttachmentDTO__`

Used by: `GET /api/v1/business-requests/{ref_id}/attachments`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `array[SubmissionAttachmentDTO]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
