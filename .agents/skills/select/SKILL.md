---
name: select
description: Create or update this project's dropdown/select services, key/value option responses, searchable resource selectors, and localized enum choices. Use when adding a select endpoint or changing its filtering, localization, or pagination contract; not for SQL SELECT statements or AI model selection.
---

# Select services

A select lets a caller choose from authorized options matching their request. Reuse the owning
application service and existing selector before creating a new endpoint or abstraction.

## Wire contract

Use `utils.select.SelectOption` (a `BaseDTO`) for each item:

```json
[{"key": "COMPLETED", "value": "Completed"}]
```

- `key` is the stable value submitted by the client: an opaque `ref_id` for database entities or
  a registered machine code for enums/catalogs. Never translate it or expose raw database IDs.
- `value` is the display label. Translate registered enum labels using `core.i18n` at request time;
  preserve user-entered resource names. Respect the existing `Accept-Language` context and fallback.
- Do not use `title`, `label`, or serialization aliases for select item fields. Rich designer catalogs
  and completion records are separate contracts and may retain their metadata/title fields.

## Response formats

Support the format the user requests. When asked for both, expose both explicitly; do not force the
frontend into one format. Existing selectors use `response_format=page|items`:

- `page` (default): the shared `PageResponse` envelope, with `result.items`, page, size, total and
  total_pages. Use `utils.presenter.select_response` for existing dual-format endpoints.
- `items`: the plain top-level JSON array shown above, with `[]` for no matches. It contains the
  same bounded page of authorized results; it is not an unbounded export. Clients needing totals
  should request `page`.

Keep the parameter and OpenAPI response union explicit. Do not add a second query/authorization
implementation for the alternate format. Preserve an existing endpoint's behavior unless the user
requests changing it; document a format or field migration that breaks existing clients.

## Request and application behavior

- Use the owning resource's validated search/filter request. Simple catalogs use `SelectQuery`;
  designer selectors use `DesignerQuery`; administrative users/groups use their existing queries.
- Search and authorize before pagination. Enforce size limits, stable ordering with a unique
  tiebreaker, and deterministic empty/out-of-range pages in both response formats.
- Code enum search matches stable keys and translated labels. Build labels per request, never at
  module import time. Register gettext messages and update/compile English and Farsi catalogs.
- Allowlist enum/resource selector kinds; never accept arbitrary table names, Python imports,
  field expressions, or URLs. Reject unknown kinds and unsupported filters through DTO validation.
- Keep existing visibility, ownership, group, permission, deleted/inactive and context checks.
  Resolve any selected key again when executing a command; appearing in a select grants no authority.
- Place query/business decisions in the owning application/data layer; handlers validate HTTP input
  and present the result. Avoid leaking ORM objects or private fields into option responses.

## Existing sources

- `src/utils/select.py`: option and query contracts, runtime label translation helper.
- `src/utils/presenter.py`: plain-array/paginated presentation.
- `src/apps/designer/application/service.py`: resource and enum selectors.
- `src/apps/designer/presentation/routes.py`: `POST /designer/selectors/{kind}`.
- `src/apps/work_groups/presentation/routes.py`: administrative user/group selects.
- `src/apps/tasks/application/service.py`: registered task/queue choices.
- `src/core/i18n.py` and `src/locales/`: locale negotiation and gettext catalogs.

## Verification

Add behavior tests before changing a select: exact key/value serialization, request search,
no matches, limits/pagination, stable keys across English/Farsi, fallback, authorization and
private/deleted records. When both formats are requested, prove they contain identical options
and document both in OpenAPI. Reuse existing integration tests for database visibility. Record
consumer-visible breaking changes through the project's backlog/change-journal workflow.
