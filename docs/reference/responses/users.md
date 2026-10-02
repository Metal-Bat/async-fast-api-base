---
tags: [api, dto, users]
---

# users response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `HistoryRecordDTO`

Used by: `POST /api/v1/admin/users/{ref_id}/history`

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

Used by: `POST /api/v1/admin/users/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_UserDTO__`

Used by: `POST /api/v1/admin/users/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_UserDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_WorkGroupSelectDTO__`

Used by: `POST /api/v1/admin/users/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_WorkGroupSelectDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/admin/users/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_UserDTO_`

Used by: `POST /api/v1/admin/users/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[UserDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_WorkGroupSelectDTO_`

Used by: `POST /api/v1/admin/users/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[WorkGroupSelectDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ReportDetailDTO`

Used by: `POST /api/v1/admin/users/report`

Owned report detail including the archive password.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque report reference. |
| `definition_key` | `string` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `file_name` | `string | null` | Yes | — |
| `file_size` | `integer | null` | Yes | — |
| `started_at` | `string | null` | Yes | — |
| `completed_at` | `string | null` | Yes | — |
| `expires_at` | `string` | Yes | — |
| `created_at` | `string` | Yes | — |
| `row_count` | `integer | null` | Yes | — |
| `exported_row_count` | `integer` | Yes | — |
| `content_type` | `string | null` | Yes | — |
| `checksum_sha256` | `string | null` | Yes | — |
| `error_code` | `string | null` | Yes | — |
| `error_message` | `string | null` | Yes | — |
| `download_count` | `integer` | Yes | — |
| `last_downloaded_at` | `string | null` | Yes | — |
| `zip_password` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/admin/users/{ref_id}`, `POST /api/v1/admin/users/{ref_id}/reset-password`, `POST /api/v1/admin/users/{ref_id}/roles`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ReportDetailDTO_`

Used by: `POST /api/v1/admin/users/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ReportDetailDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_UserDTO_`

Used by: `GET /api/v1/admin/users/{ref_id}`, `POST /api/v1/admin/users`, `POST /api/v1/admin/users/{ref_id}/restore`, `PUT /api/v1/admin/users/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `UserDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `UserDTO`

Used by: `GET /api/v1/admin/users/{ref_id}`, `POST /api/v1/admin/users`, `POST /api/v1/admin/users/search`, `POST /api/v1/admin/users/{ref_id}/restore`, `PUT /api/v1/admin/users/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque versioned user reference. |
| `username` | `string` | Yes | Unique username. |
| `email` | `string | null` | Yes | Unique email address. |
| `created_at` | `string` | Yes | UTC creation timestamp. |
| `updated_at` | `string | null` | Yes | UTC timestamp of the most recent update. |
| `deleted_at` | `string | null` | Yes | UTC soft-deletion timestamp. |
| `first_name` | `string | null` | No | Given name. |
| `last_name` | `string | null` | No | Family name. |
| `is_superuser` | `boolean` | Yes | Administrative privilege flag. |
| `is_active` | `boolean` | Yes | Whether the user is not soft-deleted. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkGroupSelectDTO`

Used by: `POST /api/v1/admin/users/select`

Resource select option using the shared wire contract.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
