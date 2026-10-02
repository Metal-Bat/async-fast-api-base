---
tags: [api, dto, notifications]
---

# notifications response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `DeliveryDTO`

Used by: `GET /api/v1/notifications/{ref_id}`, `POST /api/v1/notifications/report`, `POST /api/v1/notifications/search`, `POST /api/v1/notifications/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `channel` | `string` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `attempt_count` | `integer` | Yes | — |
| `provider_message_ref` | `string | null` | Yes | — |
| `last_error_code` | `string | null` | Yes | — |
| `next_attempt_at` | `string | null` | Yes | — |
| `delivered_at` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `NotificationDTO`

Used by: `GET /api/v1/notifications/{ref_id}`, `POST /api/v1/notifications/report`, `POST /api/v1/notifications/search`, `POST /api/v1/notifications/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `request_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `process_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `template_key` | `string` | Yes | — |
| `template_version` | `string` | Yes | — |
| `locale` | `string` | Yes | — |
| `subject` | `string` | Yes | — |
| `content` | `string | null` | Yes | — |
| `priority` | `integer` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `read_at` | `string | null` | Yes | — |
| `created_at` | `string` | Yes | — |
| `deliveries` | `array[DeliveryDTO]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_NotificationDTO__`

Used by: `POST /api/v1/notifications/report`, `POST /api/v1/notifications/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_NotificationDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_NotificationDTO_`

Used by: `POST /api/v1/notifications/report`, `POST /api/v1/notifications/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[NotificationDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NotificationDTO_`

Used by: `GET /api/v1/notifications/{ref_id}`, `POST /api/v1/notifications/{ref_id}/read`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `NotificationDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
