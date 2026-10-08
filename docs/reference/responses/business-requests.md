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
| `process_ref_id` | `string | null` | No | Real authorized root-process ref for tracking, or null for a draft/no process. Never derive a process ref from another entity reference. |
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

### `PageResponse_Page_ResourceHistoryDTO__`

Used by: `POST /api/v1/business-requests/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_ResourceHistoryDTO_` | Yes | — |

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

### `Page_ResourceHistoryDTO_`

Used by: `POST /api/v1/business-requests/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[ResourceHistoryDTO]` | No | — |
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

### `ResourceHistoryDTO`

Used by: `POST /api/v1/business-requests/{ref_id}/history`

Authorized timeline metadata; no canonical values or actor identifiers.

فرادادهٔ مجاز تاریخچه؛ بدون مقادیر فرم یا شناسهٔ کاربران.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `changed_at` | `string` | Yes | UTC change timestamp. / زمان تغییر به UTC. |
| `operation` | `string` | Yes | Persisted lifecycle action. / رخداد ذخیره‌شده. |
| `version` | `integer | null` | No | Recorded revision when available; null otherwise. / نسخه در صورت موجود بودن؛ در غیر این صورت null. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RuntimeActionDTO`

Used by: `GET /api/v1/business-requests/{ref_id}/view`, `POST /api/v1/business-requests/{ref_id}/collections/edit`

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

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RuntimeFieldMetadataDTO`

Used by: `GET /api/v1/business-requests/{ref_id}/view`, `POST /api/v1/business-requests/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `scope` | `string` | Yes | Visible JSON Schema property/items scope. |
| `validation_schema` | `object` | Yes | Bounded compiled schema of this visible field only. No defaults, examples, hidden properties or shared definitions; backend validates the full canonical document. |
| `writable` | `boolean` | Yes | — |
| `required` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RuntimeFormStateDTO`

Used by: `GET /api/v1/business-requests/{ref_id}/view`, `POST /api/v1/business-requests/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `runtime_dialect` | `string` | No |  Default: `bpms.runtime/1`. |
| `resource_kind` | `string` | Yes | — |
| `resource_ref_id` | `string` | Yes | Current opaque revision-bearing reference for the owning request/work item; replace after every mutation. |
| `form_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `form_version_number` | `integer` | Yes | — |
| `submission_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `design_key` | `string` | Yes | Exact pinned client variant; locale changes cannot change this key. |
| `render_dialect` | `string` | No |  Default: `bpms.render/1`. |
| `data_dialect` | `string` | No |  Default: `https://json-schema.org/draft/2020-12/schema`. |
| `view_key` | `string` | Yes | — |
| `purpose` | `string` | Yes | — |
| `resolved_locale` | `string` | Yes | Locale selected by the pinned catalog, or negotiated en/fa fallback. |
| `direction` | `string` | Yes | — |
| `data` | `object` | Yes | Canonical actor-visible values. Hidden values are preserved only on the server. |
| `item_identity` | `object` | Yes | Stable row keys for visible collection paths only. |
| `page_settings` | `object` | No | Pinned display-only settings; optional pages contains at most 32 unique key/title/scopes entries with actor-readable scopes only. No scripts, bindings or runtime values. |
| `before_data` | `object | null` | No | Prior submitted data filtered through the same task view, or null when unavailable. |
| `before_item_identity` | `object | null` | No | Actor-filtered prior row identities; null when unavailable. / هویت مجاز ردیف‌های پیشین؛ در صورت نبودن null. |
| `render_schema` | `object` | Yes | Actor-filtered bounded bpms.render/1 display document. Server-evaluated calculation metadata and client expressions are omitted; writable_scopes is authoritative for editability. |
| `readable_scopes` | `array[string]` | Yes | — |
| `writable_scopes` | `array[string]` | Yes | — |
| `required_scopes` | `array[string]` | Yes | — |
| `field_metadata` | `array[RuntimeFieldMetadataDTO]` | Yes | — |
| `actions` | `array[RuntimeActionDTO]` | No | — |
| `override_provenance` | `object` | No | Visible override actor/reason/value/time only; input checksums remain server-only. |
| `issues` | `array[object]` | No | Safe visible pointer/code pairs. Hidden canonical validation failures produce a generic task.validation issue. |

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

### `SuccessResponse_RuntimeFormStateDTO_`

Used by: `GET /api/v1/business-requests/{ref_id}/view`, `POST /api/v1/business-requests/{ref_id}/collections/edit`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `RuntimeFormStateDTO` | Yes | — |

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
