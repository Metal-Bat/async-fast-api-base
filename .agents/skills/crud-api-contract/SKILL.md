---
name: crud-api-contract
description: Apply this project's fixed CRUD, search, detail, history, and report HTTP route contract and subject-based Swagger ordering when adding or changing resource endpoints.
---

# CRUD API Contract

## Required tests and delivery checks

Never add or change a route before a failing test describes its observable contract. Exercise
business behavior through the application-service seam and add a route/OpenAPI test for HTTP
exposure; do not place untested business decisions directly in a presentation handler.

Before delivery, run the project formatter, complete test suite, all lint/type checks, and all
pre-commit hooks. Every check must pass.

Apply one predictable interface to every resource so clients can derive routes without resource-specific rules.

For a plural resource base such as `/users`:

- Create: `POST /users`
- Search: `POST /users/search`. Accept the shared filter, sort, page, and size body and return the shared paginated response.
- Detail: `GET /users/{ref_id}`. Use the opaque, versioned `ref_id` exposed by the resource DTO.
- Update: `PUT /users/{ref_id}`. Treat the body as the complete client-supplied update representation. Keep server-managed fields out of it.
- Delete: `DELETE /users/{ref_id}`. Identify the resource only by `ref_id`, never by a mutable name.
- History: `POST /users/{ref_id}/history`. Accept the shared searchable pagination body and return the shared paginated response. Add this route for mutable persisted resources.
- Report: `POST /users/report`. Accept the same search body and return the same paginated response shape as search unless a specific report contract is requested.

Keep static paths such as `/search` and `/report` distinct from member identifiers in the OpenAPI interface. Use plural lowercase nouns for resource paths.

Every collection is bounded and paginated, including in-memory catalogs. Do not expose `/query`, unbounded `GET` collections, or `PATCH` update routes.

Immutable resources expose search and detail but no update. Operational actions that are not CRUD, such as retry, revoke, restore, password reset, or role assignment, may remain explicit member actions.

## Swagger presentation

Group operations by resource subject, not by HTTP method. Give each resource one focused OpenAPI
tag (for example, `permissions` and `roles`) and declare tag metadata in the intended subject order.
Within each subject, display the standard operations in this order:

1. Search
2. Detail
3. History
4. Report
5. Create
6. Update
7. Delete

Place resource-specific actions after the standard operations. Do not use Swagger's built-in
`method` sorter because it separates one resource workflow into GET, POST, PUT, and DELETE groups.
This is presentation order only: keep the HTTP methods and paths defined by this contract, including
`POST` for search, history, and report.

Return normal HTTP status codes in both the HTTP response and the response envelope for ordinary protocol errors: 400, 401, 403, 404, 409, 422, 429, 500, and 503. Reserve custom application codes for errors that represent a distinct business rule callers need to handle separately.

Localize every user-facing response message through the core gettext module. Refresh and compile Babel catalogs after adding or changing messages.

All JSON request DTOs, response DTOs, envelopes, and pagination models must inherit
`core.base_dto.BaseDTO`. Their canonical JSON and OpenAPI field names use `snake_case`; do not add
serialization aliases. Validation-only aliases are permitted only for explicit backward-compatible
input transitions.
