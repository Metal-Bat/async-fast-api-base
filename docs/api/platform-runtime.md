# Frontend platform runtime contract

Implemented on the reviewed baseline `8921841`, October 2, 2026. These additions supersede the readiness review's F01–F03 defects and C01–C03/C05/C06 gaps within the tested scope. Existing authentication, permissions, opaque references, error codes and snake_case envelopes remain authoritative.

## Ordinary actors

`POST /api/v1/request-types/eligible/search` requires `requests.start`. Example body: `{"page":1,"size":20,"supported_render_dialects":["bpms.render/1"]}`. Returns the normal `result` page with opaque type references and exact current published workflow/form pins. Filters run before pagination: active roots, published dependencies, workflow start grants, authenticated client/release restrictions, and renderer dialect. Missing/incompatible/unauthorized choices are all absent. Empty capabilities return an empty page. Selection grants no authority; create independently repeats eligibility checks. Browser client headers never establish confidential identity.

`GET /api/v1/business-requests/{ref_id}/view` requires `requests.start`, ownership/superuser and origin-client policy. It returns `bpms.runtime/1`, not a privileged authoring schema. Only DRAFT owners have writable scopes. Other states are summaries. Request DTOs now include `process_ref_id`, null before execution and the actual root process reference after submission. Existing process/timeline routes enforce their visibility policy; never derive a process ref from another opaque reference.

`GET /api/v1/work-items/{ref_id}/runtime?key=review` requires `requests.start` and item visibility. Omit key to select the pinned default view. Runtime state includes current owning/submission refs, pinned form/version/design identity, visible compiled field metadata, display-only render document, canonical visible values, stable row keys, effective writable/required scopes, actions and locale/direction. Nonclaimants and closed items have no writable scopes/actions. Hidden defaults, field schemas, values, input fingerprints and executable client expressions remain server-only. An incompatible pinned render dialect returns VERSION_CONFLICT (409).

Runtime display deliberately omits calculation/rule/default/source/navigation binding metadata. Use existing authorized option/navigation operations when implementing those features; do not reconstruct hidden input dependencies from authoring schemas. Validation metadata supports the backend's compiled JSON Schema subset; the backend validates the complete canonical document. The runtime and render dialects are independently versioned. Clients must reject unknown runtime/render dialects before attempting to render.

Example shape is emitted by `RuntimeFormStateDTO` in generated Swagger. Synthetic example references illustrate shape only; use server-returned references in commands.

## Mutations and reconciliation

| Operation | Result and next command | Replay |
| --- | --- | --- |
| Claim, save, complete/reject/return | WorkItemDTO contains current `ref_id` and authorized `runtime_state`. Replace references and evaluated values. | Existing command_key replay with the identical actor/action/payload; changed payload conflicts. |
| Collection edit, manual override | SuccessResponse data is now RuntimeFormStateDTO with current owning/submission refs, projected data/identity/provenance. | No idempotency key; never blindly replay on timeout. |
| Attachment mutations | Existing response shape; read `/runtime` before the next task command to reconcile current refs and canonical data. | Existing endpoint contract applies. |
| Request create/save/submit | Existing request DTO with actual `process_ref_id`; read `/view` for runtime state after mutation. | Submit uses its existing submit_key; save is revision checked. |

Collection/override runtime results replace their older narrower data response. Update clients before deploying both sides. Commands on a task must be serialized. Use the latest owning ref after each response, not the submission ref. A read accepts an earlier revision-bearing reference as an identifier and resolves current state if the actor still has access; writes reject stale revisions. A timeout without idempotency is uncertain: refetch and compare authorized state before deciding whether another command is appropriate.

For policy-filtered saves and completion, data is a patch of supplied writable fields. Omitted fields remain canonical; explicit null writes null and is validated against the schema. `delete_paths` explicitly removes writable object properties using instance JSON pointers, e.g. `/optional_note`; row-index deletion is rejected. Named edit `view_key` limits writes; summary/print views cannot write. Hidden/read-only fields cannot be overwritten, deleted through a parent, or exposed through validation errors. Restricted arrays retain canonical hidden columns; structural edits use stable-key collection commands. Legacy tasks with an empty field policy and no named view retain whole-document replacement semantics.

## Policy editors and kinds

RequestTypeDTO now returns `client_targets` with current client refs and minimum/inclusive and maximum/exclusive release bounds. PUT omission preserves targets. An explicit empty list deliberately clears them. Unrelated renames cannot relax confidential restrictions.

`POST /workflows/{ref_id}/grants/search` requires `workflows.manage`. `POST /integration-connections/{ref_id}/grants/search` requires `integrations.manage` plus per-connection manage/owner/superuser authority. Both return current nondeleted grants with bounded page/filter contracts and current target refs, not reconstructed audit history. Connection access denial is 403; missing roots are 404.

WorkItemDTO `kind` is HUMAN_TASK for form-backed tasks, AI_APPROVAL only when an actual AI approval association exists, and UNSUPPORTED otherwise. A missing form alone never implies AI support. Only HUMAN_TASK items carry the ordinary runtime form state.

All new runtime/catalog/grant responses are private, no-store. HTTP payload logs exclude business and authored documents. English/Farsi Swagger operation descriptions preserve machine keys, enums and operation IDs.

## Evidence

New unit regressions first failed against the unmodified baseline. The disposable PostgreSQL flow suite now includes real HTTP login/requester/reviewer/outsider sessions, hidden-field save/completion preservation, sanitized collection/override results, serialized owning references, runtime/catalog access, actual process navigation refs, confidential release boundaries, omitted versus explicit-clear restrictions, eligibility changes before creation, and per-connection current-grant authorization. ASGI tests intentionally do not start S3 lifespan; media delivery and worker deployment are separate existing integration gates.

## Server-resolved display state (frontend Step 20)

Authorized runtime reads include an optional `runtime_state` on each scalar render node:
`{"visible":true,"enabled":true,"required":false,"overridable":false}`. These are booleans evaluated from the pinned rules and current canonical data on the server. They contain no expressions, source bindings, input fingerprints or hidden values. Render `options.read_only` and effective writable scopes still restrict editing; an enabled flag never grants authorization. `overridable` requires the declared calculation permission and an editable, actor-visible scope. Override/reset keeps the existing protected endpoint and reason contract; its runtime response replaces evaluated values.

Flags refresh after authorized reads/saves. Unsaved dependency changes require saving before their server-calculated visibility/required state is authoritative. No browser expression evaluator or authoring-preview endpoint is advertised. Repeated-row behavior and host navigation remain later frontend capabilities. Existing clients may ignore these additional display hints; runtime/render dialects, DTO schema shapes and operation IDs are unchanged.

وضعیت نمایش `runtime_state` شامل پرچم‌های بولی `visible`، `enabled`، `required` و `overridable` است که با قواعد نسخهٔ ثابت و داده‌های فعلی روی سرور محاسبه می‌شوند. عبارت‌ها، وابستگی‌ها و مقادیر پنهان به مرورگر ارسال نمی‌شوند. فعال بودن کنترل مجوز ویرایش نمی‌دهد؛ محدودهٔ قابل نوشتن و مجوز بازنویسی همچنان روی سرور بررسی می‌شود. وضعیت پس از خواندن یا ذخیرهٔ مجاز تازه می‌شود.

See [operations runtime additions](operations-runtime.md) for private binary responses, authorized metadata history, bounded pages and correction row identities. / برای قراردادهای افزوده، [اجرای عملیات](operations-runtime.md) را ببینید.
