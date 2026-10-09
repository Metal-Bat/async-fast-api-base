---
tags: [api, dto, setup]
---

# setup response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `SetupCheck`

Used by: `GET /api/v1/setup/readiness`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `required` | `boolean` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `reason` | `string` | Yes | Stable localized message key, never an exception or provider response. |
| `repair_key` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SetupReport`

Used by: `GET /api/v1/setup/readiness`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | `integer` | No |  Default: `1`. |
| `scope` | `string` | No |  Default: `development_demo`. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `checked_at` | `string` | Yes | — |
| `refresh_after_seconds` | `integer` | No |  Default: `30`. |
| `checks` | `array[SetupCheck]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_SetupReport_`

Used by: `GET /api/v1/setup/readiness`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `SetupReport` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
