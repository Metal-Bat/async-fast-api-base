---
tags: [api, dto, inbox]
---

# inbox response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `AccountTarget`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `available` | `boolean` | Yes | — |
| `ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `kind` | `string` | No |  Default: `account`. |
| `route_key` | `string` | No |  Default: `me`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CalendarTarget`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `available` | `boolean` | Yes | — |
| `ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `kind` | `string` | No |  Default: `calendar`. |
| `route_key` | `string` | No |  Default: `calendar_events`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CaseTarget`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `available` | `boolean` | Yes | — |
| `ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `kind` | `string` | No |  Default: `case`. |
| `route_key` | `string` | No |  Default: `business_requests`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FutureTarget`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `available` | `boolean` | Yes | — |
| `ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `kind` | `string` | Yes | — |
| `route_key` | `null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `InboxDTO`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | `integer` | No |  Default: `1`. |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `template_key` | `string` | Yes | — |
| `template_version` | `string` | Yes | — |
| `locale` | `string` | Yes | — |
| `subject` | `string` | Yes | — |
| `content` | `string | null` | Yes | — |
| `priority` | `integer` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `read_at` | `string | null` | Yes | — |
| `created_at` | `string` | Yes | — |
| `target` | `CaseTarget | WorkTarget | ReportTarget | AccountTarget | SupportTarget | CalendarTarget | FutureTarget` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_InboxDTO__`

Used by: `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_InboxDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_InboxDTO_`

Used by: `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[InboxDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ReportTarget`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `available` | `boolean` | Yes | — |
| `ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `kind` | `string` | No |  Default: `report`. |
| `route_key` | `string` | No |  Default: `reports`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_InboxDTO_`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `InboxDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_UnreadDTO_`

Used by: `GET /api/v1/inbox/unread`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `UnreadDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SupportTarget`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `available` | `boolean` | Yes | — |
| `ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `kind` | `string` | No |  Default: `support`. |
| `route_key` | `string` | No |  Default: `support_incidents`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `UnreadDTO`

Used by: `GET /api/v1/inbox/unread`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `total` | `integer` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkTarget`

Used by: `GET /api/v1/inbox/{ref_id}`, `POST /api/v1/inbox/report`, `POST /api/v1/inbox/search`, `POST /api/v1/inbox/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `available` | `boolean` | Yes | — |
| `ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `kind` | `string` | Yes | — |
| `route_key` | `string` | No |  Default: `work_items`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
