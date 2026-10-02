---
tags: [api]
---

# Reusable form library

Published data types and components are exact, immutable versions. Authors need `forms.manage` and must own a definition, be a superuser, or have an active direct/work-group use grant to reference it. Only owners and superusers can edit, publish, retire, or grant access. Search returns only visible definitions. A retired version remains readable for historical inspection, but new drafts and publication cannot resolve it.

## Authoring flow

1. `POST /form-data-types` or `POST /form-components` with `code`, `name`, and `is_active`.
2. `POST /form-data-type-versions` or `POST /form-component-versions` with `root_ref_id`, a positive `number`, and `document`. Draft documents can be replaced by `PUT /.../{ref_id}`.
3. `POST /...-versions/{ref_id}/publish` validates the complete exact-version dependency graph and stores its resolved snapshot, dependency manifest, and SHA-256 checksum. Published documents cannot be edited. `POST /...-versions/{ref_id}/retire` prevents new references.
4. Use `POST /.../search`, `POST /.../report`, `GET /.../{ref_id}`, and `POST /.../{ref_id}/history` for subject-oriented discovery and audit. Use `POST /form-components/{ref_id}/grants` or the equivalent data type endpoint to grant a user or active work group use access; `DELETE /.../{ref_id}/grants/{grant_ref_id}` revokes it.

Every `ref_id` includes a row revision. Send the current revision for edits and publication. Stale revisions return `VERSION_CONFLICT`; invalid documents return `VALIDATION_FAILED` with JSON-pointer issues. Envelopes and fields use snake_case.

A component document has `dialect: bpms.component/1`, an object `data_schema`, a `bpms.render/1` `render_schema`, optional exact `types` and `components`, `parameters_schema`, declared `parameter_targets`, localized `messages`, `overridable_messages`, `supported_actions`, and `required_capabilities`. Data type documents use `bpms.data-type/1`, `data_schema`, optional exact `uses`, and `help_messages`. Dependencies must already be published and accessible when the parent is published. Nested references resolve into the parent's immutable snapshot. Published references form an acyclic graph because drafts cannot be dependencies.

Library documents may also carry `category`, localized `help_messages`, and `sample_input`; component documents retain `required_capabilities`. Publication validates a sample against the resolved data schema. The [definition library API](definition-library.md) presents this metadata, permission-filtered usage, version comparison, templates, and bulk draft upgrade reports.

## Live references and copies

A form draft may provide `reuse_instances` alongside its canonical `data_schema` and `render_schema`. Each instance binds a published component to an object `schema_pointer` and an empty vertical `node_pointer`. The compiler replaces those placeholders, prefixes node keys, scopes, rule dependencies, and message keys by `instance_key`, and pins all transitive dependency checksums in `reuse_manifest`. The resolved document is stored in the form version. The authored source remains in `reuse_source` so draft edits and publication can revalidate access and retired dependencies. Publication hashes both resolved documents and the manifest. Existing forms have null reuse fields and keep their old checksum algorithm.

Example instance:

```json
{
  "instance_key": "billing",
  "component_ref": "<exact published revision ref>",
  "schema_pointer": "/properties/billing",
  "node_pointer": "/root/children/0",
  "parameters": {"heading": "Billing address"}
}
```

Parameter values must match the component's JSON Schema. Only declared render `label` and `options.placeholder` targets may change. Message overrides require declared message keys and locales. Repeated array schema paths may contain components; each instance has distinct node and message identities.

`POST /form-versions/{ref_id}/reuse-upgrade-preview` accepts `{"replacements":{"billing":"<new exact ref>"}}`. It resolves the proposed draft without writing, returns the new manifest and documents, and reports `reuse.incompatible_schema` when an instance's schema changes. Apply a compatible replacement by updating the draft explicitly. Published forms cannot be upgraded.

`POST /forms/copy-component` accepts `documents` and one `instance`; it returns inline `FormDocuments` with no `reuse_instances`. The copy is editable content and has no live library reference.

## Compatibility and operations

The additive migration creates component, data type, version, grant, and history tables, plus nullable form-version reuse columns. Run the single Alembic lineage through revision `9154a7157416`. The database rejects mutation of published library snapshots and enforces one active grant per resource/target. No new environment variables or dependencies are required. Renderer/editor UI remains owned by BPMS-017.
