---
tags: [api, dto, favorites]
---

# favorites response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `FavoriteDTO`

Used by: `GET /api/v1/me/favorites/{ref_id}`, `POST /api/v1/me/favorites`, `POST /api/v1/me/favorites/report`, `POST /api/v1/me/favorites/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `target` | `ResourceLink` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_FavoriteDTO__`

Used by: `POST /api/v1/me/favorites/report`, `POST /api/v1/me/favorites/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_FavoriteDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_PersonalHistoryDTO__`

Used by: `POST /api/v1/me/favorites/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_PersonalHistoryDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_FavoriteDTO_`

Used by: `POST /api/v1/me/favorites/report`, `POST /api/v1/me/favorites/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[FavoriteDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_PersonalHistoryDTO_`

Used by: `POST /api/v1/me/favorites/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[PersonalHistoryDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PersonalHistoryDTO`

Used by: `POST /api/v1/me/favorites/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `changed_at` | `string` | Yes | — |
| `operation` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ResourceKind`

Used by: `GET /api/v1/me/favorites/{ref_id}`, `POST /api/v1/me/favorites`, `POST /api/v1/me/favorites/report`, `POST /api/v1/me/favorites/search`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ResourceLink`

Used by: `GET /api/v1/me/favorites/{ref_id}`, `POST /api/v1/me/favorites`, `POST /api/v1/me/favorites/report`, `POST /api/v1/me/favorites/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `ResourceKind` | Yes | — |
| `ref_id` | `string` | Yes | Fresh version-bearing reference; replace cached mutation refs. |
| `label` | `string` | Yes | Safe current display name from the owning resource service. |
| `number` | `integer | null` | No | Exact version number, when applicable. |
| `available` | `boolean` | Yes | Current selection eligibility; does not grant execution authority. |
| `locator` | `string` | Yes | Stable encrypted identity; invalid after signing-key replacement. |
| `route_key` | `ResourceKind` | Yes | Allowlisted frontend route key; no arbitrary navigation URL. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_FavoriteDTO_`

Used by: `GET /api/v1/me/favorites/{ref_id}`, `POST /api/v1/me/favorites`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `FavoriteDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/me/favorites/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
