---
tags: [api, dto, step-types]
---

# step-types response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `Cardinality`

Used by: `GET /api/v1/step-types/{ref_id}`, `POST /api/v1/step-types/search`, `POST /api/v1/step-types/{ref_id}/publish`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ExecutionMode`

Used by: `GET /api/v1/step-types/{ref_id}`, `POST /api/v1/step-types/search`, `POST /api/v1/step-types/{ref_id}/publish`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_SelectOption_str___`

Used by: `POST /api/v1/step-types/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_SelectOption_str__` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_StepTypeVersionDTO__`

Used by: `POST /api/v1/step-types/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_StepTypeVersionDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_SelectOption_str__`

Used by: `POST /api/v1/step-types/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SelectOption_str_]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_StepTypeVersionDTO_`

Used by: `POST /api/v1/step-types/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[StepTypeVersionDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PortDTO`

Used by: `GET /api/v1/step-types/{ref_id}`, `POST /api/v1/step-types/search`, `POST /api/v1/step-types/{ref_id}/publish`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `port_key` | `string` | Yes | — |
| `direction` | `PortDirection` | Yes | — |
| `value_schema` | `object` | Yes | — |
| `required` | `boolean` | Yes | — |
| `nullable` | `boolean` | Yes | — |
| `cardinality` | `Cardinality` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PortDirection`

Used by: `GET /api/v1/step-types/{ref_id}`, `POST /api/v1/step-types/search`, `POST /api/v1/step-types/{ref_id}/publish`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SelectOption_str_`

Used by: `POST /api/v1/step-types/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `StepTypeVersionDTO`

Used by: `GET /api/v1/step-types/{ref_id}`, `POST /api/v1/step-types/search`, `POST /api/v1/step-types/{ref_id}/publish`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `code` | `string` | Yes | — |
| `name` | `string` | Yes | — |
| `handler_key` | `string` | Yes | — |
| `handler_version` | `string` | Yes | — |
| `execution_mode` | `ExecutionMode` | Yes | — |
| `config_schema` | `object` | Yes | — |
| `ports` | `array[PortDTO]` | Yes | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `number` | `integer` | Yes | — |
| `status` | `string` | No | Lifecycle state; consult the owning resource guide. Default: `PUBLISHED`. |
| `is_available` | `boolean` | No |  Default: `True`. |
| `category` | `string | null` | No | — |
| `name_key` | `string | null` | No | — |
| `help_key` | `string | null` | No | — |
| `help_text` | `string | null` | No | — |
| `outcomes` | `array[string]` | No | — |
| `examples` | `array[object]` | No | — |
| `required_capabilities` | `array[string]` | No | — |
| `has_inputs` | `boolean` | No |  Default: `False`. |
| `has_outputs` | `boolean` | No |  Default: `False`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_StepTypeVersionDTO_`

Used by: `GET /api/v1/step-types/{ref_id}`, `POST /api/v1/step-types/{ref_id}/publish`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `StepTypeVersionDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
