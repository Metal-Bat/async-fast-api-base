---
tags: [api, dto, definition-library]
---

# definition-library response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `BulkUpgradeReport`

Used by: `POST /api/v1/designer/library/upgrade-apply`, `POST /api/v1/designer/library/upgrade-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `compatible` | `boolean` | Yes | — |
| `impacts` | `array[UpgradeImpact]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FormExplanation`

Used by: `POST /api/v1/designer/library/form-versions/{ref_id}/explanation`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `localization_issues` | `array[object]` | Yes | — |
| `rules` | `array[RuleExplanation]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `LibraryCard`

Used by: `POST /api/v1/designer/library/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `root_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `code` | `string` | Yes | — |
| `title` | `string` | Yes | — |
| `number` | `integer` | Yes | — |
| `category` | `string` | Yes | — |
| `help_text` | `string | null` | No | — |
| `sample_input` | `object` | No | — |
| `available_locales` | `array[string]` | No | — |
| `required_capabilities` | `array[string]` | No | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `LibraryDependency`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/dependencies`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `checksum` | `string | null` | No | — |
| `depth` | `integer` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `LibraryUsage`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/where-used`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `root_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `path` | `string` | Yes | — |
| `direct` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_LibraryCard__`

Used by: `POST /api/v1/designer/library/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_LibraryCard_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_LibraryUsage__`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/where-used`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_LibraryUsage_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_SelectOption_str___`

Used by: `POST /api/v1/designer/library/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_SelectOption_str__` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_LibraryCard_`

Used by: `POST /api/v1/designer/library/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[LibraryCard]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_LibraryUsage_`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/where-used`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[LibraryUsage]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_SelectOption_str__`

Used by: `POST /api/v1/designer/library/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SelectOption_str_]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ReplacementGuidance`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/guidance`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `deprecated` | `boolean` | Yes | — |
| `replacement_ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `reason` | `string | null` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RuleExplanation`

Used by: `POST /api/v1/designer/library/form-versions/{ref_id}/explanation`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `node_pointer` | `string` | Yes | — |
| `effect` | `string` | Yes | — |
| `source_scope` | `string` | Yes | — |
| `operator` | `string` | Yes | — |
| `description` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SelectOption_str_`

Used by: `POST /api/v1/designer/library/select`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_BulkUpgradeReport_`

Used by: `POST /api/v1/designer/library/upgrade-apply`, `POST /api/v1/designer/library/upgrade-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `BulkUpgradeReport` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_FormExplanation_`

Used by: `POST /api/v1/designer/library/form-versions/{ref_id}/explanation`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `FormExplanation` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ReplacementGuidance_`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/guidance`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ReplacementGuidance` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_TemplateDraft_`

Used by: `POST /api/v1/designer/library/templates`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `TemplateDraft` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_VersionComparison_`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/compare`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `VersionComparison` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_list_LibraryDependency__`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/dependencies`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `array[LibraryDependency]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TemplateDraft`

Used by: `POST /api/v1/designer/library/templates`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | — |
| `root_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `provenance` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `UpgradeImpact`

Used by: `POST /api/v1/designer/library/upgrade-apply`, `POST /api/v1/designer/library/upgrade-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `string` | Yes | — |
| `version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `compatible` | `boolean` | Yes | — |
| `affected_bindings` | `array[string]` | Yes | — |
| `issues` | `array[object]` | Yes | — |
| `translation_changes` | `array[string]` | Yes | — |
| `capability_changes` | `array[string]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `VersionComparison`

Used by: `POST /api/v1/designer/library/{kind}/{ref_id}/compare`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `source_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `target_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `changed_paths` | `array[string]` | Yes | — |
| `removed_capabilities` | `array[string]` | Yes | — |
| `added_capabilities` | `array[string]` | Yes | — |
| `removed_locales` | `array[string]` | Yes | — |
| `added_locales` | `array[string]` | Yes | — |
| `schema_compatible` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
