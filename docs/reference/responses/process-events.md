---
tags: [api, dto, process-events]
---

# process-events response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `EventDeliveryResultDTO`

Used by: `POST /api/v1/process-events/{event_type}/deliver`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_EventDeliveryResultDTO_`

Used by: `POST /api/v1/process-events/{event_type}/deliver`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `EventDeliveryResultDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
