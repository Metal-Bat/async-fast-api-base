---
tags: [architecture]
---

# Versioned forms

The `apps.forms` module owns form authoring. All routes require `forms.manage`; JSON contracts
inherit `BaseDTO` and use snake_case. `/forms` and `/form-versions` provide create, search,
detail, update, delete, history, and report operations. Version searches require `form_ref_id`.
POST `/forms/validate`, `/forms/preview`, and `/forms/render-schema` provide validation, a
renderer-neutral preview document, and the generated render meta-schema respectively.

## Documents and validation

Data dialect is `https://json-schema.org/draft/2020-12/schema`; render dialect is `bpms.render/1`.
The server uses `jsonschema` Draft202012Validator for schema and instance validation. Pydantic
alone generates schemas but does not validate arbitrary submitted schemas. `rfc3339-validator`
makes date-time validation available rather than silently accepting malformed dates.

This is a deliberately bounded subset: object roots, primitive types, properties, required,
additionalProperties, arrays/items/prefixItems, enum/const, numeric and length bounds, annotations,
and date/date-time/email/uuid formats. References are acyclic local `#/$defs/` references.
Unknown keywords, regular expressions, combinators, dynamic references, and network references
are rejected. The implementation's keyword allowlist is authoritative.

Each document is limited to 65,536 serialized bytes, 2,048 nodes, nesting depth 24, and lists of
256 entries. Reference chains are limited to 16, expansion to 2,048 nodes, and expanded schemas
are bounded again. Instance validation also has a schema/data work-product budget of 100,000.
At most 32 issues are returned, containing a JSON pointer and machine code without submitted
values. The checksum is SHA-256 over canonical sorted compact JSON documents.

Example document pair:

```json
{
  "data_schema": {
    "type": "object",
    "properties": {"name": {"type": "string", "maxLength": 100}},
    "required": ["name"],
    "additionalProperties": false
  },
  "render_schema": {
    "dialect": "bpms.render/1",
    "root": {
      "component": "vertical",
      "children": [{"component": "text", "scope": "#/properties/name", "label": "Name"}]
    }
  }
}
```

RenderNode registers layout/display, primitive, choice, date, user/group, repeater/table,
calculated, media, attachment_collection, and action controls. Only `default` and `compact`
renderers and `users`/`work_groups` selectors are accepted. Options are checked for component
compatibility; grid bounds, accessibility, localization keys, and child placement are validated.
Scopes traverse only properties, items, and prefixItems schema locations. Target types must
match the control. Date controls require matching formats; choices require enums or selectors.
Actions refer to declared outcomes. Conditional rules use eq/ne/present; calculations declare
sum/concat/count with compatible input/output types. These are validated metadata: expression
execution belongs to BPMS-008. No JavaScript, Python, arbitrary selector URL, or HTML execution
is provided. A future renderer must escape labels and other text.

Validation and preview return `valid`, `issues`, and an optional checksum; invalid preview is a
successful validation operation with `valid=false`. Invalid publication raises 422/public code
1002 with `data.issues`. Preview returns a validated render document, not a visual frontend.
Attachment storage and submission rules remain BPMS-004/BPMS-009.

## Lifecycle and persistence

Definitions and versions have UUIDv7 identities, optimistic versions, and generated histories.
Draft documents may be replaced using a fresh opaque reference. Publication locks the version
and active definition, validates again, and stores checksum, actor, and time atomically.
PostgreSQL additionally prevents inserting a published version or modifying/deleting a
published/retired version, except the published-to-retired transition. Only drafts can be deleted.
Concurrent publishers cannot both succeed.

An exact opaque version reference continues to resolve after retirement or root deactivation;
future runtime publication must require PUBLISHED for new consumers. Existing consumers retain
their exact version. Historical reads do not require a current optimistic version; mutations do.
There is no runtime submission or browser form renderer in this module.

Apply migration `be9a70072a3d` after `b8d982c92b94`. It adds FORM_DEFINITION, FORM_VERSION, both
histories, constraints, indexes, and immutability triggers without rewriting existing data.

## Dynamic primitive contracts

BPMS-024 centralizes primitive definitions in `apps.forms.domain.fields`. Validator, DTO enum and
designer metadata derive from that registry. Option sources and host navigation remain pinned
render JSON; current domain memberships are checked at request submission and human completion.
See [dynamic field API and client contract](../api/form-fields.md) for wire encoding, visibility,
race handling, host policy, atomic navigation proposals and shared client examples.
