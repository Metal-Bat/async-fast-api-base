---
tags: [api, dto, auth]
---

# auth response DTOs

These schemas are emitted by successful API responses in this topic. Reviewed examples are included only when a curated fixture exists. Required nullable fields must be present and may be null; optional fields may be omitted as allowed by the schema. See the [frontend journey](../../guides/frontend-journey.md) for lifecycle and call order. The live Swagger/OpenAPI document is authoritative.

### `SuccessResponse_NoneType_`

Used by: `POST /api/v1/auth/change-password`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/logout-all`, `POST /api/v1/auth/reset-password`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `null` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_TokenPairDTO_`

Used by: `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `TokenPairDTO` | Yes | — |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "success": true,
  "request_id": "docs-purchase-001",
  "error": null,
  "code": 200,
  "data": {
    "access_token": "synthetic-access-token",
    "refresh_token": "synthetic-refresh-token",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

### `SuccessResponse_UserDTO_`

Used by: `GET /api/v1/auth/me`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `UserDTO` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `SuccessResponse_dict_str__str__`

Used by: `POST /api/v1/auth/forgot-password`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `success` | `boolean` | No |  Default: `True`. |
| `request_id` | `string` | Yes | — |
| `error` | `null` | No | — |
| `code` | `integer` | No |  Default: `200`. |
| `data` | `object` | Yes | — |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.

### `TokenPairDTO`

Used by: `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/token`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `access_token` | `string` | Yes | — |
| `refresh_token` | `string` | Yes | — |
| `token_type` | `string` | No |  Default: `bearer`. |
| `expires_in` | `integer` | Yes | — |

Reviewed synthetic example from the [frontend journey](../../guides/frontend-journey.md). Replace references and tokens with server-returned values; this is not a captured response.

```json
{
  "access_token": "synthetic-access-token",
  "refresh_token": "synthetic-refresh-token",
  "token_type": "bearer",
  "expires_in": 900
}
```

### `UserDTO`

Used by: `GET /api/v1/auth/me`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ref_id` | `string` | Yes | Opaque versioned user reference. |
| `username` | `string` | Yes | Unique username. |
| `email` | `string | null` | Yes | Unique email address. |
| `created_at` | `string` | Yes | UTC creation timestamp. |
| `updated_at` | `string | null` | Yes | UTC timestamp of the most recent update. |
| `deleted_at` | `string | null` | Yes | UTC soft-deletion timestamp. |
| `first_name` | `string | null` | No | Given name. |
| `last_name` | `string | null` | No | Family name. |
| `is_superuser` | `boolean` | Yes | Administrative privilege flag. |
| `is_active` | `boolean` | Yes | Whether the user is not soft-deleted. |

No reviewed business example is published for this schema. Use the field contract above and the [response scenarios](../../api/response-scenarios.md); do not infer valid lifecycle values from field types alone.
