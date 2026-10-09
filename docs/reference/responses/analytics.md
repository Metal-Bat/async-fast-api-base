---
tags: [api, dto, analytics]
---

# analytics response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `BusinessRequestQuery`

Used by: `POST /api/v1/analytics/query`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `filters` | `array[FilterCriteria]` | No | — |
| `sort_orders` | `array[SortOrder]` | No | — |
| `scope` | `string` | No | Visible uses current read policy; mine additionally requires requester ownership. Default: `visible`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CartableKind`

Used by: `POST /api/v1/analytics/query`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CartableQueryDTO`

Used by: `POST /api/v1/analytics/query`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `cartable` | `CartableKind` | Yes | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `time_field` | `string` | No | Timestamp used by optional half-open date bounds. Default: `created_at`. |
| `after` | `string | null` | No | Inclusive UTC instant lower bound. |
| `before` | `string | null` | No | Exclusive UTC instant upper bound. |
| `overdue_before` | `string | null` | No | Only items with a non-null deadline strictly before this instant. |
| `status` | `string | null` | No | Lifecycle state; consult the owning resource guide. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FilterCriteria`

Used by: `POST /api/v1/analytics/query`

One filter in the shared search wire format.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `field_name` | `string` | Yes | — |
| `operation` | `FilterOperation` | Yes | — |
| `value` | `object` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FilterOperation`

Used by: `POST /api/v1/analytics/query`

Filter operators exposed by the shared search contract.

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `MetricBucket`

Used by: `POST /api/v1/analytics/query`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `date` | `string` | Yes | — |
| `value` | `number | null` | Yes | — |
| `population_count` | `integer` | Yes | — |
| `sample_count` | `integer` | Yes | — |
| `unknown_count` | `integer` | Yes | — |
| `drilldown` | `MetricDrilldown` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `MetricDefinition`

Used by: `GET /api/v1/analytics/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `metric_key` | `MetricKey` | Yes | — |
| `version` | `integer` | No |  Default: `1`. |
| `unit` | `string` | Yes | — |
| `population` | `string` | Yes | — |
| `timestamp` | `string | null` | Yes | — |
| `availability` | `string` | No |  Default: `available`. |
| `reason` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `MetricDrilldown`

Used by: `POST /api/v1/analytics/query`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `route_key` | `string` | Yes | — |
| `query` | `BusinessRequestQuery | CartableQueryDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `MetricKey`

Used by: `GET /api/v1/analytics/catalog`, `POST /api/v1/analytics/query`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `MetricResult`

Used by: `POST /api/v1/analytics/query`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `metric_key` | `MetricKey` | Yes | — |
| `version` | `integer` | No |  Default: `1`. |
| `unit` | `string` | Yes | — |
| `availability` | `string` | Yes | — |
| `reason` | `string | null` | No | — |
| `generated_at` | `string` | Yes | — |
| `as_of` | `string` | Yes | — |
| `timezone` | `string` | Yes | — |
| `series` | `array[MetricSeries]` | No | — |
| `population_count` | `integer | null` | No | — |
| `sample_count` | `integer | null` | No | — |
| `unknown_count` | `integer | null` | No | — |
| `total_value` | `number | null` | No | — |
| `drilldown` | `MetricDrilldown | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `MetricSeries`

Used by: `POST /api/v1/analytics/query`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `buckets` | `array[MetricBucket]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SortOperation`

Used by: `POST /api/v1/analytics/query`

Sort direction for one field or a sequence of fields.

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SortOrder`

Used by: `POST /api/v1/analytics/query`

Sort one field or multiple fields using the same direction.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `multi_field` | `array[string]` | No | — |
| `field_name` | `string | null` | No | — |
| `operation` | `SortOperation` | No |  Default: `asc`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_MetricResult_`

Used by: `POST /api/v1/analytics/query`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `MetricResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_list_MetricDefinition__`

Used by: `GET /api/v1/analytics/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `array[MetricDefinition]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
