---
tags: [api, dto, workflow-versions]
---

# workflow-versions response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `GraphBinding`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `step` | `string` | Yes | — |
| `target_port` | `string` | Yes | — |
| `target_schema` | `object` | Yes | — |
| `ordinal` | `integer` | No |  Default: `0`. |
| `source_kind` | `string` | Yes | — |
| `source_path` | `string | null` | No | — |
| `source_step` | `string | null` | No | — |
| `source_port` | `string | null` | No | — |
| `source_schema` | `object | null` | No | — |
| `constant_value` | `object` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `GraphFlow`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

Optional advanced control-flow policy; absent means legacy single-path behavior.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `split` | `string | null` | No | — |
| `join` | `string | null` | No | — |
| `cancelled_branches` | `string` | No |  Default: `ARRIVE`. |
| `max_visits` | `integer | null` | No | — |
| `retry_limit` | `integer` | No |  Default: `3`. |
| `compensation_step` | `string | null` | No | — |
| `compensation_only` | `boolean` | No |  Default: `False`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `GraphIssue`

Used by: `POST /api/v1/workflow-versions/{ref_id}/default-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `code` | `string` | Yes | — |
| `line` | `integer | null` | No | — |
| `column` | `integer | null` | No | — |
| `expected_schema` | `object | null` | No | — |
| `actual_schema` | `object | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `GraphSnapshot`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `interface` | `SubprocessInterface | null` | No | Reusable published workflow interface; null preserves ordinary workflow behavior. |
| `steps` | `array[GraphStep]` | No | — |
| `bindings` | `array[GraphBinding]` | No | — |
| `targets` | `array[GraphTarget]` | No | — |
| `transitions` | `array[GraphTransition]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `GraphStep`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `type_code` | `string` | Yes | — |
| `type_version_ref` | `string | null` | No | — |
| `config` | `object` | No | — |
| `flow` | `GraphFlow` | No | — |
| `form_ref` | `string | null` | No | — |
| `field_policy` | `object | null` | No | — |
| `task_contract` | `HumanTaskContract | null` | No | — |
| `subprocess` | `SubprocessCall | null` | No | Pinned child call on a SUBPROCESS step. Execution uses the exact published version and isolated mapped inputs. |
| `default_priority` | `integer | null` | No | — |
| `timeout_seconds` | `integer | null` | No | — |
| `display_order` | `integer` | No |  Default: `0`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `GraphTarget`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `step` | `string` | Yes | — |
| `user_ref` | `string | null` | No | — |
| `work_group_ref` | `string | null` | No | — |
| `condition` | `string | null` | No | — |
| `priority` | `integer` | No |  Default: `0`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `GraphTransition`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `source` | `string` | Yes | — |
| `target` | `string` | Yes | — |
| `outcome` | `string` | Yes | — |
| `condition` | `string | null` | No | Boolean expression over declared request/process/reachable outputs and saved origin client. Use version_in_range(client.release, literal_minimum, literal_maximum_exclusive) for releases. Null is unconditional; errors stop progression. |
| `is_default` | `boolean` | No | Final else for this source/outcome, used only when no non-default matches. At most one; client-aware groups require an unconditional default below all branch priorities. Default: `False`. |
| `priority` | `integer` | No | Descending if/elif order within a source/outcome. Duplicate priorities are invalid. First matching non-default wins outside explicit parallel split policy. Default: `0`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HistoryRecordDTO`

Used by: `POST /api/v1/workflow-versions/{ref_id}/history`, `POST /api/v1/workflow-versions/{ref_id}/workspace/history`

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

### `HumanTaskContract`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `default_view` | `string` | Yes | — |
| `correction_entry` | `boolean` | No |  Default: `False`. |
| `inherit_previous` | `boolean` | No |  Default: `False`. |
| `views` | `array[TaskView]` | Yes | — |
| `actions` | `array[TaskAction]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `LocalizedTaskText`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `en` | `string` | Yes | — |
| `fa` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_HistoryRecordDTO__`

Used by: `POST /api/v1/workflow-versions/{ref_id}/history`, `POST /api/v1/workflow-versions/{ref_id}/workspace/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_WorkflowVersionDTO__`

Used by: `POST /api/v1/workflow-versions/report`, `POST /api/v1/workflow-versions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_WorkflowVersionDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/workflow-versions/{ref_id}/history`, `POST /api/v1/workflow-versions/{ref_id}/workspace/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_WorkflowVersionDTO_`

Used by: `POST /api/v1/workflow-versions/report`, `POST /api/v1/workflow-versions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[WorkflowVersionDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RestorePlan`

Used by: `POST /api/v1/workflow-versions/{ref_id}/default-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `template_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `template_checksum` | `string` | Yes | — |
| `mode` | `string` | Yes | — |
| `dependencies` | `object` | Yes | — |
| `changed_step_keys` | `array[string]` | Yes | — |
| `changed_paths` | `array[string]` | No | Safe changed top-level definition paths; no embedded config or private values. |
| `blockers` | `array[GraphIssue]` | Yes | — |
| `expires_in_seconds` | `integer` | No |  Default: `600`. |
| `plan_token` | `string | null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RestoreResult`

Used by: `POST /api/v1/workflow-versions/{ref_id}/default-apply`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `workspace_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `replayed` | `boolean` | No |  Default: `False`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubprocessCall`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_version_ref` | `string` | Yes | Exact published child workflow version ref_id. Existing pins survive retirement. |
| `inputs` | `array[SubprocessInputMapping]` | No | Explicit source mapping for required child inputs and assignment references. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubprocessInputMapping`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | `string` | Yes | — |
| `source_kind` | `string` | Yes | — |
| `source_schema` | `object` | Yes | Source JSON Schema; publication checks compatibility with the child input. |
| `source_path` | `string | null` | No | — |
| `source_step` | `string | null` | No | — |
| `source_port` | `string | null` | No | — |
| `constant_value` | `object` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubprocessInterface`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `inputs` | `array[SubprocessPort]` | No | Named values copied into the child; parent context is not implicit. |
| `outputs` | `array[SubprocessOutput]` | No | Named values returned from child step output ports. |
| `category` | `string` | No |  Default: `general`. |
| `help_messages` | `object` | No | — |
| `sample_inputs` | `object` | No | — |
| `required_capabilities` | `array[string]` | No | — |
| `outcomes` | `object` | Yes | Business outcome name to child FINISH step key. The parent also handles failure. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubprocessOutput`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | `string` | Yes | — |
| `value_schema` | `object` | Yes | Declared output schema matching the named child step output port. |
| `source_step` | `string` | Yes | Child graph step producing this output. |
| `source_port` | `string` | Yes | Output port on source_step. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubprocessPort`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | `string` | Yes | — |
| `value_schema` | `object` | Yes | JSON Schema Draft 2020-12 type expected in the isolated child context. |
| `required` | `boolean` | No | A call must map this input when true. Default: `True`. |
| `assignment` | `string | null` | No | Actor or group assignment reference carried as a string. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_GraphSnapshot_`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `GraphSnapshot` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/workflow-versions/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_RestorePlan_`

Used by: `POST /api/v1/workflow-versions/{ref_id}/default-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `RestorePlan` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_RestoreResult_`

Used by: `POST /api/v1/workflow-versions/{ref_id}/default-apply`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `RestoreResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_WorkflowVersionDTO_`

Used by: `GET /api/v1/workflow-versions/{ref_id}`, `POST /api/v1/workflow-versions`, `POST /api/v1/workflow-versions/{ref_id}/publish`, `POST /api/v1/workflow-versions/{ref_id}/retire`, `POST /api/v1/workflow-versions/{ref_id}/workspace/promote`, `PUT /api/v1/workflow-versions/{ref_id}`, `PUT /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `WorkflowVersionDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_WorkflowWorkspaceDTO_`

Used by: `GET /api/v1/workflow-versions/{ref_id}/workspace`, `POST /api/v1/workflow-versions/{ref_id}/layout-reset`, `PUT /api/v1/workflow-versions/{ref_id}/workspace`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `WorkflowWorkspaceDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TaskAction`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `kind` | `string` | Yes | — |
| `outcome_key` | `string` | Yes | — |
| `title` | `LocalizedTaskText` | Yes | — |
| `confirmation` | `LocalizedTaskText | null` | No | — |
| `required_scopes` | `array[string]` | No | — |
| `require_comment` | `boolean` | No |  Default: `False`. |
| `validation` | `string` | No |  Default: `complete`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TaskView`

Used by: `GET /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `purpose` | `string` | Yes | — |
| `title` | `LocalizedTaskText` | Yes | — |
| `scopes` | `array[string]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkflowVersionDTO`

Used by: `GET /api/v1/workflow-versions/{ref_id}`, `POST /api/v1/workflow-versions`, `POST /api/v1/workflow-versions/report`, `POST /api/v1/workflow-versions/search`, `POST /api/v1/workflow-versions/{ref_id}/publish`, `POST /api/v1/workflow-versions/{ref_id}/retire`, `POST /api/v1/workflow-versions/{ref_id}/workspace/promote`, `PUT /api/v1/workflow-versions/{ref_id}`, `PUT /api/v1/workflow-versions/{ref_id}/graph`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `template_source` | `object | null` | No | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `workflow_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `number` | `integer` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `default_priority` | `integer` | Yes | — |
| `graph_checksum` | `string | null` | Yes | — |
| `published_at` | `string | null` | Yes | — |
| `published_by_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkflowWorkspaceDTO`

Used by: `GET /api/v1/workflow-versions/{ref_id}/workspace`, `POST /api/v1/workflow-versions/{ref_id}/layout-reset`, `PUT /api/v1/workflow-versions/{ref_id}/workspace`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `workspace_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |
| `document` | `WorkspaceDocument` | Yes | — |
| `promoted_graph_checksum` | `string | null` | No | Checksum of the last explicitly promoted graph; layout-only saves do not change execution pins. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkspaceDocument`

Used by: `GET /api/v1/workflow-versions/{ref_id}/workspace`, `POST /api/v1/workflow-versions/{ref_id}/layout-reset`, `PUT /api/v1/workflow-versions/{ref_id}/workspace`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `dialect` | `string` | No |  Default: `bpms.workspace/1`. |
| `graph` | `object` | No | Incomplete authoring JSON, at most 256 KiB and depth 32. It is never executed; promotion validates GraphSnapshot and all dependencies. |
| `positions` | `object` | No | Positions keyed by stable authored step key, never database row IDs. |
| `viewport` | `WorkspaceViewport` | No | — |
| `collapsed` | `array[string]` | No | — |
| `routing` | `object` | No | Optional edge waypoints keyed by authored connection identity; at most 64 points each. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkspacePoint`

Used by: `GET /api/v1/workflow-versions/{ref_id}/workspace`, `POST /api/v1/workflow-versions/{ref_id}/layout-reset`, `PUT /api/v1/workflow-versions/{ref_id}/workspace`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `x` | `number` | No |  Default: `0`. |
| `y` | `number` | No |  Default: `0`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkspaceViewport`

Used by: `GET /api/v1/workflow-versions/{ref_id}/workspace`, `POST /api/v1/workflow-versions/{ref_id}/layout-reset`, `PUT /api/v1/workflow-versions/{ref_id}/workspace`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `x` | `number` | No |  Default: `0`. |
| `y` | `number` | No |  Default: `0`. |
| `zoom` | `number` | No |  Default: `1`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
