---
tags: [api]
---

# Using client-aware form and workflow conditions

Requires the existing form/workflow designer permissions. Login binds a registered client to the
session; arbitrary client headers do not change predicate context. See
[client identity](client-designs.md) and [predicate semantics](../architecture/client-predicates.md).

## Preview a form

`POST /api/v1/forms/preview` requires `forms.manage` and returns the existing success envelope.
It validates every variant and resolves the current authenticated session's presentation without
saving or publishing anything. Example body:

```json
{
  "data_schema": {"type": "object", "properties": {}},
  "render_schema": {"root": {"component": "vertical"}},
  "variants": [
    {
      "key": "modern_desktop",
      "priority": 20,
      "condition": "client.kind == \"DESKTOP\" and version_in_range(client.release, \"2.10\", null)",
      "render_schema": {"root": {"component": "grid"}}
    },
    {
      "key": "android",
      "priority": 10,
      "condition": "client.kind == \"ANDROID\"",
      "render_schema": {"root": {"component": "vertical"}}
    }
  ]
}
```

Save the body as `form-preview.json` and call:

```sh
curl -X POST https://api.example.com/api/v1/forms/preview \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  --data-binary @form-preview.json
```

In the envelope's `data`, inspect `valid`, `issues`, `variant_key`, `design_revision`,
`render_schema` and `page_settings`. Desktop 2.10 selects `modern_desktop`; desktop 2.9, B2B and
legacy sessions fall back to `shared`; Android selects `android`. No secret is part of this body.

`POST /api/v1/forms/validate` validates the same contract without selecting a design. Bad expressions
produce `valid: false` with issues such as pointer `/variants/0/condition`, code
`expression.version.predicate_required`, line `1` and column `0`. Do not use
`client.release >= "2.10"`. Invalid request DTOs use the existing 422 envelope; unauthenticated or
unauthorized calls use existing auth errors. Runtime selection errors use the existing validation
error envelope and do not silently fall back.

Publish through the existing draft version and `/form-versions/{ref_id}/publish` lifecycle. Keep
opaque version references and returned design revision when editing an interaction; use explicit
cross-client resume instead of silently replacing its context.

## Workflow branches

Within one source/outcome, use priority 30 for the desktop range expression, 20 for Android,
and 0 for the unconditional `is_default: true` transition. Conditions are optional strings of at
most 1,024 characters. Default branches in client-aware groups cannot have a condition. Duplicate
priorities/defaults and unsupported expressions are rejected by existing graph validation with
exact pointers and source locations. Ordinary routing chooses one branch; explicit parallel splits
retain their existing semantics.

Designer `/catalog` includes `version_in_range`; `/completion` includes typed `client.*` paths
under existing workflow authorization. JSON names and expression keys remain the same in English
and Farsi. Human labels never become predicate values. Backend validation and preview are delivered;
an Angular condition editor remains BPMS-017.
