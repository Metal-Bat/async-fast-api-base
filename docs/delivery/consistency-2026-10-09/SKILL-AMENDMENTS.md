# Scoped instruction amendments — review and merge, never replace blindly

This file proposes documentation/rule repairs. It does not change HTTP behavior, code, approvals or migrations. Merge relevant language into the current skills/AGENTS only after confirming the same implemented contracts. Preserve all other rules and existing skill content.

## Backend CRUD skill: preserve actual compatibility exceptions

Target: `.agents/skills/crud-api-contract/SKILL.md`.

Replace the absolute interpretation of “no PATCH update routes” with a scoped rule:

> Conventional mutable resources use the project's PUT-by-ref update contract. Preserve the already implemented GET/PATCH `/api/v1/me/preferences` and `/api/v1/me/profile` singleton self-service contracts as explicit compatibility exceptions. Their omitted/null/partial-update semantics remain authoritative. Do not convert them to PUT, change payload shape or permit general new PATCH resource routes as a consistency cleanup. Any additional exception needs its own recorded contract decision and tests.

Clarify protocol/app error wording without silently changing any existing code:

> HTTP status and public application error number are separate, tested fields. Keep the current `utils.errors` catalog and `utils.presenter` envelope semantics. Do not replace established application codes with HTTP numbers merely to conform prose. Record and review a specific incompatibility before changing the public wire contract.

## Backend Swagger / DTO verification

Target: `.agents/skills/swagger-contracts/SKILL.md` and relevant existing DTO contract tests.

Add:

> Verify route-reachable fixed JSON models recursively, including computed output fields and serialization-mode schemas. All typed public nested objects must satisfy the BaseDTO contract. Distinguish fixed DTO fields from explicitly bounded dynamic document keys. Validate examples and effective generated OpenAPI after shared localization/header/tag enrichment. Entity metadata does not justify exposing private storage fields. Document observed exceptions and compatibility, not proposed behavior as implemented.

## Both repositories: current decisions and clear completion labels

Targets: existing AGENTS delivery section and product-delivery/smart-backlog rules where their wording disagrees.

Add or replace obsolete text with:

> Reconcile the current backend `docs/delivery/approved-decisions.json` and `docs/changes/DB-002.md` before schema or verification changes. DB-002 supersedes old migration-file policy; it does not authorize shared resets, blind stamping or repeated edits to applied revisions. D07 records two exact accepted SDK warnings; a result under that policy stays VERIFIED_WITH_EXCEPTION, never strict exception-free. New exceptions require approval. A local pass still does not prove paired/browser/demo/deployed/user acceptance.

Keep the strict requirement to run complete final `mise run check`, preserve exit codes, retain failure evidence and run task-required scenarios. Do not let an accepted backend SDK exception excuse frontend warnings, required skipped tests, hidden output or fixture-only integration.

## Frontend shared ownership / design consistency

Targets: AGENTS and current UI/architecture guidance.

Add:

> Standard business UI is PrimeNG-first with semantic tokens and explicit tested exceptions. Reuse existing shared controls; a cross-feature import must have a documented public seam and no domain/presentation inversion. Do not duplicate Administration's schema controls into Studio or use them to replace domain-specific configuration. One frozen producer manifest governs the main transport and reviewed metadata slices. Backend persisted defaults win for explicit reset; neutral actor-cleanup defaults are separate.

## Installation ordering

Merge the repository-specific root addendum supplied in this pack. It points to this file and the new contract-consistency skill. Do not overwrite root AGENTS.md or an existing skill. If a newer decision conflicts, record the exact conflict and preserve working behavior while resolving it. Do not infer a business approval from a rule-only amendment.
