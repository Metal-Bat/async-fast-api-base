---
tags: [api, dto, me]
---

# me response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `AppearancePreferences`

Used by: `GET /api/v1/me/preferences`, `PATCH /api/v1/me/preferences`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `theme_mode` | `string` | No | Appearance mode; system follows the device preference. Default: `system`. |
| `theme_key` | `string` | No | Approved workspace palette key, shared with the frontend. Default: `blue`. |
| `density` | `string` | No | Workspace control density. Default: `comfortable`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HelpActionResult`

Used by: `POST /api/v1/me/help-state/dismiss`, `POST /api/v1/me/help-state/seen`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `saved` | `boolean` | Yes | True only when the explicit help action was persisted. |
| `reason` | `string` | Yes | Safe compatibility result; failure to save never authorizes or completes business work. |
| `state` | `HelpStateDTO | null` | No | Authoritative saved state; null for an incompatible or unavailable release. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HelpResetResult`

Used by: `POST /api/v1/me/help-state/reset`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `deleted_records` | `integer` | Yes | Number of self help-state records removed; preferences and business data are preserved. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HelpStateDTO`

Used by: `GET /api/v1/me/help-state`, `POST /api/v1/me/help-state/dismiss`, `POST /api/v1/me/help-state/seen`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `help_key` | `string` | Yes | Help actually opened or dismissed by this authenticated user. |
| `revision` | `string` | Yes | Exact frontend content revision; stale revisions are not persisted. |
| `locale` | `string` | Yes | Locale actually opened or dismissed; locales are acknowledged independently. |
| `first_viewed_at` | `string | null` | Yes | First explicit open in UTC, preserved on repeats; null if only dismissed. |
| `last_viewed_at` | `string | null` | Yes | Latest explicit open in UTC; list reads never update it. |
| `dismissed_at` | `string | null` | Yes | First explicit dismissal in UTC, or null. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `HelpStatePage`

Used by: `GET /api/v1/me/help-state`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `release_key` | `string | null` | Yes | Configured frontend metadata release, or null when unavailable. |
| `states` | `Page_HelpStateDTO_` | Yes | Only the authenticated user's bounded help-state page. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `LocalePreferences`

Used by: `GET /api/v1/me/preferences`, `PATCH /api/v1/me/preferences`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `language` | `string` | No | Preferred presentation language; canonical data stays unchanged. Default: `en`. |
| `timezone` | `string` | No | Valid IANA timezone for presentation; timestamps remain UTC. Default: `UTC`. |
| `calendar` | `string` | No | Gregorian calendar only; Persian language does not select a different calendar. Default: `gregory`. |
| `numbering` | `string` | No | Preferred display digits; stored numbers keep their canonical format. Default: `latn`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `NotificationPreferences`

Used by: `GET /api/v1/me/preferences`, `PATCH /api/v1/me/preferences`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `email_enabled` | `boolean` | No | Opt in to optional application email; mandatory security and approval notices remain enabled. Default: `False`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_HelpStateDTO_`

Used by: `GET /api/v1/me/help-state`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[HelpStateDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PreferencesDTO`

Used by: `GET /api/v1/me/preferences`, `PATCH /api/v1/me/preferences`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | `integer` | No | Version of the typed personal settings contract. Default: `1`. |
| `appearance` | `AppearancePreferences` | No | Appearance settings. |
| `locale` | `LocalePreferences` | No | Language, timezone, calendar and display digits. |
| `workspace` | `WorkspacePreferences` | No | Personal workspace defaults. |
| `notifications` | `NotificationPreferences` | No | — |
| `ref_id` | `string` | Yes | Current self-owned optimistic reference; version zero represents unsaved defaults. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ProfileDTO`

Used by: `GET /api/v1/me/profile`, `PATCH /api/v1/me/profile`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Current self-profile reference from the identity owner. |
| `first_name` | `string | null` | Yes | User-editable given name, or null. |
| `last_name` | `string | null` | Yes | User-editable family name, or null. |
| `avatar_ref_id` | `string | null` | Yes | Current private owned image reference, or null; download uses the existing authorized media route. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_HelpActionResult_`

Used by: `POST /api/v1/me/help-state/dismiss`, `POST /api/v1/me/help-state/seen`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `HelpActionResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_HelpResetResult_`

Used by: `POST /api/v1/me/help-state/reset`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `HelpResetResult` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_HelpStatePage_`

Used by: `GET /api/v1/me/help-state`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `HelpStatePage` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_PreferencesDTO_`

Used by: `GET /api/v1/me/preferences`, `PATCH /api/v1/me/preferences`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `PreferencesDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_ProfileDTO_`

Used by: `GET /api/v1/me/profile`, `PATCH /api/v1/me/profile`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `ProfileDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `WorkspacePreferences`

Used by: `GET /api/v1/me/preferences`, `PATCH /api/v1/me/preferences`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `landing_key` | `string` | No | Allowlisted landing route key; a preference grants no screen permission. Default: `requests`. |
| `page_size` | `integer` | No | Default list page size, from 1 through 100 items. Default: `20`. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
