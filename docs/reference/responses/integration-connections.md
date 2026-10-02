---
tags: [api, dto, integration-connections]
---

# integration-connections response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `AIConnectionConfig`

Used by: `GET /api/v1/integration-connections/{ref_id}`, `POST /api/v1/integration-connections`, `POST /api/v1/integration-connections/report`, `POST /api/v1/integration-connections/search`, `POST /api/v1/integration-connections/{ref_id}/revoke`, `POST /api/v1/integration-connections/{ref_id}/rotate`, `POST /api/v1/integration-connections/{ref_id}/verify`, `PUT /api/v1/integration-connections/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `endpoint_key` | `SecretIdentifier` | No |  Default: `hosted`. |
| `models` | `array[string]` | Yes | — |
| `region` | `string | null` | No | — |
| `account` | `string | null` | No | Required account identifier for Snowflake or OpenAI Codex connections. ASCII letters, digits, underscores and hyphens only; never credentials. |
| `provider_retention` | `string` | Yes | — |
| `transport_attempts` | `integer` | No |  Default: `1`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ConnectionConfig`

Used by: `GET /api/v1/integration-connections/{ref_id}`, `POST /api/v1/integration-connections`, `POST /api/v1/integration-connections/report`, `POST /api/v1/integration-connections/search`, `POST /api/v1/integration-connections/{ref_id}/revoke`, `POST /api/v1/integration-connections/{ref_id}/rotate`, `POST /api/v1/integration-connections/{ref_id}/verify`, `PUT /api/v1/integration-connections/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `endpoint_key` | `SecretIdentifier` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ConnectionDTO`

Used by: `GET /api/v1/integration-connections/{ref_id}`, `POST /api/v1/integration-connections`, `POST /api/v1/integration-connections/report`, `POST /api/v1/integration-connections/search`, `POST /api/v1/integration-connections/{ref_id}/revoke`, `POST /api/v1/integration-connections/{ref_id}/rotate`, `POST /api/v1/integration-connections/{ref_id}/verify`, `PUT /api/v1/integration-connections/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `code` | `string` | Yes | — |
| `name` | `string` | Yes | — |
| `provider` | `string` | Yes | — |
| `kind` | `string` | Yes | — |
| `non_secret_config` | `ConnectionConfig | AIConnectionConfig` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `verification_status` | `string` | Yes | — |
| `created_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `GrantReferenceDTO`

Used by: `POST /api/v1/integration-connections/{ref_id}/grants`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HistoryRecordDTO`

Used by: `POST /api/v1/integration-connections/{ref_id}/history`

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

### `PageResponse_Page_ConnectionDTO__`

Used by: `POST /api/v1/integration-connections/report`, `POST /api/v1/integration-connections/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_ConnectionDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_HistoryRecordDTO__`

Used by: `POST /api/v1/integration-connections/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_SelectOption_str___`

Used by: `POST /api/v1/integration-connections/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_SelectOption_str__` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_ConnectionDTO_`

Used by: `POST /api/v1/integration-connections/report`, `POST /api/v1/integration-connections/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[ConnectionDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/integration-connections/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_SelectOption_str__`

Used by: `POST /api/v1/integration-connections/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SelectOption_str_]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SecretIdentifier`

Used by: `GET /api/v1/integration-connections/{ref_id}`, `POST /api/v1/integration-connections`, `POST /api/v1/integration-connections/report`, `POST /api/v1/integration-connections/search`, `POST /api/v1/integration-connections/{ref_id}/revoke`, `POST /api/v1/integration-connections/{ref_id}/rotate`, `POST /api/v1/integration-connections/{ref_id}/verify`, `PUT /api/v1/integration-connections/{ref_id}`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SelectOption_str_`

Used by: `POST /api/v1/integration-connections/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ConnectionDTO_`

Used by: `GET /api/v1/integration-connections/{ref_id}`, `POST /api/v1/integration-connections`, `POST /api/v1/integration-connections/{ref_id}/revoke`, `POST /api/v1/integration-connections/{ref_id}/rotate`, `POST /api/v1/integration-connections/{ref_id}/verify`, `PUT /api/v1/integration-connections/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ConnectionDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_GrantReferenceDTO_`

Used by: `POST /api/v1/integration-connections/{ref_id}/grants`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `GrantReferenceDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/integration-connections/{ref_id}`, `DELETE /api/v1/integration-connections/{ref_id}/grants/{grant_ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
