---
tags: [api, dto, calendar-events]
---

# calendar-events response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `AllDaySchedule`

Used by: `GET /api/v1/calendar/events/{ref_id}`, `POST /api/v1/calendar/events`, `POST /api/v1/calendar/events/report`, `POST /api/v1/calendar/events/search`, `PUT /api/v1/calendar/events/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `timezone` | `string` | Yes | IANA timezone for local presentation; canonical dates remain Gregorian. |
| `kind` | `string` | No |  Default: `all_day`. |
| `start_date` | `string` | Yes | Inclusive Gregorian date; no conversion into a timed event. |
| `end_date` | `string` | Yes | Exclusive Gregorian end date. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CalendarHistoryDTO`

Used by: `POST /api/v1/calendar/events/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `changed_at` | `string` | Yes | — |
| `operation` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `CalendarItemDTO`

Used by: `GET /api/v1/calendar/events/{ref_id}`, `POST /api/v1/calendar/events`, `POST /api/v1/calendar/events/report`, `POST /api/v1/calendar/events/search`, `PUT /api/v1/calendar/events/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `source_kind` | `string` | Yes | — |
| `title` | `string` | Yes | — |
| `schedule` | `TimedSchedule | AllDaySchedule | DeadlineSchedule` | Yes | — |
| `editable` | `boolean` | Yes | — |
| `route_key` | `string` | Yes | — |
| `work_group_ref_id` | `string | null` | No | Opaque reference; use the value returned by the API. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `DeadlineSchedule`

Used by: `GET /api/v1/calendar/events/{ref_id}`, `POST /api/v1/calendar/events`, `POST /api/v1/calendar/events/report`, `POST /api/v1/calendar/events/search`, `PUT /api/v1/calendar/events/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `kind` | `string` | No |  Default: `deadline`. |
| `due_at` | `string` | Yes | — |
| `timezone` | `string` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_CalendarHistoryDTO__`

Used by: `POST /api/v1/calendar/events/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_CalendarHistoryDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `PageResponse_Page_CalendarItemDTO__`

Used by: `POST /api/v1/calendar/events/report`, `POST /api/v1/calendar/events/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `result` | `Page_CalendarItemDTO_` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_CalendarHistoryDTO_`

Used by: `POST /api/v1/calendar/events/{ref_id}/history`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[CalendarHistoryDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `Page_CalendarItemDTO_`

Used by: `POST /api/v1/calendar/events/report`, `POST /api/v1/calendar/events/search`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `items` | `array[CalendarItemDTO]` | No | — |
| `page` | `integer` | No |  Default: `1`. |
| `size` | `integer` | No |  Default: `20`. |
| `total` | `integer` | Yes | — |
| `total_pages` | `integer` | Yes | Return the number of nonempty pages in the full result set. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `ReminderDTO`

Used by: `GET /api/v1/calendar/events/{ref_id}/reminders`, `GET /api/v1/calendar/work-reminders/{ref_id}`, `PUT /api/v1/calendar/work-reminders/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque reference; use the value returned by the API. |
| `due_at` | `string` | Yes | — |
| `status` | `string` | Yes | Lifecycle state; consult the owning resource guide. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_CalendarItemDTO_`

Used by: `GET /api/v1/calendar/events/{ref_id}`, `POST /api/v1/calendar/events`, `PUT /api/v1/calendar/events/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `CalendarItemDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_NoneType_`

Used by: `DELETE /api/v1/calendar/events/{ref_id}`, `DELETE /api/v1/calendar/work-reminders/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_list_ReminderDTO__`

Used by: `GET /api/v1/calendar/events/{ref_id}/reminders`, `GET /api/v1/calendar/work-reminders/{ref_id}`, `PUT /api/v1/calendar/work-reminders/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `array[ReminderDTO]` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TimedSchedule`

Used by: `GET /api/v1/calendar/events/{ref_id}`, `POST /api/v1/calendar/events`, `POST /api/v1/calendar/events/report`, `POST /api/v1/calendar/events/search`, `PUT /api/v1/calendar/events/{ref_id}`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `timezone` | `string` | Yes | IANA timezone for local presentation; canonical dates remain Gregorian. |
| `kind` | `string` | No |  Default: `timed`. |
| `start_at` | `string` | Yes | Inclusive aware instant, normalized to UTC. |
| `end_at` | `string` | Yes | Exclusive aware instant after start_at, normalized to UTC. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
