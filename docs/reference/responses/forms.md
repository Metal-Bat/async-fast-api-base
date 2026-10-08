---
tags: [api, dto, forms]
---

# forms response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `BehaviorPreview`

Used by: `POST /api/v1/forms/behavior-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `data` | `object` | Yes | — |
| `cleared` | `array[string]` | Yes | — |
| `required` | `array[string]` | Yes | — |
| `validation_timing` | `object` | No | — |
| `pending` | `array[string]` | No | — |
| `validation` | `ValidationResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CatalogMessage`

Used by: `POST /api/v1/forms/copy-component`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `text` | `string | PluralMessage` | Yes | Plain text with named {parameters}, or exactly one/other branches selected by integer count. No HTML, ICU, format specifiers or executable templates. |
| `parameters` | `object` | No | — |
| `source_revision` | `string | null` | No | Translation acknowledgement of the default message SHA-256 revision returned by validation/preview. Missing or old acknowledgements are draft gaps and block required-locale publication. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ComponentKind`

Used by: `POST /api/v1/forms/field-catalog`

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ComponentUse`

Used by: `POST /api/v1/forms/copy-component`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `instance_key` | `string` | Yes | — |
| `component_ref` | `string` | Yes | — |
| `schema_pointer` | `string` | Yes | — |
| `node_pointer` | `string` | Yes | — |
| `parameters` | `object` | No | — |
| `message_overrides` | `object` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FieldContract`

Used by: `POST /api/v1/forms/field-catalog`

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

### `FormDTO`

Used by: `GET /api/v1/forms/{ref_id}`, `POST /api/v1/forms`, `POST /api/v1/forms/report`, `POST /api/v1/forms/search`, `PUT /api/v1/forms/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `code` | `string` | Yes | — |
| `name` | `string` | Yes | — |
| `is_active` | `boolean` | No |  Default: `True`. |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `created_at` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FormDesignVariantDTO`

Used by: `POST /api/v1/forms/copy-component`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `priority` | `integer` | Yes | Descending branch order; the first matching variant wins. Shared design is the final fallback. |
| `condition` | `string | null` | No | Optional boolean expression over the declared client namespace, combined with client/range targets. Uses version_in_range(client.release, minimum, maximum_exclusive) for numeric releases; bounds are literal versions or null. Missing releases do not match. Errors fail selection. No request data, scripts or authorization grants. Null preserves legacy targeting. |
| `client_ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |
| `kind` | `string | null` | No | — |
| `minimum_release` | `string | null` | No | — |
| `maximum_release_exclusive` | `string | null` | No | — |
| `required_capabilities` | `array[string]` | No | — |
| `render_schema` | `object` | Yes | — |
| `page_settings` | `object` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FormDocuments`

Used by: `POST /api/v1/forms/copy-component`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `data_dialect` | `string` | No |  Default: `https://json-schema.org/draft/2020-12/schema`. |
| `render_dialect` | `string` | No |  Default: `bpms.render/1`. |
| `data_schema` | `object` | Yes | — |
| `behavior_dialect` | `string | null` | No | — |
| `render_schema` | `object` | Yes | Bounded bpms.render/1 document; POST /forms/render-schema returns its complete typed JSON Schema including messages, option_messages and bpms.format/1 field formatting. Message roles resolve to localized_text, localized_options and compatibility label/placeholder/accessibility fields in runtime views. |
| `page_settings` | `object` | No | — |
| `variants` | `array[FormDesignVariantDTO]` | No | — |
| `reuse_instances` | `array[ComponentUse] | null` | No | Exact authored component version references placed in empty render placeholders. Published versions pin fully resolved data/render snapshots and their transitive manifest. |
| `localization` | `FormLocalization | null` | No | Optional bpms.messages/1 catalog pinned with this exact version. Null preserves legacy reads and checksums. Draft gaps are warnings; required translations and matching parameters are mandatory at publication. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FormLocalization`

Used by: `POST /api/v1/forms/copy-component`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `dialect` | `string` | No |  Default: `bpms.messages/1`. |
| `default_locale` | `string` | No |  Default: `en`. |
| `supported_locales` | `array[string]` | No |  Default: `['en']`. |
| `required_locales` | `array[string]` | No |  Default: `['en']`. |
| `catalogs` | `object` | No | Versioned administrator-authored catalogs, at most 256 messages per locale and 64 KiB in total. Regional requests fall back to their base language, then package default, then English. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FormattedValue`

Used by: `POST /api/v1/forms/preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `node_pointer` | `string` | Yes | — |
| `canonical` | `string` | Yes | — |
| `display` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HistoryRecordDTO`

Used by: `POST /api/v1/forms/{ref_id}/history`

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

### `NavigationPlan`

Used by: `POST /api/v1/forms/navigation-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `dialect` | `string` | No |  Default: `bpms.navigation/1`. |
| `route` | `string` | Yes | — |
| `arguments` | `object` | Yes | — |
| `data_revision` | `string` | Yes | — |
| `result_schema` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `NavigationPreview`

Used by: `POST /api/v1/forms/navigation-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `plan` | `NavigationPlan` | Yes | — |
| `data` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `OptionResult`

Used by: `POST /api/v1/forms/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[SelectOption_str_]` | Yes | — |
| `page` | `integer` | Yes | — |
| `size` | `integer` | Yes | — |
| `total` | `integer` | Yes | — |
| `dialect` | `string` | No |  Default: `bpms.options/1`. |
| `key_encoding` | `string` | No |  Default: `json-scalar/1`. |
| `state` | `string` | Yes | — |
| `generation` | `integer` | Yes | — |
| `locale` | `string` | Yes | — |
| `source_revision` | `string` | Yes | — |
| `dependency_fingerprint` | `string` | Yes | — |
| `dependencies` | `object` | Yes | — |
| `remote` | `RemoteSource | null` | No | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_OptionResult_`

Used by: `POST /api/v1/forms/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `OptionResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_FormDTO__`

Used by: `POST /api/v1/forms/report`, `POST /api/v1/forms/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_FormDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_HistoryRecordDTO__`

Used by: `POST /api/v1/forms/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_FormDTO_`

Used by: `POST /api/v1/forms/report`, `POST /api/v1/forms/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[FormDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/forms/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PluralMessage`

Used by: `POST /api/v1/forms/copy-component`, `POST /api/v1/forms/preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `one` | `string` | Yes | — |
| `other` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PreviewDTO`

Used by: `POST /api/v1/forms/preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `valid` | `boolean` | Yes | — |
| `evaluated_data` | `object | null` | No | — |
| `issues` | `array[ValidationIssue]` | No | — |
| `checksum` | `string | null` | No | — |
| `warnings` | `array[ValidationIssue]` | No | Draft translation gaps. Publication promotes required gaps to errors. |
| `source_revisions` | `object` | No | Default message hashes for translation acknowledgement. |
| `render_schema` | `object | null` | No | — |
| `variant_key` | `string | null` | No | — |
| `page_settings` | `object | null` | No | — |
| `design_revision` | `string | null` | No | — |
| `localization` | `ResolvedLocalization | null` | No | — |
| `formatted_values` | `array[FormattedValue]` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RemoteSource`

Used by: `POST /api/v1/forms/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `dialect` | `string` | No |  Default: `bpms.options/1`. |
| `dependencies` | `object` | No | Named schema-scope bindings. Missing/null parents block loading; changed parents invalidate previous results and selections. Repeated rows bind within the same item. |
| `enabled_when` | `string | null` | No | Optional typed boolean expression over request data. Controls option availability, never writes or clears data. |
| `parent_change` | `string` | No |  Default: `invalidate`. |
| `removed_value` | `string` | No |  Default: `reject`. |
| `kind` | `string` | No |  Default: `remote`. |
| `membership` | `string` | No |  Default: `snapshot`. |
| `url` | `string` | Yes | Exact HTTPS URL approved by FORM_CLIENT_OPTION_URLS. Client GET only; no server fetching, credentials, redirects, embedded query or fragment. Submitted keys must still belong to the pinned schema enum. |
| `method` | `string` | No |  Default: `GET`. |
| `credentials` | `string` | No |  Default: `omit`. |
| `redirects` | `string` | No |  Default: `error`. |
| `items_pointer` | `string` | No |  Default: `/result/items`. |
| `key_pointer` | `string` | No |  Default: `/key`. |
| `value_pointer` | `string` | No |  Default: `/value`. |
| `search_parameter` | `string` | No |  Default: `search`. |
| `page_parameter` | `string` | No |  Default: `page`. |
| `size_parameter` | `string` | No |  Default: `size`. |
| `selected_parameter` | `string` | No |  Default: `selected`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ResolvedLocalization`

Used by: `POST /api/v1/forms/preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `dialect` | `string` | No |  Default: `bpms.messages/1`. |
| `resolved_locale` | `string` | Yes | — |
| `direction` | `string` | Yes | — |
| `catalog_revision` | `string` | Yes | — |
| `messages` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ResolvedMessage`

Used by: `POST /api/v1/forms/preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `locale` | `string` | Yes | — |
| `text` | `string | PluralMessage` | Yes | — |
| `parameters` | `object` | Yes | — |
| `source_revision` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RuntimeActionDTO`

Used by: `POST /api/v1/forms/runtime-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `kind` | `string` | Yes | — |
| `outcome_key` | `string` | Yes | — |
| `title` | `string` | Yes | — |
| `confirmation` | `string | null` | Yes | — |
| `required_scopes` | `array[string]` | Yes | — |
| `require_comment` | `boolean` | Yes | — |
| `validation` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RuntimeFieldMetadataDTO`

Used by: `POST /api/v1/forms/runtime-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `scope` | `string` | Yes | Visible JSON Schema property/items scope. |
| `validation_schema` | `object` | Yes | Bounded compiled schema of this visible field only. No defaults, examples, hidden properties or shared definitions; backend validates the full canonical document. |
| `writable` | `boolean` | Yes | — |
| `required` | `boolean` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `RuntimeFormStateDTO`

Used by: `POST /api/v1/forms/runtime-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `runtime_dialect` | `string` | No |  Default: `bpms.runtime/1`. |
| `resource_kind` | `string` | Yes | — |
| `resource_ref_id` | `string` | Yes | Current opaque revision-bearing reference for the owning request/work item; replace after every mutation. |
| `form_version_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `form_version_number` | `integer` | Yes | — |
| `submission_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `design_key` | `string` | Yes | Exact pinned client variant; locale changes cannot change this key. |
| `render_dialect` | `string` | No |  Default: `bpms.render/1`. |
| `data_dialect` | `string` | No |  Default: `https://json-schema.org/draft/2020-12/schema`. |
| `view_key` | `string` | Yes | — |
| `purpose` | `string` | Yes | — |
| `resolved_locale` | `string` | Yes | Locale selected by the pinned catalog, or negotiated en/fa fallback. |
| `direction` | `string` | Yes | — |
| `data` | `object` | Yes | Canonical actor-visible values. Hidden values are preserved only on the server. |
| `item_identity` | `object` | Yes | Stable row keys for visible collection paths only. |
| `page_settings` | `object` | No | Pinned display-only settings; optional pages contains at most 32 unique key/title/scopes entries with actor-readable scopes only. No scripts, bindings or runtime values. |
| `before_data` | `object | null` | No | Prior submitted data filtered through the same task view, or null when unavailable. |
| `before_item_identity` | `object | null` | No | Actor-filtered prior row identities; null when unavailable. / هویت مجاز ردیف‌های پیشین؛ در صورت نبودن null. |
| `render_schema` | `object` | Yes | Actor-filtered bounded bpms.render/1 display document. Server-evaluated calculation metadata and client expressions are omitted; writable_scopes is authoritative for editability. |
| `readable_scopes` | `array[string]` | Yes | — |
| `writable_scopes` | `array[string]` | Yes | — |
| `required_scopes` | `array[string]` | Yes | — |
| `field_metadata` | `array[RuntimeFieldMetadataDTO]` | Yes | — |
| `actions` | `array[RuntimeActionDTO]` | No | — |
| `override_provenance` | `object` | No | Visible override actor/reason/value/time only; input checksums remain server-only. |
| `issues` | `array[object]` | No | Safe visible pointer/code pairs. Hidden canonical validation failures produce a generic task.validation issue. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SelectOption_str_`

Used by: `POST /api/v1/forms/options`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `key` | `string` | Yes | — |
| `value` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_BehaviorPreview_`

Used by: `POST /api/v1/forms/behavior-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `BehaviorPreview` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_FormDTO_`

Used by: `GET /api/v1/forms/{ref_id}`, `POST /api/v1/forms`, `PUT /api/v1/forms/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `FormDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_FormDocuments_`

Used by: `POST /api/v1/forms/copy-component`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `FormDocuments` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NavigationPreview_`

Used by: `POST /api/v1/forms/navigation-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `NavigationPreview` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/forms/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_PreviewDTO_`

Used by: `POST /api/v1/forms/preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `PreviewDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_RuntimeFormStateDTO_`

Used by: `POST /api/v1/forms/runtime-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `RuntimeFormStateDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ValidationResult_`

Used by: `POST /api/v1/forms/validate`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ValidationResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_dict_str__Any__`

Used by: `POST /api/v1/forms/render-schema`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_list_FieldContract__`

Used by: `POST /api/v1/forms/field-catalog`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `array[FieldContract]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ValidationIssue`

Used by: `POST /api/v1/forms/behavior-preview`, `POST /api/v1/forms/preview`, `POST /api/v1/forms/validate`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `code` | `string` | Yes | — |
| `line` | `integer | null` | No | One-based source line for an expression issue; null for document-only issues. |
| `column` | `integer | null` | No | Zero-based source column for an expression issue; null when unavailable. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ValidationResult`

Used by: `POST /api/v1/forms/behavior-preview`, `POST /api/v1/forms/validate`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `valid` | `boolean` | Yes | — |
| `evaluated_data` | `object | null` | No | — |
| `issues` | `array[ValidationIssue]` | No | — |
| `checksum` | `string | null` | No | — |
| `warnings` | `array[ValidationIssue]` | No | Draft translation gaps. Publication promotes required gaps to errors. |
| `source_revisions` | `object` | No | Default message hashes for translation acknowledgement. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
