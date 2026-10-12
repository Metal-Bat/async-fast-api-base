# APP-BE-005.1 — Large multilingual developer seed in Compose

Backlog: APP-BE-005.1
Date: 2026-10-11
Area: developer scenarios, localization, migrations, Compose

## Summary

The one-shot Compose seed creates 3,282 requests and 102 ordinary users on a fresh
installation. Thirteen business workflows each contain 252 cases: fourteen scenario
slots across six client kinds and three languages. Editable Python fixtures and current
SQLModel entity lookup support subsequent application-service calls. Arabic is now a
supported backend locale alongside English and Persian.

## Why

The owner wanted realistic, abundant data for developer state checks and demonstrations,
with every client presentation and mixed English/Persian/Arabic names. The host-oriented
seed and the earlier foreground supervisor did not provide that workflow. The explicit
follow-up also requested Arabic as an actual project language.

## What Changed

- `mise run demo-seed` / `demo-prepare` run the development Compose service. Faker stays
  in the dev dependency group. Source is mounted; rebuild only after dependency changes.
  Locale sources compile before templates load, including on a fresh checkout.
- `scripts/demo/` contains editable forms/graphs, account/configuration fixtures,
  service-driven case transitions and personal/operational examples. SQLModel inserts
  are used where appropriate; request/work/process lifecycles use existing owners.
- `--cases-per-type` accepts 14–2000, default 252. `--inspect` reports current state,
  client key/release and fresh request/work/process references. `load_case()` returns
  entities in the caller's session by workflow, scenario, client, language and batch.
- All twenty controls, six explicit client variants, all task display purposes and
  en/fa/ar form catalogs are represented. Named scenarios exercise graph-supported
  states; their names do not fabricate unsupported terminal states.
- 102 users, eight departments, multilingual deterministic Faker values, preferences,
  calendars, saved views, notices, real private uploads and attachments, en/fa/ar
  encrypted reports, support states and disabled schedules/configuration remain useful
  to ordinary users. Existing role and personal edits are preserved.
- Version-2 fixture identities preserve earlier published resources and manually edited
  cases. Additional credentials append to the existing private file. Original generated
  English names can be localized; manually changed names remain intact.
- Arabic negotiation includes regional tags. Preferences/help/forms/task labels/AI choices/
  notifications/reports accept Arabic. Runtime direction is RTL, Arabic digits are explicit,
  and optional zero/two/few/many plural branches fall back to `other`. Canonical values and
  existing one/other-only serialization are preserved. Common errors and demo labels are
  translated; untranslated technical Swagger descriptions retain English fallback.

## Architecture

### Before

The host command discovered Compose ports and seeded a smaller catalog from application
modules. Public locale contracts accepted English/Persian only.

### After

A development image installs locked dev tools and runs a one-shot script on the Compose
network. Scenario code lives under `scripts/demo/`, with current application services owning
business behavior. Production dependencies remain unchanged. No new server, workflow
engine, permission system or external provider execution is introduced.

### Reason

This provides an editable developer fixture surface while retaining valid workflow history,
immutable pins, authorization and private object integrity.

## Compatibility

- Additive public locale value `ar`, numbering `arab`, optional plural branches and optional
  task-text `ar` preserve canonical snake_case JSON and existing en/fa serialized pins.
  Published notification handler version 2 remains unchanged; version 3 adds Arabic.
- `0003_arabic` extends the help-state constraint and installs notification v3 after the
  unchanged DB-002 baseline. The current database is upgraded forward; no reset or stamp.
  Existing databases already on `0002_required_data` use `alembic upgrade head`.
- The single producer contract export includes Arabic OpenAPI/inspector artifacts and
  actual migration lineage. The authorized APP-FE-008.1 companion consumes all three
  snapshots and adds persistent Arabic, RTL runtime/help and catalog editing. Historical
  receipts remain separate from the current paired browser acceptance.
- Private credentials remain in ignored mode-0700 directories/mode-0600 files. Existing
  passwords and operator changes are preserved. Seed operations keep their owner's
  transaction boundaries; rerun finishes missing later phases.
- External provider receipts, live AI decisions and human approvals are not fabricated.
  No worker or scheduler is started by the seed; existing workers can deliver queued work.
- The obsolete supervisor remains removed under APP-BE-029.1.

## Validation

Commands and results:

- `docker compose build demo-seed`, `docker compose run --rm demo-seed`, and `mise run demo-seed` — passed against the configured current local database. Final counts: 3,282 cases, 102 users, 17 forms, 16 workflows, 615 calendar entries, 18 uploads and four reports.
- Read-only actual-session matrix — 234 workflow/client/language runtime documents passed. The repeated mise seed and `mise run demo-seed -- --inspect` retained every catalog request/work/process version (3,277 catalog cases plus five baseline cases).
- Focused suites — 101 regression tests, 86 documentation/localization tests, eight seed CLI tests, 11 final pair/CLI tests, one real disposable seed test and 18 migration/foundation tests passed. The disposable seed test emitted three existing reporting SQLModel deprecation warnings; no exception was added.
- `FLOW_TEST_PROFILE=delivery-transfers PYTEST_ADDOPTS='-k test_actual_browser_approves' uv run --env-file .envs/.backend python -m scripts.run_flow_test` — six actual frontend/browser scenarios passed across en/fa/ar, including lost approval response recovery, real worker receipts and authorization denials.
- Final `mise run check` — all 16 stages passed: 1,001 default tests, one doctest and 135 required real-service tests. The default suite reports 225 documented opt-in exclusions; required profiles have zero skips. The result remains `VERIFIED_WITH_EXCEPTION` under the unchanged two D07 SDK exceptions.
- Companion frontend full `mise run check` — all 12 stages passed, 597 unit tests and 12 browser quality scopes, zero captured diagnostics. Exact en/fa/ar producer/consumer comparison also passed.
- Both final gates retained identical start/end source identities. Closure edits afterward are documentation/status/evidence only. Both knowledge graphs were updated.

Result: PASS for the requested local seed/Arabic feature scope, with the existing backend D07 qualification. Current [verification evidence](../delivery/developer-seed-verification.json) retains earlier failed/interrupted attempts, source hashes and limits. Historical acceptance below is preserved separately. Native applications, live paid AI, hosted/deployed acceptance and exhaustive accessibility are not established. Help acknowledgments require the matching frontend release metadata configured through `HELP_RELEASE_METADATA_FILE`.


## Backlog Impact

Unfinished task relationships were reviewed. This owner-requested follow-up remains under
APP-BE-005.1, including Arabic required for its language matrix. The user explicitly
extended scope to frontend Arabic under APP-FE-008.1. Other delivery, live AI, hosted
and recovery acceptance scopes remain separate.

Enabled:

- APP-BE-005 developer/demo data coverage.

Blocked:

- None newly introduced.

Superseded:

- Earlier host-command instructions in this record; supervisor removal remains APP-BE-029.1.

Conflicts:

- DB-002's two baseline files are preserved; the Arabic feature adds a forward revision.
  The implementation choice is recorded in approved-decisions.json, without claiming a
  general authorization to restructure migrations or reset databases.

## References

Commit: None.

Pull Request: None.

Additional notes:

- [Seed guide](../guides/demo-seed.md)
- [Operations handoff](../delivery/DEMO-OPERATIONS-HANDOFF.md)
- [Arabic migration follow-up](../delivery/migration-verification.md)
- Historical seed verification
- [Current developer seed verification](../delivery/developer-seed-verification.json)
