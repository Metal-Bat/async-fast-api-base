---
tags: [api, dto, audit-events]
---

# audit-events response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `AuthAuditEventDTO`

Used by: `GET /api/v1/admin/audit-events/{ref_id}`, `POST /api/v1/admin/audit-events/report`, `POST /api/v1/admin/audit-events/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque versioned audit-event reference. |
| `user_id` | `string | null` | Yes | — |
| `event_type` | `string` | Yes | — |
| `success` | `boolean` | Yes | — |
| `request_id` | `string | null` | Yes | — |
| `ip_address` | `string | null` | Yes | — |
| `user_agent` | `string | null` | Yes | — |
| `details` | `object` | Yes | — |
| `created_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_AuthAuditEventDTO__`

Used by: `POST /api/v1/admin/audit-events/report`, `POST /api/v1/admin/audit-events/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_AuthAuditEventDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_AuthAuditEventDTO_`

Used by: `POST /api/v1/admin/audit-events/report`, `POST /api/v1/admin/audit-events/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[AuthAuditEventDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_AuthAuditEventDTO_`

Used by: `GET /api/v1/admin/audit-events/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `AuthAuditEventDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
