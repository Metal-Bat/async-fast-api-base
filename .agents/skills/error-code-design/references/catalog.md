# Proposed public error catalog

This is a target allocation, not a claim that the current application emits these numbers. Changing existing values affects clients that branch on `code`. Keep numbers globally unique; never reuse retired numbers.

| Range | Category | Use |
| --- | --- | --- |
| 1000–1999 | Common | Requests, resources, service failures |
| 2000–2999 | Authentication and access | Credentials, tokens, permissions, account state |
| 3000–3999 | Media | Upload validation and limits |
| 4000–4999 | Infrastructure | Safe dependency failures |
| 5000–8999 | Business | Allocate small blocks by domain when an actual invariant needs a distinct client action |

## Initial allocation

| Code | Name | HTTP | Public meaning |
| ---: | --- | ---: | --- |
| 1001 | `INVALID_REQUEST` | 400 | Malformed or unsupported request |
| 1002 | `VALIDATION_FAILED` | 422 | Request data fails validation |
| 1003 | `NOT_FOUND` | 404 | Resource unavailable to caller; also missing or corrupted uploads |
| 1004 | `VERSION_CONFLICT` | 409 | Resource changed since client's version |
| 1005 | `INVALID_REFERENCE` | 422 | Opaque reference cannot be accepted |
| 1006 | `RATE_LIMITED` | 429 | General request limit reached |
| 1098 | `SERVICE_UNAVAILABLE` | 503 | Temporary service failure without safe dependency-specific cause |
| 1099 | `INTERNAL_ERROR` | 500 | Unexpected failure |
| 2001 | `INVALID_CREDENTIALS` | 401 | Authentication failed |
| 2002 | `NOT_ALLOWED` | 403 | Authenticated actor lacks permission |
| 2003 | `ACCOUNT_LOCKED` | 423 | Account temporarily locked |
| 2004 | `INVALID_TOKEN` | 401 | Token invalid, expired, or revoked |
| 2005 | `USER_NOT_FOUND` | 404 | User cannot be found where disclosure is appropriate |
| 2006 | `INACTIVE_USER` | 401 | Account inactive |
| 3001 | `UPLOAD_TOO_LARGE` | 413 | Upload exceeds configured size |
| 3002 | `INVALID_IMAGE` | 422 | Image cannot be accepted |
| 3003 | `UPLOAD_RATE_LIMIT` | 429 | User upload limit reached |
| 4001 | `DATABASE_UNAVAILABLE` | 503 | Database or transaction temporarily unavailable |
| 4002 | `DATA_CONFLICT` | 409 | Client operation conflicts with known persisted data |
| 4003 | `CACHE_UNAVAILABLE` | 503 | Required cache unavailable |
| 4004 | `STORAGE_UNAVAILABLE` | 503 | Object storage unavailable |
| 4005 | `BROKER_UNAVAILABLE` | 503 | Task broker unavailable |

Existing `1004`, `1005`, `2003`, `2004`, and `2006` retain their numbers. Other current HTTP-like numbers change when this catalog is implemented. Success response codes remain HTTP-like and outside this catalog.

## PostgreSQL translation

Keep `postgresql.<SQLSTATE>` as an internal diagnostic identity, separate from the public integer code. Extract SQLSTATE from `SQLAlchemyError.orig` or a direct driver exception without parsing message text.

| SQLSTATE | Handling | Public result |
| --- | --- | --- |
| `23505` unique violation | Known, expected uniqueness rule may get a business code; generic conflict only when client-caused | Domain code or `4002` / 409 |
| `23503` foreign-key violation | Map only a known client-caused relationship conflict | Domain code or `4002` / 409 |
| `23502`, `23514` not-null/check violation | Validation only when rule directly reflects caller input; otherwise server defect | `1002` / 422 or `1099` / 500 |
| `40001`, `40P01` serialization/deadlock | Bounded transaction retry first; exhausted attempts mean temporary unavailability | `4001` / 503 |
| SQLSTATE class `08`, `53300`, `57P01` | Connection failure, too many connections, or shutdown | `4001` / 503 |
| Unknown, missing, or ambiguous | Do not infer client fault from broad `IntegrityError` or SQLAlchemy class | `1099` / 500 |

Only inspect constraint names in a server-owned allowlist for known business rules. Never return SQLSTATE, constraint names, SQL text, bound values, or provider wording. Log the diagnostic identity with `request_id`. Add `Retry-After` only when a real retry policy provides a useful delay.

## Business allocation

Reserve 5000–8999 until domain rules are implemented. Allocate a contiguous block per domain as it grows, such as users, reports, or tasks. Record each invariant, status, safe localized message, and whether retrying unchanged input can succeed. Use existing generic codes for ordinary not-found, invalid input, and authorization failures.
