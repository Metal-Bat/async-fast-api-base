---
name: swagger-contracts
description: Maintain detailed project-specific Swagger/OpenAPI documentation when adding or changing HTTP endpoints, public DTOs, or API documentation. Covers complex BPMS lifecycle, nested JSON contracts, localization, streaming headers, and generated-schema verification.
---

# Detailed Swagger contracts

Use the existing `api-docs-writer` skill for general documentation authoring. This skill adds
repository requirements; it does not replace the current API contract with a new envelope or spec.

## Source of truth

Read the affected route, DTO, service, authorization and tests before documenting behavior.
Reuse `src/utils/base_schema.py`, `presenter.py`, `errors/`, `localized_docs.py`, and
`src/core/base_dto.py`. Follow `.agents/skills/crud-api-contract/SKILL.md` for resource routes
and `.agents/skills/select/SKILL.md` for selectors. Generate OpenAPI from FastAPI; do not maintain
a competing handwritten schema. Proposed backlog behavior must not appear as already supported.

## Required detail for changed operations

- Give a concrete summary and explain business purpose, side effects, valid lifecycle states,
  actor permissions and resource eligibility. Separate authentication from authorization,
  UI visibility and client presentation hints.
- Describe each path/query/header/body input: meaning, required versus nullable, default,
  bounds, units, canonical formats, and dependent fields. Explain revision-bearing `ref_id`,
  stale writes, exact version pins and idempotency/replay behavior where applicable.
- Describe nested DTO fields and discriminated variants. For bounded JSON documents, document
  dialect, supported subset, limits, references, compatibility and validation/metadata endpoints;
  a bare `dict[str, Any]` with no explanation or example is insufficient.
- Include realistic valid request/response examples and relevant invalid/conflict examples.
  Show actual snake_case payloads, success/pagination envelopes, key/value selectors,
  page/items alternatives, public error codes and pointer-based issues. Use synthetic data.
- Declare actual success/error statuses, content types and response models. Binary streams
  describe binary output rather than a JSON envelope. Document optional request header controls,
  response headers, defaults, rejection rules and CORS exposure where applicable.
- Explain missing/null/default behavior, locale fallback, canonical values versus translated
  labels, and action-specific validation when relevant. Add English/Farsi descriptions through
  existing localization without translating keys, paths, enums or operation IDs.
- Keep subject tags/order consistent with localized Swagger. Reuse shared descriptions while
  explaining each operation's own permissions and failure conditions.

## Verification

Inspect generated JSON/YAML OpenAPI and localized variants. Verify stable operation IDs, resolved
references, security metadata, parameter locations, response schemas/headers, discriminator
variants and examples against DTO validation and representative route behavior. Cover meaningful
contract regressions in existing API/OpenAPI tests; avoid prose-exact snapshot tests. Check complex
operations in Swagger UI when changing its rendering or interaction. Never claim browser testing
or runtime behavior from schema inspection alone.

Documentation improvements must not silently alter runtime behavior. Record discovered behavior
bugs separately through smart-backlog. Existing-surface coverage is tracked by DOCS-001.
