---
aliases: [Project documentation, BPMS docs]
tags: [index, bpms]
---

# Workflow backend documentation

Start with the route for your role below. These links work in ordinary Markdown readers and
Obsidian. The [project overview](project-overview.md) explains vocabulary and ownership;
the [repository README](../README.md) covers setup and commands.

## Open in Obsidian

1. In Obsidian's vault switcher, choose **Open folder as vault**.
2. Select the repository root, `fast-api-sample`, so links to `README.md` and source files stay
   inside the same vault.
3. Open `docs/Home.md` in the file explorer or find it with the Quick Switcher (`Ctrl+O`).
4. In **Settings → Files and links**, turn **Use Wikilinks** off and choose **Relative path to file**
   for new links. This preserves the standard Markdown used by the documentation checks.

Reading view displays the tables and Mermaid diagrams. No community plugin is required. Under
**Files and links → Excluded files**, exclude `graphify-out/` and `raw/` if generated or downloaded
notes crowd search and graph results. The `.obsidian/` settings and `.trash/` folders remain local.
Source-code links may open through an external editor; Obsidian is the documentation reader.

Opening only `docs/` also works for the guides, but links to files outside that folder are outside
that vault. See the official [vault instructions](https://obsidian.md/help/vault) and
[link settings](https://obsidian.md/help/settings).

## Choose your starting point

| I need to… | Start here | Then read |
| --- | --- | --- |
| Use requests, review work or make corrections | [User handbook](guides/user-handbook.md) | Its troubleshooting and administrator sections |
| Build a frontend | [Login-to-completion walkthrough](guides/frontend-journey.md) | [HTTP rules](guides/frontend-contract.md), [TypeScript client](examples/frontend-client.ts), [reviewed examples](examples/frontend-journey.json) |
| Find exact response fields | [Response reference](reference/responses/index.md) | Live Swagger/OpenAPI; [coverage limits](api/openapi-coverage.md) |
| Develop backend features | [Module overview](project-overview.md) | Source map below, [step extensions](guides/step-extensions.md), [core regression](testing/full-workflow-regression.md) |
| Test a release | [Core workflow regression](testing/full-workflow-regression.md) | [Conformance fixtures](testing/form-workflow-conformance.md), [documentation checks](guides/documentation-maintenance.md) |
| Deploy or investigate failures | [README](../README.md) | [Safeguards](operations/bpms-safeguards.md), [observability](operations/bpms-observability.md), [dependencies](operations/dependencies.md) |

## Know what kind of document you are reading

- **Implemented contract:** API guides and the new user/frontend guides explain current behavior.
  Generated OpenAPI is authoritative for wire fields; services and tests establish business rules.
- **Reviewed synthetic example:** checked payload shape with invented non-secret identities.
  It does not prove that a browser or a live HTTP journey ran. Replace synthetic refs with real ones.
- **Historical design:** [BPMS-001](architecture/bpms.md) records the original blueprint and estimates;
  it is not the current schema or migration instructions.
- **Proposed design:** [form package v2](architecture/form-package-v2.md) is not an accepted current
  request payload. Continue using the implemented FormDocuments/bpms.render/1 contract.
- **Roadmap:** [full workflow target](roadmap/full-workflow.md) includes AI, parallel and delivery
  stages that are not all exercised in the single core regression.

Documentation is reviewed against a repository state, not a guarantee about every deployed
environment. Check feature configuration and the live API when integrating another release.

## Design a complete case

- [Full workflow roadmap](roadmap/full-workflow.md) — staged purchase approval with AI preparation and required human approval.
- [Saved purchase-request scenario](testing/form-workflow-conformance.md) — canonical data, localization, reuse, corrections and backend replay.
- [Full workflow regression](testing/full-workflow-regression.md) — one migrated database journey and the extension rule for future workflow features.
- [BPMS architecture](architecture/bpms.md) and [Form architecture](architecture/forms.md) — domain rules and ownership.
- [Trusted step extensions](guides/step-extensions.md) — registered handler contracts.

## API and client contracts

- [Response DTO reference](reference/responses/index.md) — generated field tables and structural examples for every successful response schema, grouped by topic.
- [Response scenarios](api/response-scenarios.md) — validated examples for a claimed approval, waiting process, parallel work, AI lookup approval and selector page.
- [OpenAPI coverage inventory](api/openapi-coverage.md) — route and schema inventory; use generated Swagger for the current wire contract.
- [Form fields and dynamic options](api/form-fields.md), [behavior](api/form-behavior.md), [localization](api/form-localization.md), [client variants](api/client-designs.md).
- [Authoring selectors](api/authoring-selectors.md), [definition library](api/definition-library.md), [subprocess calls](api/subprocess-authoring.md), [human task views](api/task-views.md).
- [Private media downloads](api/private-media-downloads.md), [request client headers](api/request-user-agent.md), [Date diagnostics](api/client-date-diagnostics.md).

## Operations

- [Dependency and production install policy](operations/dependencies.md).
- [Telemetry and diagnostics](operations/bpms-observability.md).
- [Recovery and deployment safeguards](operations/bpms-safeguards.md).
- [Governed AI](architecture/ai-governance.md).

## Source map

| Area | Source |
| --- | --- |
| Identity and work groups | `src/apps/users`, `src/apps/work_groups` |
| Forms, definitions and designer | `src/apps/forms`, `src/apps/workflows`, `src/apps/designer`, `src/apps/step_types` |
| Requests and process execution | `src/apps/requests`, `src/apps/processes`, `src/apps/work_items` |
| AI, integrations and notifications | `src/apps/ai`, `src/apps/integrations`, `src/apps/notifications` |
| Private media and reports | `src/apps/media`, `src/apps/reporting` |
| Shared services and migrations | `src/core`, `src/utils`, `src/migrations` |
