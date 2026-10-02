---
tags: [api, dto, task-executions]
---

# task-executions response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `PageResponse_Page_SelectOption_str___`

Used by: `GET /api/v1/tasks/queues/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_SelectOption_str__` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_TaskExecutionDTO__`

Used by: `POST /api/v1/tasks/executions/report`, `POST /api/v1/tasks/executions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_TaskExecutionDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_SelectOption_str__`

Used by: `GET /api/v1/tasks/queues/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SelectOption_str_]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_TaskExecutionDTO_`

Used by: `POST /api/v1/tasks/executions/report`, `POST /api/v1/tasks/executions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[TaskExecutionDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SelectOption_str_`

Used by: `GET /api/v1/tasks/queues/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_TaskControlDTO_`

Used by: `POST /api/v1/tasks/executions/{task_id}/retry`, `POST /api/v1/tasks/executions/{task_id}/revoke`, `POST /api/v1/tasks/run`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `TaskControlDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_TaskExecutionDTO_`

Used by: `GET /api/v1/tasks/executions/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `TaskExecutionDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TaskControlDTO`

Used by: `POST /api/v1/tasks/executions/{task_id}/retry`, `POST /api/v1/tasks/executions/{task_id}/revoke`, `POST /api/v1/tasks/run`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `task_id` | `string` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TaskExecutionDTO`

Used by: `GET /api/v1/tasks/executions/{ref_id}`, `POST /api/v1/tasks/executions/report`, `POST /api/v1/tasks/executions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque versioned execution reference. |
| `task_id` | `string` | Yes | — |
| `task_name` | `string` | Yes | — |
| `queue` | `string | null` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `args` | `array[object] | null` | Yes | — |
| `kwargs` | `object | null` | Yes | — |
| `result` | `object | null` | Yes | — |
| `traceback` | `string | null` | Yes | — |
| `worker` | `string | null` | Yes | — |
| `retries` | `integer` | Yes | — |
| `started_at` | `string | null` | Yes | — |
| `finished_at` | `string | null` | Yes | — |
| `duration_seconds` | `number | null` | Yes | — |
| `created_at` | `string` | Yes | — |
| `updated_at` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
