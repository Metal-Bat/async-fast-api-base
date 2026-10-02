---
tags: [architecture]
---

# Client predicates (BPMS-023)

Forms and workflows use the existing bounded expression language and BPMS-022 client release
ordering. Presentation conditions select a design. Workflow conditions select a control-flow edge.
Application authorization and human-task eligibility remain separate checks.

## Client namespace

`client_expression_schema()` and `ClientContext.expression_values()` define the shared contract:

| Path | Type | Legacy/missing value |
| --- | --- | --- |
| `client.client_key`, `client.kind`, `client.platform` | nullable string | null |
| `client.release` | nullable string with `client-release` format | null |
| `client.api_version` | nullable string | null |
| `client.renderer_capabilities` | array of strings | empty array |
| `client.trusted` | boolean | false |

No credential, session identifier or ORM object enters this namespace. Designer completion exposes
these paths under `source: client`, with nullability and cardinality. The function catalog includes
`version_in_range`. Other workflow predicates retain declared request/process/reachable-output
namespaces. Form variant conditions expose only client values: mutable form data does not silently
change a pinned presentation. Data-dependent field behavior belongs to BPMS-024/029.

## Release ordering

```text
client.kind == "DESKTOP" and version_in_range(client.release, "2.10", null)
client.kind == "ANDROID"
client.trusted and contains(client.renderer_capabilities, "tables")
client.release is null
```

`version_in_range(release, minimum, maximum_exclusive)` requires a declared release field and
literal version bounds or `null`. At least one bound is required. Minimum is inclusive; maximum
is exclusive. Invalid or descending bounds fail authoring with a source location.

BPMS-022's comparator is reused: `2.10` equals `2.10.0`, sorts above `2.9`, and sorts above
`2.10.0-rc.1`. Build metadata does not change ordering. Missing release returns false; malformed
non-null runtime release raises an evaluation error. Use `is null` to test absence. Ordinary
string/identity comparisons, string transformations and concatenation cannot compare release
values. Existing ordinary string semantics are preserved. Capability membership checks use the
array's declared element type.

## Form if/elif/else selection

`FormDesignVariantDTO.condition` is optional, nullable and bounded to 1,024 characters. It is ANDed
with the variant's client/kind/release targets. A condition-only variant is supported. Variants
are ordered by descending priority, and evaluation stops at the first match. The existing shared
render/page document is the single final else. Conditional variants cannot use the reserved
`shared` key; duplicate keys and overlapping equal-priority targets are rejected. Conditions are
not assumed mutually exclusive when checking ambiguous priorities.

No match returns shared design. Legacy clients receive shared unless a condition explicitly
matches their null identity. An evaluation error or missing required renderer capability stops
selection; it does not fall through to a different design. Every variant is validated at
publication, even when a preview would select an earlier branch.

`apps.forms.application.designs` owns selection and its expression calls. This module was moved
from `apps.forms.domain.variants` so domain DTOs do not depend on an application service.
Form preview and request/human-work consumers all use the same resolver.

## Workflow if/elif/else selection

Existing transitions use descending priority within each source/outcome. The first matching
non-default wins in ordinary routing; an explicit parallel split retains its multi-edge behavior.
At most one default exists. In a group using client predicates, the default must be unconditional
and have lower priority than every non-default branch. Duplicate priorities and defaults are
publication errors. Legacy graphs without client predicates retain their previous semantics.

No eligible transition follows the existing `transition.not_found` failure path. Evaluation errors
propagate through the existing transaction boundary and never authorize another branch. DECISION
expressions use the same client schema, including expressions such as:

```text
choose(version_in_range(client.release, "2.10", null), "modern", "legacy")
```

No new handler version or workflow engine is introduced. Existing joins, loops, output schemas,
work-item checks and terminal-state protection remain in force.

## Origin, interaction and trust

Workers rebuild values from `BusinessRequestEntity.origin_client_context`. They do not read current
HTTP headers or mutable client release records. A fresh worker session or duplicate callback
therefore evaluates the same origin. A completed transition is retained, not reevaluated.
Presentation uses the explicit form-interaction context. BPMS-022's authorized cross-client draft
resume may change that presentation while preserving workflow origin and historical submissions.

Session-bound registration supplies context. Public registrations do not prove device identity;
`trusted` remains false. Self-reported headers cannot replace this context or grant access. Use
existing client-target authorization for protected process entry. A predicate cannot replace it.
The same-client check now compares absent release IDs as null, fixing rejection of an interaction
whose registered client has no release.

## Pins, audit and compatibility

Variant conditions persist in the existing immutable variants JSON. Absent/null conditions are
omitted from canonical checksum input, preserving historical form checksums. Published versions
are never rewritten. Workflow graph checksums already include transition conditions.

Process transition records retain the selected edge; `transition.taken` includes only branch
metadata and `predicate_contract: bpms.predicates/1`. Form interactions retain form/version,
variant key and design revision. Predicate input values are not copied into generic events.
No evaluation-result cache is introduced, so users, locales and contexts cannot share a cached
selection. Localization changes descriptions, not canonical keys or predicate semantics.

Form validation issues now optionally include one-based `line` and zero-based `column`; non-expression
issues return null for those fields. Existing envelopes, status codes and security remain unchanged.
Swagger descriptions are available in English and Farsi. No database migration, dependency or
runtime setting is required; deploy API and workers together.

## Bounds and verification

The existing limits remain: 1,024 source characters, 128 AST nodes, depth 16, 512 evaluation work
units, bounded collections and at most 32 form variants. There is no network access, user-defined
callable or script evaluation. Compilation validates all branches; runtime short-circuits.

Tests cover numeric/prerelease/build versions, null/invalid values, forbidden comparison bypasses,
capability types, duplicate/default rules, first match, shared fallback, evaluation errors,
historical checksums, localized OpenAPI and forged headers. PostgreSQL tests cover immutable form
conditions, authorized completion, saved-origin routing after a durable wait and duplicate callbacks.
See the cited route, form and process tests for current behavior and validation.
