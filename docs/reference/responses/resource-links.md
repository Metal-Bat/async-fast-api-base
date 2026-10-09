---
tags: [api, dto, resource-links]
---

# resource-links response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `ResourceKind`

Used by: `POST /api/v1/resource-links`, `POST /api/v1/resource-links/resolve`, `POST /api/v1/resource-links/selected`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ResourceLink`

Used by: `POST /api/v1/resource-links`, `POST /api/v1/resource-links/resolve`

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

### `ResourceSummary`

Used by: `POST /api/v1/resource-links/selected`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `ResourceKind` | Yes | — |
| `ref_id` | `string` | Yes | Fresh version-bearing reference; replace cached mutation refs. |
| `label` | `string` | Yes | Safe current display name from the owning resource service. |
| `number` | `integer | null` | No | Exact version number, when applicable. |
| `available` | `boolean` | Yes | Current selection eligibility; does not grant execution authority. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ResourceLink_`

Used by: `POST /api/v1/resource-links`, `POST /api/v1/resource-links/resolve`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ResourceLink` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_list_ResourceSummary__`

Used by: `POST /api/v1/resource-links/selected`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `array[ResourceSummary]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
