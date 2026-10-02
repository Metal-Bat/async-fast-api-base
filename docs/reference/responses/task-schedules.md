---
tags: [api, dto, task-schedules]
---

# task-schedules response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `HistoryRecordDTO`

Used by: `POST /api/v1/tasks/schedules/{ref_id}/history`

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

Used by: `POST /api/v1/tasks/schedules/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_PeriodicTaskDTO__`

Used by: `POST /api/v1/tasks/schedules/report`, `POST /api/v1/tasks/schedules/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_PeriodicTaskDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/tasks/schedules/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_PeriodicTaskDTO_`

Used by: `POST /api/v1/tasks/schedules/report`, `POST /api/v1/tasks/schedules/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[PeriodicTaskDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PeriodicTaskDTO`

Used by: `GET /api/v1/tasks/schedules/{ref_id}`, `POST /api/v1/tasks/schedules`, `POST /api/v1/tasks/schedules/report`, `POST /api/v1/tasks/schedules/search`, `PUT /api/v1/tasks/schedules/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | `string` | Yes | Unique schedule name. |
| `task_name` | `string` | Yes | Registered Celery task name. |
| `queue` | `string | null` | No | Destination queue. |
| `schedule_type` | `string` | Yes | — |
| `interval_seconds` | `number | null` | No | — |
| `cron_minute` | `string | null` | No | — |
| `cron_hour` | `string | null` | No | — |
| `cron_day_of_week` | `string | null` | No | — |
| `cron_day_of_month` | `string | null` | No | — |
| `cron_month_of_year` | `string | null` | No | — |
| `clocked_at` | `string | null` | No | — |
| `args` | `array[object]` | No | — |
| `kwargs` | `object` | No | — |
| `enabled` | `boolean` | No |  Default: `True`. |
| `one_off` | `boolean` | No |  Default: `False`. |
| `start_at` | `string | null` | No | — |
| `expires_at` | `string | null` | No | — |
| `ref_id` | `string` | Yes | Opaque versioned schedule reference. |
| `created_at` | `string` | Yes | — |
| `updated_at` | `string | null` | Yes | — |
| `deleted_at` | `string | null` | Yes | — |
| `last_run_at` | `string | null` | Yes | — |
| `total_run_count` | `integer` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/tasks/schedules/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_PeriodicTaskDTO_`

Used by: `GET /api/v1/tasks/schedules/{ref_id}`, `POST /api/v1/tasks/schedules`, `PUT /api/v1/tasks/schedules/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `PeriodicTaskDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
