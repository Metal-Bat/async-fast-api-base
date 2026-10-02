---
tags: [api, dto, designer]
---

# designer response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `CatalogItemDTO`

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `title` | `string` | Yes | — |
| `category` | `string` | Yes | — |
| `type_schema` | `object` | No | — |
| `metadata` | `object` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CompletionItemDTO`

Used by: `POST /api/v1/designer/completion`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `path` | `string` | Yes | — |
| `source` | `string` | Yes | — |
| `type_schema` | `object` | Yes | — |
| `nullable` | `boolean` | Yes | — |
| `cardinality` | `string` | Yes | — |
| `source_step` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `DeclaredPort`

Used by: `POST /api/v1/designer/field-inventory`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `scope` | `string` | No |  Default: `workflow`. |
| `step` | `string` | Yes | — |
| `direction` | `string` | Yes | — |
| `port` | `string` | Yes | — |
| `type_schema` | `object` | Yes | — |
| `source_kind` | `string | null` | No | — |
| `source` | `string | null` | No | User input, process context, constant, or earlier step output; no profile source is inferred from a label. |
| `source_path` | `string | null` | No | — |
| `location` | `string` | Yes | — |
| `required` | `boolean | null` | No | — |
| `nullable` | `boolean | null` | No | — |
| `cardinality` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `DefinitionPin`

Used by: `POST /api/v1/designer/field-inventory`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | — |
| `collection_point` | `string` | Yes | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `checksum` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FieldEvidence`

Used by: `POST /api/v1/designer/field-inventory`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `reason` | `string` | Yes | Stable technical consumer reason code; see the field inventory guide. |
| `location` | `string` | Yes | Exact source definition pointer, prefixed by collection point for form documents. |
| `target` | `string | null` | No | — |
| `condition` | `string | null` | No | — |
| `explanation` | `string` | Yes | — |
| `via` | `array[string]` | No | Intermediate calculated field identities in a transitive dependency chain. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FieldInventoryResult`

Used by: `POST /api/v1/designer/field-inventory`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_version_ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `graph_checksum` | `string | null` | No | — |
| `form_snapshots` | `object` | No | — |
| `complete` | `boolean` | Yes | False when opaque, inaccessible, missing, dynamic or bounded dependencies prevent an unused claim. |
| `diagnostics` | `array[string]` | No | Bounded coverage diagnostics; review these before acting on suggestions. |
| `summary` | `FieldInventorySummary` | Yes | — |
| `fields` | `array[FieldInventoryRow]` | Yes | — |
| `declared_ports` | `array[DeclaredPort]` | No | Typed step and subprocess interface ports, including unbound declarations. |
| `resolved_pins` | `array[DefinitionPin]` | No | Accessible exact component, data-type and child workflow versions analyzed. |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `25`. |
| `total` | `integer` | No |  Default: `0`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FieldInventoryRow`

Used by: `POST /api/v1/designer/field-inventory`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `identity` | `string` | Yes | Form version, collection point and JSON Schema scope; duplicate labels do not merge identities. |
| `form_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `collection_point` | `string` | Yes | — |
| `component_instance` | `string | null` | No | — |
| `collection_scope` | `string | null` | No | — |
| `path` | `string` | Yes | — |
| `label` | `string` | Yes | — |
| `type` | `string` | Yes | — |
| `source` | `string` | Yes | Declared origin such as USER_INPUT, DEFAULT, COMPUTATION, HOST_NAVIGATION or EARLIER_TASK_OUTPUT. |
| `author_description` | `string | null` | No | — |
| `business_rationale` | `string | null` | No | — |
| `actor_targets` | `array[string]` | No | — |
| `first_use` | `string | null` | No | — |
| `required` | `boolean` | Yes | — |
| `user_entry` | `boolean` | No | Whether this collection point permits a user entry; read-only review does not count. Default: `False`. |
| `classification` | `string` | Yes | Conservative requiredness/use category for the analyzed definition set. |
| `component_scopes` | `array[string]` | No | — |
| `occurrences` | `integer` | No |  Default: `0`. |
| `dependencies` | `array[FieldEvidence]` | No | Direct and transitive uses, each with reason, location and localized explanation. |
| `suggestions` | `array[FieldSuggestion]` | No | Evidence-backed prompts for human review; never proof a field can be deleted. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FieldInventorySummary`

Used by: `POST /api/v1/designer/field-inventory`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `field_definitions` | `integer` | Yes | Field definitions across collection points; not runtime collection row count. |
| `unique_field_definitions` | `integer` | Yes | Distinct form-version/schema-scope pairs across collection points. |
| `user_entry_occurrences` | `integer` | Yes | — |
| `user_entered` | `integer` | Yes | — |
| `repeated_collection` | `integer` | Yes | — |
| `automatic_sources` | `integer` | Yes | — |
| `conditional_only` | `integer` | Yes | — |
| `review_candidates` | `integer` | Yes | — |
| `possible_user_inputs` | `integer` | Yes | Editable collection-point definitions over all analyzed branches; not a universal minimum. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FieldSuggestion`

Used by: `POST /api/v1/designer/field-inventory`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `code` | `string` | Yes | Stable review-candidate code, not an automatic removal instruction. |
| `explanation` | `string` | Yes | — |
| `caveat` | `string` | Yes | — |
| `impacted_locations` | `array[string]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_CatalogItemDTO__`

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_CatalogItemDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_CompletionItemDTO__`

Used by: `POST /api/v1/designer/completion`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_CompletionItemDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_SelectOption_str___`

Used by: `POST /api/v1/designer/selectors/{kind}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_SelectOption_str__` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_CatalogItemDTO_`

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[CatalogItemDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_CompletionItemDTO_`

Used by: `POST /api/v1/designer/completion`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[CompletionItemDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_SelectOption_str__`

Used by: `POST /api/v1/designer/selectors/{kind}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SelectOption_str_]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SelectOption_str_`

Used by: `POST /api/v1/designer/selectors/{kind}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_FieldInventoryResult_`

Used by: `POST /api/v1/designer/field-inventory`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `FieldInventoryResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
