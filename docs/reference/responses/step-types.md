---
tags: [api, dto, step-types]
---

# step-types response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `BusinessOperationDTO`

Used by: `GET /api/v1/step-types/operations`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `operation_key` | `string` | Yes | Exact code-owned operation identifier and version; no arbitrary HTTP scripting. |
| `handler_key` | `string` | Yes | Required deployed step handler key. |
| `handler_version` | `string` | Yes | Required exact deployed handler version. |
| `execution_scopes` | `array[string]` | Yes | Allowed execution contexts; sandbox cancellation is compensation-only. |
| `allowed_providers` | `array[string]` | Yes | Compatible registered connection providers. |
| `connection_kind` | `string` | No | Required connection kind; AI and notification connections are incompatible. Default: `SERVICE`. |
| `execution_principal` | `string` | No | Pinned workflow publisher; protected sandbox effects require an active ordinary publisher. Default: `publisher`. |
| `authentication` | `string` | No | Credential mode; secret values and references remain private. Default: `bearer_secret`. |
| `endpoint_source` | `string` | No | Endpoint resolved by an administrator-owned key, never an authored URL. Default: `admin_owned`. |
| `approval_policy` | `string | null` | Yes | Versioned required human approval policy for create, otherwise null; tool approval is distinct. |
| `has_business_effect` | `boolean` | Yes | Whether execution changes sandbox business state; metadata inspection has no effect. |
| `timeout_seconds` | `integer` | No | Total network deadline in seconds; a timeout does not prove provider rollback. Default: `10`. |
| `retry_policy` | `string` | Yes | Diagnostic retries or lookup-only recovery after uncertain business dispatch. |
| `reconciliation` | `string | null` | Yes | Supported operation-specific receipt lookup, otherwise null. |
| `compensation` | `string | null` | No | Supported explicit reversal family; null means no registered automated reversal. |
| `input_schema` | `object` | Yes | Code-owned JSON Schema, not authored HTTP configuration. |
| `output_schema` | `object` | Yes | Code-owned JSON Schema for the bounded result port. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

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

### `SuccessResponse_list_BusinessOperationDTO__`

Used by: `GET /api/v1/step-types/operations`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `array[BusinessOperationDTO]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
