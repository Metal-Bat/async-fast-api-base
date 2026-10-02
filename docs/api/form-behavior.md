---
tags: [api]
---

# Deterministic form behavior and collection editing

`bpms.behavior/1` is an opt-in behavior dialect on a form version. Versions without `behavior_dialect` keep the previous render and validation behavior and their prior checksum algorithm. The new dialect uses the published `bpms.render/1` calculation and rule declarations. No client script is executed by the backend.

## Evaluation order

At draft creation only, the server starts with existing data, including explicit `null`, fills missing fields from authorized initial data, then fills still-missing JSON Schema defaults. Initialization does not run on subsequent save, preview, locale change, or submit. `POST /forms/behavior-preview` can model this one-time step with `initialize: true`; it does not persist.

The evaluator then computes fields in dependency order, evaluates visibility rules, clears hidden values, and enforces conditional requirements. A calculation cycle, duplicate target or reference into an unbound repeated row is invalid at form publication. Registered `sum`, `concat`, and `count` functions and bounded typed expressions use the existing expression compiler. Repeated row functions bind source scopes within each concrete row. A source in another repeated collection is rejected during publication. Repeated expressions are rejected until a typed row namespace exists. `sum` converts decimal input through decimal arithmetic before returning canonical JSON numbers, avoiding binary float artifacts such as `0.30000000000000004` for `0.1 + 0.2`.

Visibility does not remove JSON Schema obligations. If a hidden field is still required by the canonical schema, submission fails. UI `validation_timing` and `pending` remote-source hints appear in behavior preview, but server validation always runs at submit. Display localization, digits, timezone, and date formatting remain separate from canonical values; the existing `bpms.format/1` formatter and canonical-value validator continue to govern those fields.

`POST /forms/behavior-preview` accepts `documents`, `data`, optional `initial`, and `initialize`. It returns canonical `data`, `cleared` concrete paths, `required` concrete paths, `validation_timing`, `pending`, and the same `ValidationResult` used by authoritative submission. The [shared fixture](../../tests/fixtures/form_behavior_v1.json) is suitable for Angular/native client conformance tests.

## Server-authoritative calculations and overrides

Request and work-item draft saves recompute calculated fields. Submission runs the same evaluator again and rejects altered computed values (`behavior.derived_tampered`) or submitted values for hidden fields (`behavior.hidden_tampered`). The canonical evaluated data is stored before option validation and workflow completion.

A calculation may declare `override_permission`. Only a user with that permission may call `POST /business-requests/{ref_id}/overrides` on an owned draft or `POST /work-items/{ref_id}/overrides` on a claimed draft. A `set` command includes `scope`, `value`, and a meaningful `reason`; the value must match the field schema. The separate `override_provenance` record stores the actor ref, reason, value, UTC time, and checksum of source values. The override remains valid only while those source values match. Changed sources fail with `behavior.override_stale` until an explicit `reset` command removes the provenance and recomputes. Unknown or incomplete provenance is rejected. Stable item keys and stored override records are metadata, not an authorization substitute.

Example command:

```json
{
  "scope": "/properties/total",
  "operation": "set",
  "value": 7,
  "reason": "Approved adjustment"
}
```

## Stable collections

`POST /business-requests/{ref_id}/collections/edit` and `POST /work-items/{ref_id}/collections/edit` accept a declared object-array `path`, `operation` (`add`, `remove`, `reorder`, or `duplicate`), an `item_key` for existing rows, optional `target_index`, and a new `value` for `add`. The current revision-bearing resource ref and normal owner/claimant and client checks apply. Stale refs fail with `VERSION_CONFLICT`.

The response returns canonical `data`, an `item_identity` map of concrete array paths to UUIDv7 keys, and validation issues annotated with the affected item keys. Identity remains separate from business data. Reordering moves nested identity subtrees and active attachment field paths in one transaction. Removed rows remove their active attachment links; duplicated rows get new keys and empty attachment fields while the original keeps its links. Full draft saves preserve keys for existing arrays and reject untracked length changes; clients use the edit endpoint for structural changes. The identity map lets clients keep local errors and correction feedback attached to the same row after movement.

Example:

```json
{
  "path": "/rows",
  "operation": "reorder",
  "item_key": "0199b24f-5dc7-7fc6-9e27-1af60e65972a",
  "target_index": 0
}
```

## Storage and compatibility

Alembic revision `58e200bb4077` adds nullable `FORM_VERSION.BEHAVIOR_DIALECT` and audited nullable `FORM_SUBMISSION.ITEM_IDENTITY` and `OVERRIDE_PROVENANCE` columns. Existing rows remain null and retain their behavior and checksum. The migration is reversible without a data rewrite. Both request and human-work submissions use the same evaluator and the published authored render selected by the submission’s pinned variant key. No new environment variables or Python dependencies are required.
