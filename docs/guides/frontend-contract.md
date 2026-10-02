# Shared frontend HTTP rules

Audience: frontend developers. Status: implemented contract. Reviewed: 2026-10-02.

[Walkthrough](frontend-journey.md) · [Documentation home](../Home.md)

## Authentication and client identity

Use JSON `POST /api/v1/auth/login` for application login. `/auth/token` is the OAuth form endpoint
used by Swagger and checks its separately configured client credentials. Do not copy Swagger
secrets into frontend code. Protected requests send `Authorization: Bearer <access_token>`.

`POST /auth/refresh` takes `{"refresh_token":"the-current-token"}` and returns a replacement pair
in `data`. Refresh tokens rotate. Serialize refresh across concurrent requests, replace both
tokens together, and discard the old refresh token. Reuse can revoke the session. An uncertain
refresh result may require signing in again; do not retry the consumed refresh token in a loop.
`POST /auth/logout` takes the refresh token to revoke that session. Clear local state on logout.

The example client keeps tokens in memory. It demonstrates protocol calls, not a full browser
session-storage architecture. Decide session persistence and cross-tab coordination explicitly.
A registered client/release is bound at login; changing a device label or User-Agent later does
not change authorization. Confidential client credentials require a trusted server boundary.

## Envelope, field and reference rules

- JSON names are `snake_case`. Machine values and enum codes are not translated.
- Success/detail responses use `data`; searches use `result` with `items`, `page`, `size`,
  `total` and `total_pages`. Selectors may explicitly support a plain array with
  `response_format=items`. A plain array is not an envelope.
- Success `code` usually mirrors the HTTP success status. Error `code` is a stable numeric
  application code. Always inspect the HTTP status and `success`; do not equate every `code`
  with HTTP status. Some no-content operations return HTTP 200 with envelope `code: 204`.
- A required nullable property must be present and may be null. An optional property may be
  omitted. These are different contracts; do not treat every missing field as null.
- `ref_id` includes revision information. Keep it opaque; use the current value returned by the
  server, encode it in URLs, and replace it after mutations. Never construct it from a UUID.
- Keep canonical form values separate from display labels, translations and render documents.
  Published versions are pinned for active cases. Use their returned snapshots and named views.

Full reviewed bodies are in the [example fixture](../examples/frontend-journey.json).
The [response reference](../reference/responses/index.md) lists all fields, including schemas
without a reviewed business example. Live JSON OpenAPI is `/api/v1/openapi.json`.

## Parameters and defaults used in the walkthrough

| Name | In | Type | Required | Default | Constraints | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `ref_id` | path | string | yes | none | opaque server-issued value | Current resource and revision; encode as one segment. |
| `Authorization` | header | string | protected calls | none | `Bearer <access_token>` | User session, not a resource grant by itself. |
| `Accept-Language` | header | string | no | English fallback | supported English/Farsi negotiation | Message and presentation language; docs are English. |
| `Content-Type` | header | string | JSON bodies | none | `application/json` | Login in this guide is JSON, not OAuth form data. |
| `page` | body | integer | no | 1 | ≥1 | One-based page number. |
| `size` | body | integer | no | 20 | 1–100 | Maximum items in the requested page. |
| `cartable` | body | string | work search | none | available, claimed, completed, watching, submitted, unread | Which personal/eligible work list to query. |
| `key` | query | string | no | pinned default view | ≤64 characters | Named human-task view. |
| `priority` | body | integer or null | no | configured priority on creation | 0–9 | Scheduling priority, not an authorization level. |
| `data` | body | object | save/complete | creation defaults to `{}` | pinned form and field policy | Canonical form values; save sends the intended replacement data. |
| `submit_key` | body | string | submit | none | 1–128 characters | Stable key for one logical request submission. |
| `command_key` | body | string | task commands | none | 1–128 characters | Stable key for one task action and payload. |
| `outcome_key` | body | string | finish action | none | 1–64 characters; declared outcome | Copy from the selected available task action. |
| `comment` | body | string or null | when action requires it | null | ≤4,000 characters | Human explanation for the decision. |

Login requires `username` (maximum 255 characters) and `password`; `device_name` is optional,
maximum 255. Optional `client_key`, `client_secret`, `client_release` follow the
[registered-client contract](../architecture/client-context.md). Draft creation also requires
`request_type_ref_id`. Refresh and logout require `refresh_token`.

Shared searches accept `filters` and `sort_orders`; work-item search instead uses its specific
cartable DTO. Example for request search:

```json
{"page":1,"size":20,"filters":[{"field_name":"status","operation":"equal","value":"DRAFT"}],"sort_orders":[{"field_name":"created_at","operation":"desc"}]}
```

Use only fields/operators exposed for that resource. Going beyond the last page returns an empty
page; it is not permission to request an unbounded list.

## Error handling

These are actual numeric codes from the [error enums](../../src/utils/errors/common.py) and
[authentication enums](../../src/utils/errors/auth.py), mapped by
[exception handlers](../../src/utils/exception_handlers.py).

| HTTP | Code | Typical affected calls / condition | Frontend action |
| --- | ---: | --- | --- |
| 401 | 2001 | Login credentials invalid or protected session rejected | Sign in; do not loop retries. |
| 401 | 2004 | Refresh token invalid, expired or reused | Clear the stale pair and sign in. |
| 401 | 2006 | Account inactive | Contact administrator. |
| 403 | 2002 | Create/save/actions: missing permission, workflow access or client access | Explain access failure; do not retry as a different action. |
| 404 | 1003 | Detail/claim/actions: missing or invisible resource | Refresh list; avoid revealing hidden records. |
| 409 | 1004 | Save/submit/claim/actions: stale revision, wrong lifecycle or changed replay payload | Fetch latest state and reconcile. The same code covers more than stale edits. |
| 422 | 1002 | Login/save/submit/actions: DTO, form or action validation | Preserve input; show summary and any `data.issues`. |
| 422 | 1005 | Member routes: invalid opaque reference | Refetch refs; do not attempt to decode or repair them. |
| 423 | 2003 | Login: temporarily locked account | Wait/contact administrator. |
| 429 | 1006 | Common rate limit where enabled | Back off; honor `Retry-After` when present. |
| 500 | 1099 | Unexpected backend error | Show correlation ID; reconcile state before retrying a mutation. |
| 503 | 1098 | Application unavailable | Preserve edits and retry later where safe. Infrastructure failures may have their own codes. |

An error envelope has `success: false`, `request_id`, localized `error`, numeric `code`, and
nullable `data`. Validation examples and conflict responses are in fixture steps `invalid` and
`stale`. Do not depend on English error text for control flow. Not every validation response has
field issues, and transport/proxy errors may not have a JSON envelope at all.

Errors set `X-Request-ID`, `Content-Language` and `Vary: Accept-Language`. Protected request/task
documents use `Cache-Control: private, no-store`. Do not place them in a shared cache. Browser
access to a response header depends on the configured CORS exposure; the JSON `request_id` is
available without reading that header. Download endpoints can return binary bodies instead of
JSON; use the [private download guide](../api/private-media-downloads.md).

## Retry boundaries

Retry only when the operation's contract supports it. Retain a submit/action key and its exact
payload until success is known. A changed form or a different action needs a new key. Creating a
draft and replacing request data do not accept those keys. Refresh-token rotation also needs
special handling. The TypeScript example deliberately leaves retry decisions with the caller.
