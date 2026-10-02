---
tags: [api, dto, form-versions]
---

# form-versions response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `CatalogMessage`

Used by: `GET /api/v1/form-versions/{ref_id}`, `POST /api/v1/form-versions`, `POST /api/v1/form-versions/report`, `POST /api/v1/form-versions/search`, `POST /api/v1/form-versions/{ref_id}/publish`, `POST /api/v1/form-versions/{ref_id}/retire`, `PUT /api/v1/form-versions/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `text` | `string | PluralMessage` | Yes | Plain text with named {parameters}, or exactly one/other branches selected by integer count. No HTML, ICU, format specifiers or executable templates. |
| `parameters` | `object` | No | — |
| `source_revision` | `string | null` | No | Translation acknowledgement of the default message SHA-256 revision returned by validation/preview. Missing or old acknowledgements are draft gaps and block required-locale publication. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ComponentUpgradeIssue`

Used by: `POST /api/v1/form-versions/{ref_id}/reuse-upgrade-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `pointer` | `string` | Yes | — |
| `code` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ComponentUpgradePreview`

Used by: `POST /api/v1/form-versions/{ref_id}/reuse-upgrade-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `compatible` | `boolean` | Yes | — |
| `issues` | `array[ComponentUpgradeIssue]` | Yes | — |
| `manifest` | `array[object]` | Yes | — |
| `documents` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ComponentUse`

Used by: `GET /api/v1/form-versions/{ref_id}`, `POST /api/v1/form-versions`, `POST /api/v1/form-versions/report`, `POST /api/v1/form-versions/search`, `POST /api/v1/form-versions/{ref_id}/publish`, `POST /api/v1/form-versions/{ref_id}/retire`, `PUT /api/v1/form-versions/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `instance_key` | `string` | Yes | — |
| `component_ref` | `string` | Yes | — |
| `schema_pointer` | `string` | Yes | — |
| `node_pointer` | `string` | Yes | — |
| `parameters` | `object` | No | — |
| `message_overrides` | `object` | No | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FormDesignVariantDTO`

Used by: `GET /api/v1/form-versions/{ref_id}`, `POST /api/v1/form-versions`, `POST /api/v1/form-versions/report`, `POST /api/v1/form-versions/search`, `POST /api/v1/form-versions/{ref_id}/publish`, `POST /api/v1/form-versions/{ref_id}/retire`, `PUT /api/v1/form-versions/{ref_id}`

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

### `FormLocalization`

Used by: `GET /api/v1/form-versions/{ref_id}`, `POST /api/v1/form-versions`, `POST /api/v1/form-versions/report`, `POST /api/v1/form-versions/search`, `POST /api/v1/form-versions/{ref_id}/publish`, `POST /api/v1/form-versions/{ref_id}/retire`, `PUT /api/v1/form-versions/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `dialect` | `string` | No |  Default: `bpms.messages/1`. |
| `default_locale` | `string` | No |  Default: `en`. |
| `supported_locales` | `array[string]` | No |  Default: `['en']`. |
| `required_locales` | `array[string]` | No |  Default: `['en']`. |
| `catalogs` | `object` | No | Versioned administrator-authored catalogs, at most 256 messages per locale and 64 KiB in total. Regional requests fall back to their base language, then package default, then English. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `FormVersionDTO`

Used by: `GET /api/v1/form-versions/{ref_id}`, `POST /api/v1/form-versions`, `POST /api/v1/form-versions/report`, `POST /api/v1/form-versions/search`, `POST /api/v1/form-versions/{ref_id}/publish`, `POST /api/v1/form-versions/{ref_id}/retire`, `PUT /api/v1/form-versions/{ref_id}`

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
| `template_source` | `object | null` | No | — |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `form_ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `number` | `integer` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |
| `checksum` | `string | null` | Yes | — |
| `published_at` | `string | null` | Yes | — |
| `published_by_ref_id` | `string | null` | Yes | Opaque reference; use the value returned by the API. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HistoryRecordDTO`

Used by: `POST /api/v1/form-versions/{ref_id}/history`

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

### `PageResponse_Page_FormVersionDTO__`

Used by: `POST /api/v1/form-versions/report`, `POST /api/v1/form-versions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_FormVersionDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_HistoryRecordDTO__`

Used by: `POST /api/v1/form-versions/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_HistoryRecordDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_FormVersionDTO_`

Used by: `POST /api/v1/form-versions/report`, `POST /api/v1/form-versions/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[FormVersionDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HistoryRecordDTO_`

Used by: `POST /api/v1/form-versions/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HistoryRecordDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PluralMessage`

Used by: `GET /api/v1/form-versions/{ref_id}`, `POST /api/v1/form-versions`, `POST /api/v1/form-versions/report`, `POST /api/v1/form-versions/search`, `POST /api/v1/form-versions/{ref_id}/publish`, `POST /api/v1/form-versions/{ref_id}/retire`, `PUT /api/v1/form-versions/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `one` | `string` | Yes | — |
| `other` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ComponentUpgradePreview_`

Used by: `POST /api/v1/form-versions/{ref_id}/reuse-upgrade-preview`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ComponentUpgradePreview` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_FormVersionDTO_`

Used by: `GET /api/v1/form-versions/{ref_id}`, `POST /api/v1/form-versions`, `POST /api/v1/form-versions/{ref_id}/publish`, `POST /api/v1/form-versions/{ref_id}/retire`, `PUT /api/v1/form-versions/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `FormVersionDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/form-versions/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
