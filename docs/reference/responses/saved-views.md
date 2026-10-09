---
tags: [api, dto, saved-views]
---

# saved-views response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `AppliedView`

Used by: `POST /api/v1/me/saved-views/{ref_id}/apply`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `compatible` | `boolean` | Yes | — |
| `reason` | `string` | Yes | — |
| `resource_kind` | `ViewScope` | Yes | — |
| `query` | `object | null` | No | — |
| `column_keys` | `array[string]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `JsonValue`

Used by: `GET /api/v1/me/saved-views/{ref_id}`, `POST /api/v1/me/saved-views`, `POST /api/v1/me/saved-views/report`, `POST /api/v1/me/saved-views/search`, `POST /api/v1/me/saved-views/{ref_id}/apply`, `POST /api/v1/me/saved-views/{ref_id}/default`, `PUT /api/v1/me/saved-views/{ref_id}`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_PersonalHistoryDTO__`

Used by: `POST /api/v1/me/saved-views/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_PersonalHistoryDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_SavedViewDTO__`

Used by: `POST /api/v1/me/saved-views/report`, `POST /api/v1/me/saved-views/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_SavedViewDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_PersonalHistoryDTO_`

Used by: `POST /api/v1/me/saved-views/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[PersonalHistoryDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_SavedViewDTO_`

Used by: `POST /api/v1/me/saved-views/report`, `POST /api/v1/me/saved-views/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SavedViewDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PersonalHistoryDTO`

Used by: `POST /api/v1/me/saved-views/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `changed_at` | `string` | Yes | — |
| `operation` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SavedViewDTO`

Used by: `GET /api/v1/me/saved-views/{ref_id}`, `POST /api/v1/me/saved-views`, `POST /api/v1/me/saved-views/report`, `POST /api/v1/me/saved-views/search`, `POST /api/v1/me/saved-views/{ref_id}/default`, `PUT /api/v1/me/saved-views/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `name` | `string` | Yes | — |
| `resource_kind` | `ViewScope` | Yes | — |
| `schema_version` | `integer` | Yes | — |
| `query` | `object` | Yes | — |
| `column_keys` | `array[string]` | Yes | — |
| `page_size` | `integer` | Yes | — |
| `is_default` | `boolean` | Yes | — |
| `compatible` | `boolean` | Yes | — |
| `reason` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_AppliedView_`

Used by: `POST /api/v1/me/saved-views/{ref_id}/apply`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `AppliedView` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/me/saved-views/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_SavedViewDTO_`

Used by: `GET /api/v1/me/saved-views/{ref_id}`, `POST /api/v1/me/saved-views`, `POST /api/v1/me/saved-views/{ref_id}/default`, `PUT /api/v1/me/saved-views/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `SavedViewDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ViewScope`

Used by: `GET /api/v1/me/saved-views/{ref_id}`, `POST /api/v1/me/saved-views`, `POST /api/v1/me/saved-views/report`, `POST /api/v1/me/saved-views/search`, `POST /api/v1/me/saved-views/{ref_id}/apply`, `POST /api/v1/me/saved-views/{ref_id}/default`, `PUT /api/v1/me/saved-views/{ref_id}`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
