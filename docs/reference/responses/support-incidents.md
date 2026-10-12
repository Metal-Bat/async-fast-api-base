---
tags: [api, dto, support-incidents]
---

# support-incidents response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `IncidentDTO`

Used by: `GET /api/v1/support/incidents/by-support/{support_ref}`, `GET /api/v1/support/incidents/{ref_id}`, `POST /api/v1/support/incidents/report`, `POST /api/v1/support/incidents/search`, `POST /api/v1/support/incidents/{ref_id}/acknowledge`, `POST /api/v1/support/incidents/{ref_id}/resolve`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque incident reference containing its current version. |
| `support_ref` | `string` | Yes | Correlation UUID; inspection requires support.incidents.manage. |
| `category` | `string` | Yes | Canonical incident category; localized labels do not change this value. |
| `error_code` | `integer` | Yes | Stable safe error code; exception messages and stack traces are never accepted. |
| `operation` | `string` | Yes | Safe operation identifier; contains no submitted business payload. |
| `state` | `string` | Yes | Incident lifecycle state: OPEN, ACKNOWLEDGED or RESOLVED. |
| `occurrence_count` | `integer` | Yes | Number of grouped occurrences retained for this incident. |
| `first_seen_at` | `string` | Yes | Timezone-aware UTC instant of the first grouped occurrence. |
| `last_seen_at` | `string` | Yes | Timezone-aware UTC instant of the latest grouped occurrence. |
| `expires_at` | `string` | Yes | Timezone-aware UTC retention deadline; expired incidents may be removed. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `IncidentHistoryDTO`

Used by: `POST /api/v1/support/incidents/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `changed_at` | `string` | Yes | Timezone-aware UTC instant of this lifecycle transition. |
| `operation` | `string` | Yes | Safe operation identifier; contains no submitted business payload. |
| `from_state` | `string | null` | Yes | Previous canonical state; null for the initial transition. |
| `to_state` | `string | null` | Yes | Resulting canonical state; null when no destination state is recorded. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_IncidentDTO__`

Used by: `POST /api/v1/support/incidents/report`, `POST /api/v1/support/incidents/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_IncidentDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_IncidentHistoryDTO__`

Used by: `POST /api/v1/support/incidents/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_IncidentHistoryDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_IncidentDTO_`

Used by: `POST /api/v1/support/incidents/report`, `POST /api/v1/support/incidents/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[IncidentDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_IncidentHistoryDTO_`

Used by: `POST /api/v1/support/incidents/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[IncidentHistoryDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_IncidentDTO_`

Used by: `GET /api/v1/support/incidents/by-support/{support_ref}`, `GET /api/v1/support/incidents/{ref_id}`, `POST /api/v1/support/incidents/{ref_id}/acknowledge`, `POST /api/v1/support/incidents/{ref_id}/resolve`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `IncidentDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_SupportReceipt_`

Used by: `POST /api/v1/support/client-failures`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `SupportReceipt` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SupportReceipt`

Used by: `POST /api/v1/support/client-failures`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `persisted` | `boolean` | Yes | True only after independent incident commit; false means durability is unavailable. |
| `support_ref` | `string | null` | Yes | Correlation identity only; support.incidents.manage is still required for inspection. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
