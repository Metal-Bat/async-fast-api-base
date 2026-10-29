# Local workflow seeds and optional business demonstrations

Run from the project root after configuring `.envs/.backend` and applying the current
migrations (`0005_binding_object_fields`). The database must already be reachable from the host:

```sh
mise run demo-seed
```

`demo-prepare` is an alias. This runs `uv run python -m scripts.demo_seed` locally,
inserts records and exits. There is no Compose seed service or seed image. The script
loads `.envs/.backend`; the Compose hostname `postgres` maps to `127.0.0.1` using the
configured PostgreSQL port. Explicit host environment variables take precedence.
The default insert uses PostgreSQL only: it does not upload files, start workers,
create reports or generate thousands of business cases. It never migrates or resets data.

## What the default inserts and why

Five deployed handlers provide typed executable ports: `ARITHMETIC`, `NUMBER_COMPARE`,
`BOOLEAN_LOGIC`, `IF_ELSE`, `SELECT_VALUE`. The local insert reconciles and publishes
their version-one contracts; API startup reconciliation alone leaves new extensions as
drafts. Existing START, FINISH, TRANSFORM, TIMER, EVENT_WAIT, HUMAN_TASK, DECISION,
SUBPROCESS and parallel/join policies retain their existing runtime contracts.

The following sixteen examples are ordinary published reusable subprocesses. Each has
named input ports, a `result` output, sample inputs and English/Persian purpose text.
Use them through the authorized definition library or the designer subprocess catalog.
Each has one useful published version; the lightweight insert creates no artificial
draft/retired copies. For if/else, connect both `true` and `false` outcomes in the caller,
as well as the normal subprocess `failure` path.

| Seed key | Why it exists |
| --- | --- |
| `math.add` | Combine quantities or scores. |
| `math.subtract` | Calculate a remaining quantity or difference. |
| `math.multiply` | Apply a rate or weight to a quantity. |
| `math.divide` | Calculate a ratio; reject a zero divisor. |
| `math.remainder` | Group batches or assign cyclic positions. |
| `compare.eq` | Check numeric equality. |
| `compare.ne` | Detect mismatched numeric values. |
| `compare.lt` | Enforce a strict upper limit. |
| `compare.lte` | Enforce an inclusive upper limit. |
| `compare.gt` | Detect a value exceeding a threshold. |
| `compare.gte` | Enforce a minimum quantity or score. |
| `logic.and` | Require both conditions. |
| `logic.or` | Accept either condition. |
| `logic.not` | Invert a condition for an exclusion rule. |
| `control.if_else` | Choose the execution path from a boolean, with both branches connected. |
| `data.select` | Choose a supplied value without branching execution. |

Arithmetic uses finite JSON numbers and ordinary floating-point operations. It rejects
booleans, numeric strings, NaN, infinity and zero divisors. It is for quantities and
scores, not exact currency accounting. `NUMBER_COMPARE` produces a boolean;
`IF_ELSE` consumes that boolean and routes execution. `SELECT_VALUE` instead selects
one of two supplied JSON values; both are required and either may be null. AND/OR
require two boolean inputs; NOT uses only the left input.

| Reusable data type | Why it exists |
| --- | --- |
| `text` | Carry labels, identifiers and text between steps. |
| `integer` | Whole item counts and batch counters. |
| `number` | Fractional quantities, ratios and numeric results. |
| `boolean` | Input/output conditions for logic and branching. |
| `date` | Calendar dates without a time or timezone. |
| `date_time` | Timestamp values for deadlines and events. |
| `number_list` | Bounded collections of numeric measurements or scores. |
| `record` | Keep a label and numeric result together. |

| Reusable input component | Why it exists |
| --- | --- |
| `numeric_operands` | Enter left/right numbers for calculations and comparisons. |
| `boolean_conditions` | Enter left/right conditions for boolean logic. |
| `conditional_labels` | Enter a condition and two alternative text labels. |

All new types and components include schema-valid samples and English/Persian help.
Definitions use the installation namespace `wf.<installation>.`; existing business
examples and published pins remain intact. Three ordinary accounts (designer,
requester, reviewer) are inserted once when absent. Log in as the printed designer
account to use owned types/components; sharing with another actor uses existing grants.
Reruns add missing entries without duplicating them. Changed/deleted/retired seed
definitions are refused rather than overwritten. Do not delete data before rerunning.
Keep `.demo-seed` when rerunning: its private manifest retains installation ownership
and the original credentials. Deleting it does not authorize taking over existing users.

`scripts/demo/workflow_library.py` is the editable source for example inputs, expected
results, schemas and purposes. Execution classes are in
`src/apps/step_types/extensions/primitives.py`. There is no arbitrary code or function
name execution through seed data.

## Executable business review examples

```sh
mise run real-process-seed
mise run demo-seed -- --inspect --with-real-processes
```

This additive v3 profile publishes thirteen domain workflows and a Legal review
child. By default each receives one draft and one genuinely submitted waiting
request. Reviewers must perform their own tasks; installation never manufactures
approval, inspection findings, receipt files or provider outcomes. Finance inputs use
decimal strings and explicit currency; seven nonfinancial processes require no budget.
Invoice arrival correlates by invoice number. Equipment is a reservation request
review, not an automatic booking system. Contract amendment after Legal review uses
a new request under the current supported subprocess lifecycle.

Reuse the existing private installation directory and credentials. `--process-cases-per-type`
accepts 1–10. Client key/version appear in inspection output, without credentials or
submitted payloads. Reruns preserve existing cases, published pins and editable work;
conflicting seed definitions are refused. Legacy v2 lifecycle cases remain unchanged.
The audit and scenario responsibilities are in `docs/changes/APP-BE-005.3.md`.
Run `mise run real-process-test` for actual disposable database/worker acceptance.

Requests retain their originating client release. For the frontend development
boundary, use the public client key and version printed by inspection:

```sh
BOUNDARY_CLIENT_MODE=public BOUNDARY_CLIENT_KEY=<inspected-client-key> BOUNDARY_CLIENT_RELEASE=1.0.0 pnpm start
```

Run that command in the frontend checkout after stopping its previous development
server/boundary. Public clients have no client secret. Log in again so the session
uses that registered release. Do not remove origin-client checks to open old cases;
legacy v2 cases retain their own originating release. Production keeps its existing
confidential boundary requirements.

## Optional larger business dataset

With `--with-demo-cases`, the default case count creates **252 cases for each of thirteen business workflows**, plus five
baseline cases and an administrative cancellation: **3,282 requests and 102 ordinary
users** on a fresh installation. The main catalog has fourteen scenario slots × six
client kinds × three languages. All twenty supported form controls remain represented,
with reusable components, rich authoring versions, calendars, notices, attachments,
reports, support incidents and disabled integration/AI/schedule configurations.

```sh
mise run demo-seed -- --with-demo-cases --cases-per-type 504
mise run demo-seed -- --inspect
```

The allowed range is 14–2000 per workflow. Counts below 252 omit later client/language
combinations. Increasing the count adds cases; reducing it preserves existing cases.
The full seed performs real workflow transitions and can take several minutes. It needs
the application's existing cache, broker and S3 endpoints configured with host-reachable
addresses and credentials; the script does not start those services. Faker remains a
development dependency and is omitted from the production runtime image.

The command prints the path to `.demo-seed/<target>/credentials.json`. This ignored
private file contains randomly generated initial passwords and all usernames. Newly added accounts append to the file without changing earlier entries. Its
installation manifest binds repeat runs to the same target and stable resource IDs.
Keep these files: removing them does not remove the database records, and a subsequent
installation refuses conflicting usernames. Passwords never appear in normal command
output. Later password, profile, preference and case edits remain operator-owned.

Use `demo.requester` and `demo.reviewer` for the original purchase/service examples;
`demo.designer` for the complete Studio catalog; `demo.admin` for administration,
reports and support; and department accounts such as `demo.finance.requester`,
`demo.finance.reviewer`, `demo.technology.requester` and `demo.technology.reviewer`
for their business cases. Ordinary account permissions and task candidacy apply.

## Inspectable coverage

| Implemented area | Seeded data and actions |
| --- | --- |
| People and permissions | Realistic names, six installed role templates, ordinary accounts, localized departments and memberships. Existing role edits are preserved. |
| Business forms | Procurement, leave, expenses, IT service, onboarding, access, travel, contracts, incidents, equipment, invoices, quality and project rollout, with domain-specific fields and realistic generated values. |
| All twenty render components | The project rollout dossier contains action, attachment collection, boolean, calculated, choice, date, datetime, display, grid, group, horizontal, integer, media, number, repeater, table, text, textarea, user and vertical controls. It includes decimal presentation, nested objects, dependent user/group selectors and English/Persian/Arabic catalogs. |
| Client presentation | Six client kinds, current and disabled successor releases, and explicit WEB/ANDROID/IOS/DESKTOP/B2B/SDK form variants in every catalog form. Shared design remains the fallback for legacy-origin requests. |
| Reusable form authoring | Contact, address and budget components/data types; published, draft and retired versions; a published two-party form with two immutable component instances. |
| Designer | Executable published graphs plus editable draft workspaces, saved step positions and viewports, promoted/retired examples and publication checksums. |
| Workflow control | Serial approvals, parallel split/join, priority routing, correction loops, transforms, timed waits, event subscriptions and pinned subprocesses. Completed child calls settle through the subprocess owner; selected invoices consume real seed events. |
| Requests and tasks | Draft/running/completed/cancelled/failed requests; open, claimed, started, completed, rejected, returned and cancelled work; actual comments, saves, forwarding, correction feedback and activity history. Rejection is a work-item outcome, not an invented request status. |
| Process states | Waiting, paused, cancelled, completed and failed instances. Explicit `demo.wait.delivery_failed` examples use the failure owner; no-effect compensation exercises the existing compensation lifecycle without inventing external receipts. |
| Personal workspace | English/Persian/Arabic, Latin/Persian/Arabic numbering, timezone, palette/density/landing/page-size preferences; saved views, a favorite, help state, pinned/watched/archived/read work and read/unread notifications. |
| Calendar and reminders | Past/current/future timed and all-day events, future reminders and ordinary pending outbox work. Dates are anchored to the persisted installation, so reruns retain the same intent. |
| Private media and attachments | Real storage uploads, private document briefs and cover images/avatars. An untouched draft project dossier receives a linked document and cover through the attachment/request owners. |
| Reports and analytics | Real English, Persian and Arabic encrypted report archives, a queued report, and populated request/work metrics backed by actual lifecycle records. |
| Support | Every supported incident category, with open/acknowledged/resolved examples and real transition history. Incidents are explicitly labeled `demo.*`. |
| Tasks | Disabled interval, crontab and clocked schedule examples, plus ordinary application outbox records from actual seeded actions. Existing workers/scheduler control later delivery. |
| Integrations and AI | Disabled service/order/notification/AI configuration, a revoked connection and three bounded AI agent drafts. These are inspectable authoring examples. |

External order receipts, paid AI decisions/tool approvals, protected-effect reversal
and uncertain-result reconciliation require configured providers, immutable verified
connections and actual human approval. The seed does not fabricate those outcomes,
grant superuser recovery authority or declare external/hosted/browser acceptance.
Transient states such as request submission, report processing and compensation dispatch
belong to real execution and are not forced into inconsistent permanent records.
Task expiry requires an elapsed real deadline and an authorized administrator; the
seed does not backdate work or create a superuser to force that state.

Business records install in one transaction. Upload/report/schedule owners keep their
own transaction boundaries; rerunning repairs missing later phases. Existing case edits,
personal choices and files are preserved. Modified immutable seed resources are refused
rather than overwritten. Unrelated application data is retained.

## Paired frontend and help metadata

The companion frontend now persists Arabic preferences and renders Arabic runtime forms,
options, help and editable catalogs in RTL. Consume the matching en/fa/ar producer contract.
For saved help acknowledgments, mount the frontend's `docs/delivery/help-release-metadata.json`
into the backend container and set `HELP_RELEASE_METADATA_FILE` to that mounted path.
This is metadata only; help text remains frontend-owned. Without the configured release,
the existing compatibility behavior displays help but does not persist acknowledgments.

## Editable developer scenarios

The data lives in ordinary Python modules under `scripts/demo/`: `templates.py` defines
forms and workflow graphs, `catalog.py` creates actors and exercises workflow services,
`configuration.py` creates inspectable configuration, and `personal.py` / `operations.py`
populate personal and operational features. Fixture inserts use SQLModel where suitable;
request/task transitions use application services so history and authorization stay valid.

`scenarios.py` exposes `load_case()` and `current_states()` using your existing session.
For example, inside a developer script run in the development container:

```python
from pathlib import Path

from scripts.bootstrap_application import open_manifest
from scripts.demo.scenarios import load_case
from core.deps import SessionFactory
from core.settings import settings


async def inspect_leave():
    # Use the installation directory printed by the seed command.
    path = Path(".demo-seed/<target>/installation.json")
    with open_manifest(path, database=settings.POSTGRES_DB, create=False) as manifest:
        async with SessionFactory() as session:
            case = await load_case(
                session, manifest, "leave", "waiting", client="WEB", language="ar"
            )
            # These SQLModel entities belong to this session. Use their current
            # versioned references and the appropriate actor in your service calls.
            return case.request, case.requester, case.reviewer, case.work_items
```

Scenario names are `draft`, `waiting`, `claimed`, `editing`, `completed`, `rejected`,
`correction`, `watching`, `paused`, `cancelled`, `forwarded`, `archived`, `failed_wait`
and `compensated_wait`. They describe the intended exercise; the graph's actual
capabilities determine the resulting state. `--inspect` is authoritative for current
states, including later manual edits. It emits fresh references plus client keys and
release versions, without passwords. Use those public client keys with release `1.0.0`
when logging in to operate a client-pinned request.

The new catalog uses a separate v2 namespace so earlier immutable published resources
and manually edited cases survive. Profiles still using the original generated English
names receive deterministic localized names; manually changed profiles are preserved.

Arabic is now accepted by language negotiation, personal settings, help state, form
catalogs, task text, notifications and reports. Arabic forms use RTL and can explicitly
select Arabic digits; canonical stored values remain unchanged. Common errors and demo
labels are translated. Untranslated technical Swagger descriptions fall back to English.
Client variants verify backend rendering contracts; B2B/SDK records do not imply a native
UI, and frontend language-picker/translation rollout remains a separate consumer change.

## Verification

```sh
mise run workflow-library-test
mise run demo-seed-test
mise run check
```

The seed test uses an owned disposable database and private services. It seeds twice,
checks stable counts and all represented lifecycle states, keeps an edited request,
checks actual attachments, uploads, reports, schedules and support records, and removes
its disposable resources. It does not certify a deployed frontend or external provider.

The obsolete supervisor and its prepare/verify/rehearse/reset/stop commands have
been removed. Demo commands are `demo-seed`, its `demo-prepare` alias, and
`demo-seed-test`. See [the operations handoff](../delivery/DEMO-OPERATIONS-HANDOFF.md).
