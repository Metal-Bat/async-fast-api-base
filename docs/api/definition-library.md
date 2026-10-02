---
tags: [api]
---

# Definition library and draft upgrade API

The definition library serves published authored components, data types, and callable subprocess versions. It reuses the existing form-library grants and workflow access grants. It creates independent form/workflow drafts from exact published versions and previews proposed draft upgrades before any write. The API does not maintain a marketplace or change a published snapshot.

All paths below have `/api/v1` prefix, require a bearer token, accept and return `application/json`, and use snake_case fields. `ref_id` values contain an opaque row ID and revision; obtain them from a search or detail response. A stale write returns `VERSION_CONFLICT`. The normal response envelope is `{"success":true,"request_id":"...","error":null,"code":200,"data":...}`; paginated endpoints use `result` containing `{items,page,size,total}`. A created template returns HTTP 201 and `code:201`. Errors use the existing localized envelope, for example `{"success":false,"request_id":"...","error":"Validation failed","code":422,"data":{"issues":[{"pointer":"/targets","code":"library.duplicate_target"}]}}` (issue placement follows the shared validation handler). `Accept-Language: fa` localizes the envelope and Swagger text; keys, ref IDs, enums, and submitted values remain canonical.

## Permissions and visibility

`forms.manage` is required for component, data-type and form operations; `workflows.manage` is required for subprocess and workflow operations. Mixed searches and mixed upgrade batches require both. A component or data-type version must be owned by the caller or shared through a current direct or active work-group use grant. A subprocess must be viewable under the current workflow owner, OPEN, or view grant rule. New workflow calls need start access when validated. Search and where-used omit inaccessible definitions and counts. Form versions follow the existing `forms.manage` authoring permission. These responses are authoring metadata, not authorization to execute a process or read protected form inputs.

## Search and inspect

| Method and path | Request | Result |
| --- | --- | --- |
| `POST /designer/library/search` | `LibrarySearch`: `page` 1–100 (default 1), `size` 1–100 (default 20), optional `kind`, `search` (1–100 chars), `category` (1–64 chars), `locale` (`en`/`fa`, default `en`), `capabilities` (up to 32). | Page of exact published version cards with category, help text, sample input, available locales and required capabilities. An absent locale falls back to English help. |
| `POST /designer/library/{kind}/{ref_id}/dependencies` | No body. | Direct and transitive exact version refs, checksum, and depth. Inaccessible dependencies are suppressed. |
| `POST /designer/library/{kind}/{ref_id}/where-used` | `LibrarySearch` page controls. | Visible draft/published consumer refs, binding path and `direct` flag. |
| `POST /designer/library/{kind}/{ref_id}/compare` | `{"other_ref_id":"<exact-ref>"}` | Changed JSON pointers, added/removed capabilities and help locales, and a conservative schema-equality flag. Preview the actual draft before applying. |
| `POST /designer/library/{kind}/{ref_id}/guidance` | No body. | Retirement/deprecation status and newest published version under the same definition, if any. A suggested version is never applied automatically. |
| `POST /designer/library/form-versions/{ref_id}/explanation` | No body. | Missing/stale translation pointers and bounded rule effects, source scopes and operators. Rule values and protected input data are omitted. |

`kind` is `component`, `data_type`, or `subprocess`. Search is bounded to 10,000 candidate versions per kind; requests beyond that limit return `VALIDATION_FAILED` rather than an incomplete total. Versions are sorted by kind, code, number, and ref ID before page slicing. A sample is optional authored metadata and is checked against the resolved data schema or declared subprocess ports during publication. It is not evidence of a successful execution.

Example request:

```http
POST /api/v1/designer/library/search
Authorization: Bearer <token>
Content-Type: application/json

{"kind":"component","category":"address","locale":"fa","page":1,"size":20}
```

Example page excerpt:

```json
{"success":true,"request_id":"<uuid>","error":null,"code":200,"result":{"items":[{"kind":"component","ref_id":"<exact-ref>","root_ref_id":"<root-ref>","code":"AddressEditor","title":"Address editor","number":2,"category":"address","help_text":"ویرایش نشانی","sample_input":{"city":"Tehran"},"available_locales":["en","fa"],"required_capabilities":[],"status":"PUBLISHED"}],"page":1,"size":20,"total":1}}
```

## Instantiate templates

`POST /designer/library/templates` accepts `kind` (`form` or `workflow`), `source_ref_id`, unique `code`, `name`, and `mode` (`COPY` or `REFERENCE`). It creates a new root and version 1 draft in one transaction, owned by the caller, with stored `template_source: {source_ref_id,source_checksum,mode}` on the new version. The source must be an exact published version and accessible. `COPY` embeds a form's resolved document without reusable component bindings. `REFERENCE` keeps its exact component pins and revalidates current grants. Workflow templates copy the graph as an independent draft; subprocess calls in that graph keep exact published child pins and are revalidated. The source is never changed. `template_source` remains visible on form and workflow version detail responses.

```http
POST /api/v1/designer/library/templates
Authorization: Bearer <token>
Content-Type: application/json

{"kind":"form","source_ref_id":"<published-form-ref>","code":"Purchase_v2","name":"Purchase draft","mode":"REFERENCE"}
```

HTTP 201 response `data` contains `kind`, `root_ref_id`, `version_ref_id`, and `provenance`. Duplicate codes, unavailable dependencies or invalid copied documents fail atomically. Retiring a source later does not change a created draft's stored content or provenance.

## Preview and apply bulk upgrades

`POST /designer/library/upgrade-preview` accepts `targets` (1–32). Each target supplies `kind` (`form` or `workflow`), a current draft `version_ref_id`, and 1–64 `replacements`. Form keys are `instance_key` values and point to exact published component versions. Workflow keys are step keys with subprocess calls and point to exact published child workflow versions. The response reports each affected binding, schema/translation/capability issues, and `compatible`; it makes no changes. Only drafts can be upgraded.

```http
POST /api/v1/designer/library/upgrade-preview
Authorization: Bearer <token>
Content-Type: application/json

{"targets":[{"kind":"form","version_ref_id":"<draft-ref>","replacements":{"billing":"<component-v2-ref>"}},{"kind":"workflow","version_ref_id":"<draft-workflow-ref>","replacements":{"manager_call":"<approval-v2-ref>"}}]}
```

A compatible response has `data.compatible: true` and one `impacts` item per target. `POST /designer/library/upgrade-apply` accepts the same body, locks drafts, recomputes compatibility, and writes all updates in one transaction. Any incompatible target rejects the whole batch with `VALIDATION_FAILED`; an obsolete draft revision returns `VERSION_CONFLICT`. Replayed apply calls with old revision refs fail as stale writes. Published versions remain immutable. The existing single-form `reuse-upgrade-preview` and ordinary draft edit routes continue to work.

## Errors and operational notes

| HTTP | Public code | Cause |
| --- | --- | --- |
| 401 | `INVALID_CREDENTIALS` | Missing or invalid bearer token. |
| 403 | `NOT_ALLOWED` | Missing `forms.manage` or `workflows.manage`. |
| 404 | `NOT_FOUND` | Missing or inaccessible exact definition. |
| 409 | `VERSION_CONFLICT` | Stale draft/source, retired replacement, immutable version, or inactive definition. |
| 422 | `VALIDATION_FAILED` | Unknown instance/step, malformed metadata, incompatible upgrade, size bound, invalid sample or publication contract. |

Apply migration `b13a0c7d2e44` before enabling template creation. It adds nullable template provenance to form/workflow versions and their history tables. No new environment variables, workers, packages, or client renderer behavior are required.
