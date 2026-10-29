# Binding object fields v1

Owner: APP-BE-019.UX03; consumers APP-FE-023/024. Date: 2026-10-28.
Implementation and scoped local acceptance are verified under the exact D07 SDK exception policy. The final current-source receipt governs documentation closure; this contract does not claim deployment or user acceptance.

## Representation and compatibility

GraphBinding gains optional `target_projection: {dialect: "bpms.binding.object/1", path: "/customer/name"}`.
Absent/null means the existing whole-port binding and is omitted during canonical serialization, preserving old published payloads and checksums. No source kind changes. Public fixed models remain BaseDTO/snake_case. Private storage uses nullable TARGET_PATH, TARGET_PROJECTION_VERSION and TARGET_SCHEMA facts with an atomic all-null-or-supported-complete projection constraint; explicit mappings join them into the public projection. Version 1 is the only supported version.

The existing SCALAR input must be an object port. For a generic object port, projected bindings carry an explicit author-declared object shape in the existing target_schema field; it is persisted only for projected bindings. A port with declared properties retains its exact pinned schema. Every binding for one projected port must use the same root shape. This authoring type declaration never grants access or weakens the final registered port/operation validation. A nonempty RFC 6901 path (maximum 1024 UTF-8 bytes, 12 segments) chooses declared object properties. Arrays may be assigned as whole leaf values; v1 does not manufacture array containers or dynamic additional-property names. Reserved prototype keys are rejected. LIST ports retain existing flattening/ordering semantics and do not accept object-field projections.

## Composition rules

All bindings for one projected port use projections and contiguous unique ordinals starting at zero. A whole-port binding cannot mix with field bindings. Duplicate paths and ancestor/descendant overlaps are errors regardless of order; there is no last-write-wins policy. Each source is checked against its destination leaf schema. Required target structure must be covered. REQUEST/CONTEXT declarations remain authoring types, never data or authorization; projected new bindings require enough declared schema to validate their selected source. Prior step outputs retain pinned port metadata and existing dominance checks.

Runtime resolves the existing authorized sources through the existing engine, then places each value into a fresh object. Explicit null remains null and must satisfy the destination schema. Missing source data is an error, never implicit null/default/omission. Arrays stay arrays. Ordinals determine deterministic construction/display order and never override a conflict. Validate the complete object against the persisted target declaration, then retain the existing registered input validation before handler invocation. New object assembly is bounded to 64 fields and 256 KiB. No existing published type/version or operation replay body changes.

## Authoring preview

A current authorized workflow version supplies the ownership/type context for a bounded candidate-graph preview. Only caller-entered samples and constants visible in that candidate are used. No saved submission, execution output, credential or runtime context is fetched as a sample. Each sample names a selected binding ordinal; the UI supplies typed controls, never required raw JSON or copied references. Preview uses the same projection operation as runtime, validates the complete target input, and returns bounded structural paths/types and issue codes without values. Candidate identity and explicit non-execution flags fence stale responses. Missing samples remain distinguishable from explicit null, zero, false and empty collections.

Expressions retain the existing declared variable environment. Request values require an explicit REQUEST binding/source declaration in the workflow; v1 adds no implicit request/global lookup or ambient private-data access. An undeclared request expression remains a compile error with a purposeful bind-first explanation.

## Rollout and verification

Use a new forward revision after 0004; preserve all applied revisions, source declarations, published payloads and active pins. Null old rows require no backfill. Protected effect payloads retain their exact whole approved binding; compose data upstream of human approval rather than splice a protected payload afterward. Partial downgrade refuses populated projection facts; use reviewed forward repair/backup for an in-use installation. Test fresh/populated upgrade and the exact old canonical checksum, new composition execution, typed nested/null/array/conflict cases, current authorization and redaction. Then regenerate the single producer manifest and all reviewed consumer slices, run actual paired/browser scenarios and both complete final gates on stable source. Existing D07 exceptions are not strict or deployed acceptance.
