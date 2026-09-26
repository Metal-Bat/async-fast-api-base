---
name: error-code-design
description: Design or implement this project's stable public API error codes, including business failures and safe PostgreSQL SQLSTATE mappings. Use for error catalogs, exception handlers, localization, or error response documentation; not for unrelated database or API work.
---

# Error code design

Read [references/catalog.md](references/catalog.md) for the proposed public allocation and PostgreSQL mapping. It is a target contract: inspect the live catalogs before editing, since current numbers still mix HTTP statuses and application codes.

## Public contract

- Keep the existing `ErrorResponse` shape: `success`, `request_id`, `error`, `code`, and `data`. The integer `code` identifies an application failure; the HTTP status expresses protocol semantics. Neither is derived from the other.
- Give every distinct public failure one globally unique, stable number. Never recycle a retired number. Message wording and translations may change without renumbering; different client action requires a new code.
- Keep safe English fallbacks and translations in the gettext catalogs. Preserve the JSON envelope and `snake_case` wire names.
- Choose the narrowest safe public failure. Use a generic code when a specific one would disclose resource existence, credentials, schema details, or internal state. Missing uploads and checksum mismatches share the public not-found code.
- Use the reserved business range only for domain invariants that need a distinct client decision. Record the invariant, HTTP status, retry behavior, and safe message when allocating a code; avoid one code per validation field or database constraint.
- Never expose exception text, SQL, parameters, constraint names, SQLSTATE, or raw provider messages to clients.

## PostgreSQL boundary

`utils.postgresql_errors` discovers SQLSTATE identities for diagnosis; it is not the public error catalog. Inspect `SQLAlchemyError.orig` or a direct driver exception for SQLSTATE, then apply the safe mapping in [references/catalog.md](references/catalog.md). Unknown or ambiguous failures receive a generic public result while SQLSTATE remains in server logs.

Retryable failures may be retried inside a bounded transaction policy. After retries are exhausted, return the agreed availability result. A broad `IntegrityError` alone does not prove a client conflict.

## Workflow in this repository

1. Inspect `utils/errors`, `utils/exception_handlers.py`, `utils/postgresql_errors.py`, `utils/presenter.py`, locale catalogs, and affected callers. Follow `AGENTS.md` graphify rules.
2. For a design request, propose exact numbers, HTTP statuses, public meanings, and compatibility impact without editing runtime code. For an implementation request, update catalogs, mappings, translations, docs, and tests together.
3. Test number uniqueness, response shape/status, localization, expected and unknown SQLSTATE through wrapped errors, and equal public results for missing versus corrupted uploads.
4. Run applicable project checks and update graphify after code changes.
