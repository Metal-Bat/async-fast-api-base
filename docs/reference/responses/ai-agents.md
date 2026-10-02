---
tags: [api, dto, ai-agents]
---

# ai-agents response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `AIAgentDTO`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `code` | `string` | Yes | — |
| `number` | `integer` | Yes | — |
| `name` | `string` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `spec` | `AIAgentDraftSpec-Output | AIAgentPublishedSpec` | Yes | — |
| `checksum` | `string | null` | Yes | — |
| `published_at` | `string | null` | Yes | — |
| `created_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIAgentDraftSpec-Output`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

Author-controlled values. All references are resolved at publication.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `connection_ref` | `string` | Yes | — |
| `provider_key` | `string` | Yes | — |
| `model_id` | `string` | Yes | — |
| `prompt_version` | `string` | Yes | — |
| `instructions` | `string` | Yes | — |
| `decision` | `AIDecisionContract | AIInputDecision` | Yes | — |
| `data_policy` | `AIPermittedData` | Yes | — |
| `field_classifications` | `object` | Yes | — |
| `user_limits` | `AITaskLimits-Output` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIAgentPublishedSpec`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `connection_ref` | `string` | Yes | — |
| `provider_key` | `string` | Yes | — |
| `model_id` | `string` | Yes | — |
| `prompt_version` | `string` | Yes | — |
| `instructions` | `string` | Yes | — |
| `decision` | `AIDecisionContract | AIInputDecision` | Yes | — |
| `data_policy` | `AIPermittedData` | Yes | — |
| `field_classifications` | `object` | Yes | — |
| `user_limits` | `AITaskLimits-Output` | Yes | — |
| `tool_versions` | `object` | No | Trusted tool key to immutable deployed version, resolved at publication; empty for tool-free agents. |
| `effective_limits` | `AITaskLimits-Output` | Yes | — |
| `price` | `AIPrice` | Yes | — |
| `transport_attempts` | `integer` | No |  Default: `1`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIBudgetStatus`

Used by: `GET /api/v1/ai-agents/processes/{process_ref}/executions/{execution_ref}/budget`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `effective_limits` | `AITaskLimits-Output` | Yes | — |
| `used` | `BudgetAmounts` | Yes | — |
| `reserved` | `BudgetAmounts` | Yes | — |
| `remaining` | `BudgetCapacity` | Yes | — |
| `currency` | `string` | Yes | — |
| `price_version` | `string` | Yes | — |
| `unknown_usage` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIChoice`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `labels` | `object` | Yes | — |
| `description` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIDecisionContract`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `question` | `string` | Yes | — |
| `options` | `array[AIChoice]` | Yes | — |
| `review_below` | `number` | No |  Default: `0.8`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIInputDecision`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `question` | `string` | Yes | — |
| `options_input_key` | `string` | Yes | — |
| `review_below` | `number` | No |  Default: `0.8`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIModelMetadataDTO`

Used by: `GET /api/v1/ai-agents/connections/{connection_ref}/models/{model_id}/metadata`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `connection_ref` | `string` | Yes | — |
| `provider` | `string` | Yes | — |
| `model_id` | `string` | Yes | — |
| `source` | `string` | Yes | — |
| `can_execute` | `boolean` | Yes | — |
| `supports_structured_output` | `boolean` | Yes | — |
| `supports_tools` | `boolean` | Yes | — |
| `region` | `string | null` | Yes | — |
| `provider_retention` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIModelSuggestionDTO`

Used by: `POST /api/v1/ai-agents/models/suggestions`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `connection_ref` | `string | null` | Yes | — |
| `model_id` | `string` | Yes | — |
| `source` | `string` | Yes | — |
| `can_execute` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIPermittedData`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `allowed_fields` | `array[string]` | Yes | — |
| `allowed_classifications` | `array[string]` | Yes | — |
| `redacted_fields` | `array[string]` | No | — |
| `allowed_tools` | `array[string]` | No | — |
| `allowed_retrieval_sources` | `array[string]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIPrice`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `version` | `string` | Yes | — |
| `input_per_million_usd` | `string` | Yes | — |
| `output_per_million_usd` | `string` | Yes | — |
| `fixed_per_request_usd` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIProviderMetadataDTO`

Used by: `GET /api/v1/ai-agents/providers/{provider_key}/metadata`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `extra` | `string` | Yes | — |
| `available` | `boolean` | Yes | — |
| `unavailable_reason` | `string | null` | Yes | — |
| `credential_mode` | `string` | Yes | — |
| `needs_endpoint` | `boolean` | Yes | — |
| `supports_custom_endpoint` | `boolean` | Yes | — |
| `supports_tools` | `boolean` | Yes | — |
| `supports_structured_output` | `boolean` | Yes | — |
| `strict_spend_supported` | `boolean` | Yes | — |
| `governed_execution` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AITaskLimits-Output`

Used by: `GET /api/v1/ai-agents/processes/{process_ref}/executions/{execution_ref}/budget`, `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `requests` | `integer` | Yes | — |
| `tool_calls` | `integer` | Yes | — |
| `input_tokens` | `integer` | Yes | — |
| `output_tokens` | `integer` | Yes | — |
| `total_tokens` | `integer` | Yes | — |
| `elapsed_seconds` | `integer` | Yes | — |
| `spend_usd` | `string` | Yes | — |
| `strict_spend` | `boolean` | No |  Default: `True`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `AIToolApprovalDTO`

Used by: `GET /api/v1/ai-agents/work-items/{work_item_ref}/tool-approval`, `POST /api/v1/ai-agents/work-items/{work_item_ref}/tool-approval`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `work_item_ref` | `string` | Yes | Current version-bearing work-item reference; claim it through the normal work-item API before inspecting or deciding the tool call. |
| `status` | `string` | Yes | Durable approval state. CONSUMED fences dispatch; it does not itself prove the model completed. DENIED, EXPIRED and CANCELLED cannot resume. |
| `tool_key` | `string` | Yes | Allowlisted trusted tool selected by the model; never a Python import or arbitrary SQL. |
| `tool_version` | `string` | Yes | Immutable deployed tool version pinned when the agent was published. |
| `arguments` | `object | null` | Yes | Exact validated named tool arguments, available only to the eligible claimant before expiry/consumption. For lookup_saved_report: report_ref is an owned saved report reference and limit is an integer from 1 to 10. Null after payload deletion; contains no message history. |
| `expires_at` | `string` | Yes | UTC deadline derived from the logical task elapsed-time budget, including human approval time. |
| `decided_at` | `string | null` | Yes | UTC decision time, or null before a claimant decision. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `BudgetAmounts`

Used by: `GET /api/v1/ai-agents/processes/{process_ref}/executions/{execution_ref}/budget`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `requests` | `integer` | No |  Default: `0`. |
| `tool_calls` | `integer` | No |  Default: `0`. |
| `input_tokens` | `integer` | No |  Default: `0`. |
| `output_tokens` | `integer` | No |  Default: `0`. |
| `total_tokens` | `integer` | No |  Default: `0`. |
| `spend_usd` | `string` | No |  Default: `0`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `BudgetCapacity`

Used by: `GET /api/v1/ai-agents/processes/{process_ref}/executions/{execution_ref}/budget`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `requests` | `integer` | Yes | — |
| `tool_calls` | `integer` | Yes | — |
| `input_tokens` | `integer` | Yes | — |
| `output_tokens` | `integer` | Yes | — |
| `total_tokens` | `integer` | Yes | — |
| `spend_usd` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HistoryRecordDTO`

Used by: `POST /api/v1/ai-agents/{ref_id}/history`

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

### `PageResponse_Page_AIAgentDTO__`

Used by: `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_AIAgentDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_AIModelSuggestionDTO__`

Used by: `POST /api/v1/ai-agents/models/suggestions`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_AIModelSuggestionDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_HistoryRecordDTO__`

Used by: `POST /api/v1/ai-agents/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_SelectOption_str___`

Used by: `POST /api/v1/ai-agents/connections/select`, `POST /api/v1/ai-agents/connections/{connection_ref}/models/select`, `POST /api/v1/ai-agents/providers/select`, `POST /api/v1/ai-agents/select`, `POST /api/v1/ai-agents/{ref_id}/choices/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_SelectOption_str__` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_AIAgentDTO_`

Used by: `POST /api/v1/ai-agents/report`, `POST /api/v1/ai-agents/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[AIAgentDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_AIModelSuggestionDTO_`

Used by: `POST /api/v1/ai-agents/models/suggestions`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[AIModelSuggestionDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/ai-agents/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_SelectOption_str__`

Used by: `POST /api/v1/ai-agents/connections/select`, `POST /api/v1/ai-agents/connections/{connection_ref}/models/select`, `POST /api/v1/ai-agents/providers/select`, `POST /api/v1/ai-agents/select`, `POST /api/v1/ai-agents/{ref_id}/choices/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SelectOption_str_]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SelectOption_str_`

Used by: `POST /api/v1/ai-agents/connections/select`, `POST /api/v1/ai-agents/connections/{connection_ref}/models/select`, `POST /api/v1/ai-agents/providers/select`, `POST /api/v1/ai-agents/select`, `POST /api/v1/ai-agents/{ref_id}/choices/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_AIAgentDTO_`

Used by: `GET /api/v1/ai-agents/{ref_id}`, `POST /api/v1/ai-agents`, `POST /api/v1/ai-agents/{ref_id}/publish`, `PUT /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `AIAgentDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_AIBudgetStatus_`

Used by: `GET /api/v1/ai-agents/processes/{process_ref}/executions/{execution_ref}/budget`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `AIBudgetStatus` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_AIModelMetadataDTO_`

Used by: `GET /api/v1/ai-agents/connections/{connection_ref}/models/{model_id}/metadata`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `AIModelMetadataDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_AIProviderMetadataDTO_`

Used by: `GET /api/v1/ai-agents/providers/{provider_key}/metadata`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `AIProviderMetadataDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_AIToolApprovalDTO_`

Used by: `GET /api/v1/ai-agents/work-items/{work_item_ref}/tool-approval`, `POST /api/v1/ai-agents/work-items/{work_item_ref}/tool-approval`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `AIToolApprovalDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/ai-agents/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
