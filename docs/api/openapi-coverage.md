---
tags: [api]
---

# OpenAPI coverage inventory

This is an inventory from the generated English OpenAPI 3.1 schema on
2026-10-02. [The machine-readable inventory](openapi-coverage.json) lists every operation with
its method, path, operation ID, route handler, summary, current description, security declaration,
parameters, request media types, response statuses and directly referenced schemas. It also lists
every field of every reachable component schema, including inline object, array and union fields.
References connect related components. The application-generated OpenAPI remains authoritative;
this inventory is a review aid, not a separate specification.

## Current coverage

| Surface | Total | Missing detailed descriptions |
| --- | ---: | ---: |
| Public operations | 302 | 147 |
| Reachable component schemas | 401 | 377 |
| Reachable schema fields | 2,078 | 1,901 |

The missing counts measure the presence of OpenAPI `description` text, not whether existing text
is correct or sufficient. In particular, summaries, titles and property names are not counted as
business explanations. The inventory records `null` where OpenAPI gives no description; it does
not manufacture one. All 302 operations have route-handler source anchors. The field list records
requiredness at its immediate object parent and the schema's declared type, format, default, enum
and reference where present. It does not infer lifecycle rules, permissions or nullability from a
field name. Those require route, DTO, service and test review before release documentation.

| Topic | Operations | Missing operation descriptions |
| --- | ---: | ---: |
| `auth` | 9 | 1 |
| `sessions` | 4 | 0 |
| `users` | 11 | 1 |
| `roles` | 7 | 0 |
| `permissions` | 9 | 0 |
| `work-groups` | 11 | 11 |
| `audit-events` | 3 | 0 |
| `history` | 1 | 0 |
| `clients` | 9 | 6 |
| `client-releases` | 7 | 5 |
| `designer` | 4 | 1 |
| `definition-library` | 10 | 0 |
| `forms` | 15 | 8 |
| `form-versions` | 10 | 6 |
| `form-components` | 9 | 6 |
| `form-component-versions` | 9 | 7 |
| `form-data-types` | 9 | 6 |
| `form-data-type-versions` | 9 | 7 |
| `step-types` | 4 | 0 |
| `workflows` | 10 | 9 |
| `workflow-versions` | 11 | 8 |
| `request-types` | 7 | 7 |
| `business-requests` | 17 | 13 |
| `processes` | 11 | 10 |
| `process-events` | 1 | 0 |
| `work-items` | 28 | 19 |
| `integration-connections` | 13 | 12 |
| `ai-agents` | 19 | 0 |
| `notifications` | 4 | 4 |
| `files` | 2 | 0 |
| `images` | 2 | 0 |
| `reports` | 5 | 0 |
| `task-definitions` | 5 | 0 |
| `task-schedules` | 7 | 0 |
| `task-executions` | 7 | 0 |
| `health` | 3 | 0 |

## Existing source material

- [Project setup and API URLs](../../README.md) and [BPMS architecture](../architecture/bpms.md)
  provide orientation. Domain contracts have separate guides for
  [forms](../architecture/forms.md), [dynamic fields](form-fields.md),
  [behavior](form-behavior.md), [localization](form-localization.md),
  [definition library](definition-library.md), [field inventory](field-inventory.md),
  [client variants](client-designs.md) and [task views](task-views.md).
- [The saved conformance scenario](../testing/form-workflow-conformance.md) is a reusable
  backend vector for purchase requests and approval calls. It is not browser or native-client
  verification.
- [The full workflow roadmap](../roadmap/full-workflow.md) assembles the source material and
  examples for Angular design review. The [core journey](../testing/full-workflow-regression.md) now has a disposable-database replay; the broader AI, parallel and delivery scenario still needs end-to-end validation.

## Remaining documentation work

The [user handbook](../guides/user-handbook.md), [frontend walkthrough](../guides/frontend-journey.md)
and [shared HTTP rules](../guides/frontend-contract.md) provide a current starting path. Curated
examples are contract-tested and generated references no longer fabricate business values for
unreviewed schemas. This does not eliminate the description gaps counted above or constitute
browser verification. See the [maintenance checks](../guides/documentation-maintenance.md).

Review every inventory row against its route, DTO, service, authorization rule and tests. Add
specific English and Farsi operation and field guidance, valid and invalid examples, public error
codes, lifecycle and version rules, dynamic document dialect references and response headers.
Then validate generated JSON/YAML, examples and representative responses; generate and type-check
a sample client; inspect authenticated Swagger interactions in a browser. Prepare the dated,
source-grounded design handoff after those checks. MEDIA-002's private-user-media disposition
contract is complete and is described in the [media download guide](private-media-downloads.md).

## Regeneration

`docs/tools/openapi_coverage.py` builds this inventory from `app.openapi()` and the effective
FastAPI route contexts. Generate the schema with a non-production test configuration; the
existing `tests/conftest.py` supplies synthetic values. For example:

```sh
PYTHONPATH=src:. uv run python - <<'PY'
import runpy
from pathlib import Path

runpy.run_path('tests/conftest.py')
from main import app
from docs.tools.openapi_coverage import write_inventory

write_inventory(app.openapi(), app, Path('docs/api/openapi-coverage.json'))
PY
```

Review changes to counts and descriptions as APIs evolve. A regenerated inventory alone does not
complete field documentation or validate runtime behavior.
