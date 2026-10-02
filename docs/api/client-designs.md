---
tags: [api]
---

# Client identity and form designs (BPMS-022)

All JSON keys use `snake_case`. Protected routes require a bearer access token and retain the shared `success`, `request_id`, `code`, `data` or paginated `result` envelopes. `Accept-Language: en|fa` chooses error and enum labels; IDs, client kinds, variant keys and version strings are never translated. Authentication uses the server-side `AUTH_SESSION` binding. `User-Agent` and client headers are diagnostics only.

## Register clients and releases

A user with `forms.manage` can create a client with `POST /api/v1/clients`. For a confidential registration, the response returns a random `secret` once; it is stored only as a hash. Public registrations return `secret: null` and cannot satisfy restricted request starts. `PUT /clients/{ref_id}` updates name/platform/active state, `POST /clients/{ref_id}/rotate-secret` rotates a confidential secret, and `DELETE` disables/soft-deletes. Search, detail, history, report and `POST /clients/select` use the normal resource contract. Writes with stale revision-bearing `ref_id` fail; history never returns the raw secret.

```json
{"code":"DESKTOP_OPERATIONS","name":"Operations desktop","kind":"DESKTOP","platform":"linux","confidential":true}
```

`POST /api/v1/client-releases` needs `forms.manage`, `client_ref_id`, a numeric `major.minor[.patch][-prerelease][+build]` version, `api_version`, and up to 32 unique renderer capabilities. Release detail/search/report/history/select and `POST /{ref_id}/disable` are protected. A disabled client or release invalidates future protected session use. Existing session tokens never gain a different client by changing headers.

```json
{"client_ref_id":"<client-ref>","version":"2.10","api_version":"v1","renderer_capabilities":["bpms.render/1"]}
```

Client and release `select` endpoints accept `SelectQuery` (`search`, `page`, `size`) and `response_format=page|items` (default `page`). The page format puts `items`, `page`, `size`, `total`, and `total_pages` under `result`; `items` returns the same bounded `[{"key":"<ref-id>","value":"Operations desktop"}]` slice. Keys are opaque revision-bearing references.

## Authenticate and target a request type

`POST /api/v1/auth/login` accepts optional `client_key`, `client_secret`, and `client_release` with the existing user credentials. All three omitted yields legacy context. An unknown key/release or invalid secret fails authentication. A public client sends key and release without a secret; the server records it as untrusted for restricted actions. A confidential secret authenticates the registered application/channel, not the physical device or its OS version. The access token carries a session ID; refresh retains the exact client/release binding.

Request type authoring accepts `client_targets`, each with an active confidential `client_ref_id` and optional inclusive `minimum_release` and exclusive `maximum_release_exclusive`. An empty list retains legacy start behavior; a nonempty list rejects untrusted, legacy or unmatched sessions even if they forge desktop headers. Workflow user/group start grants remain necessary. `allow_cross_client_resume` defaults to `false`.

```json
{"client_targets":[{"client_ref_id":"<desktop-ref>","minimum_release":"2.10","maximum_release_exclusive":"3.0"}],"allow_cross_client_resume":true}
```

## Shared and targeted form designs

`FormDocuments` keeps one `data_schema` and adds `page_settings` plus at most 32 `variants`. The existing `render_schema` is the shared fallback. A variant has a stable `key`, explicit `priority` (0–100), `render_schema`, optional `client_ref_id`, `kind`, release range, required renderer capabilities, and `page_settings` overrides. Ties whose client/kind/version targets can overlap fail publication. Higher priority wins; no match uses the shared design. Renderer capability mismatch fails explicitly. Old published checksums and render documents remain unchanged.

Page JSON is inert renderer data. It cannot authorize a server action or execute a script. Values are limited to 64 KiB, depth 24, and 2,048 nodes; credential-like keys are rejected. The returned root carries `schema_version: "bpms.page/1"`. Shared and targeted maps merge recursively; arrays and `null` replace inherited values. Page values may contain renderer-specific opaque options. `POST /forms/validate` and `/forms/preview` validate the same canonical data schema and every variant renderer. Preview uses the authenticated session context and returns `variant_key`, `design_revision`, effective `render_schema`, and `page_settings`; unsupported capabilities return a validation error.

```json
{"data_schema":{"type":"object","properties":{"name":{"type":"string"}}},"render_schema":{"dialect":"bpms.render/1","root":{"component":"vertical"}},"page_settings":{"schema_version":"bpms.page/1","navigation":{"mode":"tabs"}},"variants":[{"key":"desktop","priority":10,"kind":"DESKTOP","minimum_release":"2.10","render_schema":{"dialect":"bpms.render/1","root":{"component":"grid"}},"page_settings":{"navigation":{"mode":"sidebar"}}}]}
```

## Request and human interaction pins

`POST /business-requests` snapshots credential-free origin context for background workflow evaluation. Its `design_snapshot` contains the selected variant, hash-like design revision, effective renderer/page JSON, client context, and interaction revision. Request and work-item detail responses expose that pin. Draft update, submit and cancel require the session bound to its current interaction. `POST /business-requests/{ref_id}/resume-presentation` opens a new interaction only for a draft owned by the caller when `allow_cross_client_resume=true` and the new session is trusted; it keeps request origin, form version and data fixed, audits the new snapshot, and increments `interaction_revision`. A submitted design snapshot is sealed by PostgreSQL. Human work-item creation selects and pins its presentation from the saved request origin; work-item actions use the existing user/group permissions and do not add a client-kind gate.

Legacy callers receive the shared view for unrestricted request types. B2B/SDK clients with no renderer capability can submit canonical data through that fallback. UI visibility never replaces server authorization. Cache keys for rendered designs must include form version, design revision, client/release, locale, and authorization scope; server responses in this module are not cached.

Errors use the project's localized envelope. Common failures include 401 for invalid credentials or revoked sessions, 403 for missing permission or client policy, 404 for inaccessible references, 409 for stale versions or immutable lifecycle state, and 422 with pointer-based issues for invalid ranges, JSON or renderer documents.
