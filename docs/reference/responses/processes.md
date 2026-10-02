---
tags: [api, dto, processes]
---

# processes response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `Page_ScheduledActionDTO_`

Used by: `POST /api/v1/processes/{ref_id}/scheduled-actions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[ScheduledActionDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_TimelineEventDTO_`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[TimelineEventDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ProcessDTO`

Used by: `GET /api/v1/processes/{ref_id}`, `POST /api/v1/processes/{ref_id}/cancel`, `POST /api/v1/processes/{ref_id}/compensate`, `POST /api/v1/processes/{ref_id}/pause`, `POST /api/v1/processes/{ref_id}/recover`, `POST /api/v1/processes/{ref_id}/resume`, `POST /api/v1/processes/{ref_id}/retry`, `POST /api/v1/processes/{ref_id}/timeout`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `business_request_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `workflow_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `current_positions` | `array[ProcessPositionDTO]` | Yes | — |
| `last_error_code` | `string | null` | Yes | — |
| `started_at` | `string` | Yes | — |
| `ended_at` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ProcessPositionDTO`

Used by: `GET /api/v1/processes/{ref_id}`, `POST /api/v1/processes/{ref_id}/cancel`, `POST /api/v1/processes/{ref_id}/compensate`, `POST /api/v1/processes/{ref_id}/pause`, `POST /api/v1/processes/{ref_id}/recover`, `POST /api/v1/processes/{ref_id}/resume`, `POST /api/v1/processes/{ref_id}/retry`, `POST /api/v1/processes/{ref_id}/timeout`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `step_key` | `string` | Yes | — |
| `token_status` | `string` | Yes | — |
| `execution_status` | `string | null` | Yes | — |
| `wait_kind` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ProcessTimelineDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `process_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `business_request_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `coverage_started_at` | `string | null` | Yes | — |
| `current_positions` | `array[TimelinePositionDTO]` | Yes | — |
| `children` | `array[TimelineChildDTO]` | No | Direct child call history with pinned versions and nested active positions. |
| `steps` | `array[TimelineStepDTO]` | Yes | — |
| `transitions` | `array[TimelineTransitionDTO]` | Yes | — |
| `events` | `Page_TimelineEventDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ScheduledActionDTO`

Used by: `POST /api/v1/processes/{ref_id}/scheduled-actions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `kind` | `string` | Yes | — |
| `due_at` | `string` | Yes | — |
| `attempts` | `integer` | Yes | — |
| `max_attempts` | `integer` | Yes | — |
| `last_error_code` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_Page_ScheduledActionDTO__`

Used by: `POST /api/v1/processes/{ref_id}/scheduled-actions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `Page_ScheduledActionDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ProcessDTO_`

Used by: `GET /api/v1/processes/{ref_id}`, `POST /api/v1/processes/{ref_id}/cancel`, `POST /api/v1/processes/{ref_id}/compensate`, `POST /api/v1/processes/{ref_id}/pause`, `POST /api/v1/processes/{ref_id}/recover`, `POST /api/v1/processes/{ref_id}/resume`, `POST /api/v1/processes/{ref_id}/retry`, `POST /api/v1/processes/{ref_id}/timeout`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ProcessDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ProcessTimelineDTO_`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ProcessTimelineDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelineAttemptDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `number` | `integer` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `error_code` | `string | null` | Yes | — |
| `started_at` | `string` | Yes | — |
| `ended_at` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelineCandidateDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `principal_type` | `string` | Yes | — |
| `principal_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `can_claim` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelineChildDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

Safe child-process summary in the request's authorized timeline.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `process_ref_id` | `string` | Yes | Opaque child process reference for detailed inspection. |
| `parent_execution_ref_id` | `string` | Yes | Exact parent call visit that started this child. |
| `workflow_version_ref_id` | `string` | Yes | Pinned published child workflow version. |
| `status` | `string` | Yes | Current child process status. |
| `current_positions` | `array[TimelinePositionDTO]` | Yes | Live child token positions, including human and timer waits. |
| `children` | `array[TimelineChildDTO]` | No | Nested child summaries without copied input or output data. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelineEventDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `sequence` | `integer` | Yes | — |
| `event_type` | `string` | Yes | — |
| `step_execution_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `work_item_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `actor_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `public_payload` | `object` | Yes | — |
| `trace_id` | `string | null` | Yes | — |
| `request_id` | `string | null` | Yes | — |
| `occurred_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelineExecutionDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `visit_number` | `integer` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `wait_kind` | `string | null` | Yes | — |
| `attempts` | `array[TimelineAttemptDTO]` | Yes | — |
| `work_item` | `TimelineWorkItemDTO | null` | Yes | — |
| `form_submission_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `last_error_code` | `string | null` | Yes | — |
| `started_at` | `string | null` | Yes | — |
| `ended_at` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelinePositionDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `token_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `step_key` | `string` | Yes | — |
| `execution_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `wait_kind` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelineStepDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `step_key` | `string` | Yes | — |
| `display_order` | `integer` | Yes | — |
| `path_status` | `string` | Yes | — |
| `executions` | `array[TimelineExecutionDTO]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelineTransitionDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `source_step_key` | `string` | Yes | — |
| `target_step_key` | `string` | Yes | — |
| `outcome` | `string` | Yes | — |
| `taken_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimelineWorkItemDTO`

Used by: `POST /api/v1/processes/{ref_id}/timeline`, `POST /api/v1/processes/{ref_id}/timeline/report`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `claimant_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `candidates` | `array[TimelineCandidateDTO]` | Yes | — |
| `submission_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `outcome_key` | `string | null` | Yes | — |
| `due_at` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
