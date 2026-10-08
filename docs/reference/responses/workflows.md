---
tags: [api, dto, workflows]
---

# workflows response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `GraphIssue`

Used by: `POST /api/v1/workflows/validate`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `code` | `string` | Yes | — |
| `line` | `integer | null` | No | — |
| `column` | `integer | null` | No | — |
| `expected_schema` | `object | null` | No | — |
| `actual_schema` | `object | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `GraphValidationResult`

Used by: `POST /api/v1/workflows/validate`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `valid` | `boolean` | Yes | — |
| `issues` | `array[GraphIssue]` | No | — |
| `checksum` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HistoryRecordDTO`

Used by: `POST /api/v1/workflows/{ref_id}/history`

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

### `PageResponse_Page_HistoryRecordDTO__`

Used by: `POST /api/v1/workflows/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_WorkflowDTO__`

Used by: `POST /api/v1/workflows/report`, `POST /api/v1/workflows/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_WorkflowDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_WorkflowGrantViewDTO__`

Used by: `POST /api/v1/workflows/{ref_id}/grants/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_WorkflowGrantViewDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/workflows/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_WorkflowDTO_`

Used by: `POST /api/v1/workflows/report`, `POST /api/v1/workflows/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[WorkflowDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_WorkflowGrantViewDTO_`

Used by: `POST /api/v1/workflows/{ref_id}/grants/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[WorkflowGrantViewDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_GraphValidationResult_`

Used by: `POST /api/v1/workflows/validate`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `GraphValidationResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/workflows/{ref_id}`, `DELETE /api/v1/workflows/{ref_id}/grants/{grant_ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_WorkflowDTO_`

Used by: `GET /api/v1/workflows/{ref_id}`, `POST /api/v1/workflows`, `PUT /api/v1/workflows/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `WorkflowDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_WorkflowGrantViewDTO_`

Used by: `POST /api/v1/workflows/{ref_id}/grants`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `WorkflowGrantViewDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkflowDTO`

Used by: `GET /api/v1/workflows/{ref_id}`, `POST /api/v1/workflows`, `POST /api/v1/workflows/report`, `POST /api/v1/workflows/search`, `PUT /api/v1/workflows/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `code` | `string` | Yes | — |
| `name` | `string` | Yes | — |
| `access_mode` | `string` | No |  Default: `RESTRICTED`. |
| `is_active` | `boolean` | No |  Default: `True`. |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `created_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkflowGrantViewDTO`

Used by: `POST /api/v1/workflows/{ref_id}/grants`, `POST /api/v1/workflows/{ref_id}/grants/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `user_ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `work_group_ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `can_view` | `boolean` | No |  Default: `True`. |
| `can_start` | `boolean` | No |  Default: `False`. |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `workflow_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
