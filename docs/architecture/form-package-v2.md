---
tags: [architecture]
---

# Form package v2 contract

Status: design contract for BPMS-026. The current API accepts only `FormDocuments` with
`bpms.render/1`. Nothing in this document is an implemented endpoint or migration. BPMS-022,
BPMS-027, BPMS-024, BPMS-028, BPMS-029, BPMS-030 and BPMS-031 implement the boundaries below.

## Envelope and ownership

`bpms.form/2` is the package dialect. A version has one `data_schema` (JSON Schema Draft
2020-12), one `behavior_schema` (`bpms.behavior/1`), a map of named `render_views`
(`bpms.render/2`), `localization` (`bpms.messages/1`), and `dependencies`. These are separate
versioned dialects; a package version pins all five documents and their resolved dependencies in
one publication transaction. The package has a canonical `default` view. Form definition/version
and workflow version remain separate entities; a workflow pins an exact published form version.
The published package is immutable, including resolved component, data-type and message snapshots.
Its checksum is SHA-256 of canonical UTF-8 JSON (sorted object keys, compact separators, finite
numbers) of the complete resolved package, including dialect names and dependency version IDs.
Do not use the existing v1 checksum algorithm for v2 or recompute an old checksum.

All API DTO fields, including envelope keys, are `snake_case` and inherit `BaseDTO`. Embedded
JSON Schema keywords (`$schema`, `$defs`, `additionalProperties`, etc.) keep their standard names.
Code-owned primitives live in the existing component/type catalog. BPMS-028 owns authored reusable
component and data-type versions. BPMS-031 owns subprocess interfaces. A template is copied into a
new draft; a reference resolves and pins an exact version at publication. No authored component
becomes a second editable field source after resolution: the package snapshot is authoritative.

## Bindings and identity

Bindings use JSON Pointer (RFC 6901) against the schema tree (`schema_pointer`, for example
`/properties/billing_address/properties/city`) and the submitted value tree (`value_pointer`, for
example `/billing_address/city`). The `schema_pointer` is a design-time type check; the
`value_pointer` identifies a concrete runtime value. Array schema traversal uses `/items`, while
array values use numeric indices only at submission time. A render node inside a repeated
component declares `item_pointer` as a relative pointer beginning at its current item (`./city`),
or `parent_pointer` beginning at the nearest enclosing collection item (`../currency`). These
relative forms are resolved to concrete value pointers using a collection context; escaping above
the document root or into another collection is invalid. JSON Pointer escapes `~0` and `~1` apply
after the relative prefix. Bindings never evaluate arbitrary expressions.

Each authored render node has a stable `node_key` unique within its view. Reusable component
instances have a stable `instance_key`; namespaced keys distinguish two uses of the same component.
Repeat items carry immutable, client-generated UUIDv7 `item_key` values in a separate editing
identity map, not in business data. Reorder preserves keys; remove/reinsert creates a new key.
The server checks uniqueness and maps keys to array positions at submission. These keys identify
edits and validation feedback, not entities. Entity `ref_id` remains an opaque revision-bearing
reference and cannot be substituted for a node or item key.

## Localization and client composition

`bpms.messages/1` supports `en` and `fa` catalogs with simple named placeholders (`{count}`),
plural branches `one` and `other`, and number/date formatting delegated to the negotiated locale.
No arbitrary ICU expression or executable template is accepted in the first profile. A catalog
entry contains text or a plural object; placeholder names and branch shape must agree across
locales. Values are escaped by the client renderer. Stable keys, enum values and issue codes are
never translated. Dependency messages are namespaced as
`component.<instance_key>.<message_key>`; package overrides must name an explicitly overridable
key. Fallback is requested locale, then package default locale, then `en`; missing after fallback
is a publication error. Historical versions retain their resolved text.

Client identity and release targeting belong to BPMS-022. A trusted authenticated client identity
is distinct from an untrusted device or User-Agent hint. A form variant may select a named view
and navigation configuration, but all variants share one canonical data schema and publication
checksum. The process snapshots its origin client and form version at start; later interactions
may choose a compatible view from the current client without changing those pins. BPMS-030 task
views and action profiles constrain the selected client view; neither view selection nor visibility
grants authorization or removes server-side required data.

| Condition | Resolution |
| --- | --- |
| Explicit task action profile and compatible client variant | Apply task policy first; choose the most specific matching client view within it. |
| Multiple variants at equal specificity | Publication fails as ambiguous; no runtime first-match rule. |
| No matching variant | Use `default` view if its capability requirements are met; otherwise fail with an unsupported-client result. |
| Missing preferred locale | Apply the catalog fallback chain above; never change the selected view. |
| Component default and package override | Package wins only for an explicitly overridable namespaced key; incompatible placeholders fail publication. |
| Host navigation policy and package URL | Host allowlist, scheme and client capability checks win; invalid URLs fail publication. |
| Task visibility and field authorization | Authorization and server validation win; hidden fields cannot become writable through a view. |

Client navigation configuration may contain administrator-authored HTTPS URLs and route strings,
but the host validates schemes, origins, templates and capabilities. The server never fetches a URL
from a form package; external calls use governed integration connections. Credentials and scripts
are forbidden in documents.

## Compatibility matrix

| Consumer / package | v1 (`bpms.render/1`) | v2 (`bpms.form/2`) |
| --- | --- | --- |
| Existing published forms and process pins | Read and execute unchanged with stored checksum and documents. | No implicit rewrite or repin. |
| New authoring | v1 drafts remain accepted during transition. | Explicit v2 draft creation/translation only; no automatic published upgrade. |
| Old client | Existing v1 behavior. | Reject unless it advertises required v2 capabilities; no partial rendering. |
| Browser/native variant | Same v1 render document. | BPMS-022 selects a compatible named view; device hints never grant access. |
| `en`/`fa` locale | Existing API/registered-label behavior. | Resolve pinned messages with fallback and formatting profile above. |
| B2B data-only consumer | Validates canonical data schema without a renderer. | May submit canonical data under the same server validation/action policy; render capabilities are not required. |
| Unknown dialect/capability | Existing validator rejects unsupported render dialect. | Publication or presentation fails with a stable unsupported-dialect/capability issue. |

Only a v1 **draft** may be explicitly translated to v2. Translation copies the data schema,
maps the v1 render tree into `default`, and creates empty behavior and message documents only when
all v1 labels can be represented. Unsupported rules require author edits; translation reports
issues and does not publish. v1 published rows, history, process pins and checksums are untouched.

## Validation phases and limits

Each phase emits at most 32 stable `{pointer, code}` issues with pointers into the package or
`/data`; validation never returns secret values. BPMS-027/024/028/029/030 implement the relevant
checks. Existing v1 limits remain as implemented until a v2 validator is delivered.

1. Node: validate dialect, component contract, unique key, binding syntax/type, option bounds and
   local message placeholders. Use `node.invalid`, `binding.invalid`, `binding.type`, or
   `message.invalid` at the exact offending pointer.
2. Cross-field: compile bounded predicates and dependency graph; reject missing fields, cycles,
   incompatible writes and ambiguous source precedence as `behavior.dependency` or
   `behavior.cycle`. Evaluation cost is bounded by 10,000 operations per submission.
3. Whole package: validate schema, all views, locale completeness, exact dependency pins,
   recursion depth at most 16, at most 1,000 nodes across views, at most 100 component instances,
   and at most 256 repeat items per collection. Resolve snapshots and checksum atomically.
4. Host policy: check route/URL allowlists, capability requirements, data access and executable
   feature availability. Unsupported future behavior, view or subprocess features fail publication
   with `feature.unsupported` at their package pointer until their owning task lands.
5. Submission: validate canonical data and action profile server-side against the pinned version,
   item-key map and current authorization. Limit input JSON to 1 MiB and 32 issues; return
   `/data/...` pointers plus `item_key` context for repeat feedback. A visible/required UI flag
   never overrides canonical data and task-action policy.

## Representative package excerpt

This is a design example, not an accepted request to the current API. It shows two instances of
one pinned bilingual address component, nested invoice items, two views, actions and navigation.

```json
{
  "package_dialect": "bpms.form/2",
  "data_dialect": "https://json-schema.org/draft/2020-12/schema",
  "behavior_dialect": "bpms.behavior/1",
  "render_dialect": "bpms.render/2",
  "localization_dialect": "bpms.messages/1",
  "data_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
      "billing_address": {"$ref": "#/$defs/address"},
      "shipping_address": {"$ref": "#/$defs/address"},
      "invoice_items": {"type": "array", "items": {"type": "object", "properties": {
        "description": {"type": "string"}, "amount": {"type": "number"},
        "taxes": {"type": "array", "items": {"type": "object", "properties": {
          "code": {"type": "string"}, "amount": {"type": "number"}
        }}}
      }}}
    },
    "$defs": {"address": {"type": "object", "properties": {
      "city": {"type": "string"}, "street": {"type": "string"}
    }}}
  },
  "behavior_schema": {"dialect": "bpms.behavior/1", "rules": []},
  "render_views": {
    "default": {"dialect": "bpms.render/2", "root": {"node_key": "purchase", "component": "vertical", "children": [
      {"node_key": "billing", "instance_key": "billing", "component_ref": "address_editor@3", "value_pointer": "/billing_address"},
      {"node_key": "shipping", "instance_key": "shipping", "component_ref": "address_editor@3", "value_pointer": "/shipping_address"},
      {"node_key": "lines", "component": "repeater", "schema_pointer": "/properties/invoice_items", "value_pointer": "/invoice_items", "children": [
        {"node_key": "taxes", "component": "repeater", "schema_pointer": "/properties/invoice_items/items/properties/taxes", "item_pointer": "./taxes"}
      ]}
    ]}},
    "manager": {"dialect": "bpms.render/2", "root": {"node_key": "manager_review", "component": "vertical", "children": [
      {"node_key": "approve", "component": "action", "action_key": "approve"},
      {"node_key": "correct", "component": "action", "action_key": "request_correction"}
    ]}},
    "finance": {"dialect": "bpms.render/2", "root": {"node_key": "finance_review", "component": "vertical", "children": [
      {"node_key": "pay", "component": "action", "action_key": "confirm_payment"}
    ]}}
  },
  "localization": {"dialect": "bpms.messages/1", "default_locale": "en", "catalogs": {
    "en": {"address.city": "City", "address.street": "Street", "items.count": {"one": "{count} item", "other": "{count} items"}},
    "fa": {"address.city": "شهر", "address.street": "خیابان", "items.count": {"one": "{count} مورد", "other": "{count} مورد"}}
  }},
  "dependencies": [{"kind": "component", "key": "address_editor", "version": 3, "checksum": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}],
  "client_variants": [{"client_key": "web", "view": "default", "required_capabilities": ["bpms.render/2"],
    "navigation": {"success_url": "https://app.example.test/requests/{request_ref_id}"}}],
  "task_views": [{"task_key": "manager_approval", "view": "manager", "actions": ["approve", "request_correction"]},
    {"task_key": "finance_review", "view": "finance", "actions": ["confirm_payment"]}]
}
```

The `address_editor@3` authored component itself binds `./city` and `./street`; at publication
these resolve under each instance root and its pinned messages are namespaced by `billing` and
`shipping`. The example's `task_views` and `client_variants` are future owned extensions, not
current form fields. Subprocess references similarly pin a BPMS-031 published interface version,
never a mutable definition or arbitrary class name.


## BPMS-027 implementation boundary

The implemented localization slice is documented in [form localization](../api/form-localization.md).
It adds optional `FormDocuments.localization` to existing `bpms.render/1`; it does not activate the
full form/2 proposal. Catalog entries refine the illustrative plain-text proposal into typed
`{text, parameters, source_revision}` objects so parameter compatibility and source acknowledgement
are explicit. `text` retains the agreed string or one/other subset. Gregorian calendar support is
explicit; Persian digits and RTL are supported without implying Jalali conversion. Other package,
behavior, view and component contracts still require their own backlog tasks.
