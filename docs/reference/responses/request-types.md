---
tags: [api, dto, request-types]
---

# request-types response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `EligibleRequestTypeDTO`

Used by: `POST /api/v1/request-types/eligible/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `code` | `string` | Yes | — |
| `name` | `string` | Yes | — |
| `workflow_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `form_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `render_dialect` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HistoryRecordDTO`

Used by: `POST /api/v1/request-types/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `string` | Yes | — |
| `entity_id` | `string` | Yes | — |
| `modifier_type` | `string` | Yes | — |
| `modifier_id` | `string` | Yes | — |
| `changed_at` | `string` | Yes | — |
| `operation` | `string` | Yes | — |
| `request_id` | `string | null` | No | — |
| `trace_id` | `string | null` | No | — |
| `reason` | `string | null` | No | — |
| `source_ip` | `string | null` | No | — |
| `user_agent` | `string | null` | No | — |
| `from_values` | `object` | Yes | — |
| `to_values` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_EligibleRequestTypeDTO__`

Used by: `POST /api/v1/request-types/eligible/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_EligibleRequestTypeDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_HistoryRecordDTO__`

Used by: `POST /api/v1/request-types/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_RequestTypeDTO__`

Used by: `POST /api/v1/request-types/report`, `POST /api/v1/request-types/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_RequestTypeDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_EligibleRequestTypeDTO_`

Used by: `POST /api/v1/request-types/eligible/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[EligibleRequestTypeDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/request-types/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_RequestTypeDTO_`

Used by: `POST /api/v1/request-types/report`, `POST /api/v1/request-types/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[RequestTypeDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RequestTypeClientTargetDTO`

Used by: `GET /api/v1/request-types/{ref_id}`, `POST /api/v1/request-types`, `POST /api/v1/request-types/report`, `POST /api/v1/request-types/search`, `PUT /api/v1/request-types/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `client_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `minimum_release` | `string | null` | No | — |
| `maximum_release_exclusive` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RequestTypeDTO`

Used by: `GET /api/v1/request-types/{ref_id}`, `POST /api/v1/request-types`, `POST /api/v1/request-types/report`, `POST /api/v1/request-types/search`, `PUT /api/v1/request-types/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `code` | `string` | Yes | — |
| `name` | `string` | Yes | — |
| `workflow_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `form_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `is_active` | `boolean` | No |  Default: `True`. |
| `default_priority` | `integer | null` | No | — |
| `client_targets` | `array[RequestTypeClientTargetDTO]` | No | Authoritative confidential-client/release restrictions. On PUT, omission preserves existing restrictions; an explicit empty list deliberately removes them. |
| `allow_cross_client_resume` | `boolean` | No |  Default: `False`. |
| `extension_contract` | `string | null` | No | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `created_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/request-types/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_RequestTypeDTO_`

Used by: `GET /api/v1/request-types/{ref_id}`, `POST /api/v1/request-types`, `PUT /api/v1/request-types/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `RequestTypeDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
