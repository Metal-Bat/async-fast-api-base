---
tags: [api, dto, designer]
---

# designer response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `Cardinality`

Used by: `GET /api/v1/designer/inspector-contract`, `POST /api/v1/designer/catalog`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CatalogItemDTO`

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `title` | `string` | Yes | — |
| `category` | `string` | Yes | — |
| `type_schema` | `object` | No | — |
| `metadata` | `StepCatalogMetadata | SubprocessCatalogMetadata | FieldContract | ProcessStatusMetadata | EmptyCatalogMetadata` | No | — |

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

### `ComponentKind`

Used by: `GET /api/v1/designer/inspector-contract`, `POST /api/v1/designer/catalog`

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

### `DependencyPin`

Used by: `POST /api/v1/designer/dependency-readiness`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `requested_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `resource` | `ResourceLink` | Yes | — |
| `checksum` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `DependencyReadiness`

Used by: `POST /api/v1/designer/dependency-readiness`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | `integer` | No |  Default: `1`. |
| `scope` | `string` | No |  Default: `author_publication`. |
| `workflow_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `checked_at` | `string` | Yes | — |
| `ready` | `boolean` | Yes | — |
| `graph_checksum` | `string | null` | Yes | — |
| `issues` | `array[RepairIssue]` | Yes | — |
| `pins` | `array[DependencyPin]` | Yes | — |
| `requester_eligibility` | `string` | No |  Default: `not_checked`. |
| `client_readiness` | `string` | No |  Default: `not_checked`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `EmptyCatalogMetadata`

Used by: `POST /api/v1/designer/catalog`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ExecutionMode`

Used by: `GET /api/v1/designer/inspector-contract`, `POST /api/v1/designer/catalog`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FieldContract`

Used by: `GET /api/v1/designer/inspector-contract`, `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `ComponentKind` | Yes | — |
| `version` | `integer` | No |  Default: `1`. |
| `node_kind` | `string` | Yes | — |
| `description` | `string` | Yes | — |
| `data_schema` | `object` | Yes | — |
| `options_schema` | `object` | Yes | — |
| `defaults` | `object` | Yes | — |
| `renderers` | `array[string]` | No | — |
| `client_kinds` | `array[string]` | No | — |
| `children` | `boolean` | Yes | — |
| `validation` | `array[string]` | No | — |

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

### `HandlerInspector`

Used by: `GET /api/v1/designer/inspector-contract`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `code` | `string` | Yes | — |
| `name` | `string` | Yes | — |
| `handler_key` | `string` | Yes | — |
| `handler_version` | `string` | Yes | — |
| `execution_mode` | `ExecutionMode` | Yes | — |
| `config_schema` | `object` | Yes | — |
| `ports` | `array[PortDTO]` | Yes | — |
| `contract_fingerprint` | `string` | Yes | — |
| `config_dialect` | `string` | No |  Default: `json-schema-2020-12`. |
| `bindings` | `array[InspectorBinding]` | No | — |
| `outcomes` | `array[string]` | No | — |
| `outcome_source` | `string` | Yes | — |
| `required_capabilities` | `array[string]` | No | — |
| `name_key` | `string | null` | No | — |
| `help_key` | `string | null` | No | — |
| `help_text` | `string | null` | No | — |
| `examples` | `array[object]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `InspectorBinding`

Used by: `GET /api/v1/designer/inspector-contract`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | JSON pointer within the handler configuration. |
| `selector_kind` | `string` | Yes | Existing authorized selector; selection does not grant use permission. |
| `pinned` | `boolean` | Yes | Whether the field selects an exact immutable version. |
| `secret_reference` | `boolean` | Yes | Selects a protected resource; never enter or return credentials. |
| `scope` | `string` | Yes | Owning service eligibility policy applied again at publication. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `InspectorContract`

Used by: `GET /api/v1/designer/inspector-contract`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | `integer` | No |  Default: `1`. |
| `handlers` | `array[HandlerInspector]` | Yes | — |
| `fields` | `array[FieldContract]` | Yes | — |
| `diagnostic_pointer_format` | `string` | No |  Default: `json-pointer`. |
| `preview_policy` | `string` | No |  Default: `bounded-pure-synthetic-only`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `InspectorDiagnostic`

Used by: `POST /api/v1/designer/config-validation`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `code` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `InspectorValidationResult`

Used by: `POST /api/v1/designer/config-validation`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `valid` | `boolean` | Yes | — |
| `diagnostics` | `array[InspectorDiagnostic]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `JsonValue`

Used by: `GET /api/v1/designer/inspector-contract`, `POST /api/v1/designer/catalog`

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

### `PortDTO`

Used by: `GET /api/v1/designer/inspector-contract`, `POST /api/v1/designer/catalog`

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

Used by: `GET /api/v1/designer/inspector-contract`, `POST /api/v1/designer/catalog`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ProcessStatusMetadata`

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `compatible_next_values` | `array[string]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RepairIssue`

Used by: `POST /api/v1/designer/dependency-readiness`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `code` | `string` | Yes | — |
| `node_key` | `string | null` | Yes | — |
| `repair_key` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ResourceKind`

Used by: `POST /api/v1/designer/dependency-readiness`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ResourceLink`

Used by: `POST /api/v1/designer/dependency-readiness`

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

### `SelectOption_str_`

Used by: `POST /api/v1/designer/selectors/{kind}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `StepCatalogMetadata`

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `code` | `string` | Yes | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `number` | `integer` | Yes | — |
| `handler_key` | `string` | Yes | — |
| `handler_version` | `string` | Yes | — |
| `execution_mode` | `ExecutionMode` | Yes | — |
| `ports` | `array[PortDTO]` | Yes | — |
| `runtime_available` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubprocessCatalogMetadata`

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `workflow_version_ref` | `string` | Yes | — |
| `interface` | `SubprocessInterface` | Yes | — |
| `runtime_available` | `boolean` | Yes | — |
| `call_step_type` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubprocessInterface`

Used by: `POST /api/v1/designer/catalog`

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

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | `string` | Yes | — |
| `value_schema` | `object` | Yes | Declared output schema matching the named child step output port. |
| `source_step` | `string` | Yes | Child graph step producing this output. |
| `source_port` | `string` | Yes | Output port on source_step. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SubprocessPort`

Used by: `POST /api/v1/designer/catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | `string` | Yes | — |
| `value_schema` | `object` | Yes | JSON Schema Draft 2020-12 type expected in the isolated child context. |
| `required` | `boolean` | No | A call must map this input when true. Default: `True`. |
| `assignment` | `string | null` | No | Actor or group assignment reference carried as a string. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_DependencyReadiness_`

Used by: `POST /api/v1/designer/dependency-readiness`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `DependencyReadiness` | Yes | — |

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

### `SuccessResponse_InspectorContract_`

Used by: `GET /api/v1/designer/inspector-contract`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `InspectorContract` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_InspectorValidationResult_`

Used by: `POST /api/v1/designer/config-validation`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `InspectorValidationResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
