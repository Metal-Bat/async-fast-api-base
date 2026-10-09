# Wave four backend handoff

Backend baseline: `995829eebd9483ac6b589c1648fc799c650ad464`, with uncommitted
wave-three/four changes. Read-only paired boundary:
`afe4bbe5f566c80e7eb45f6ef9f12c041d60139d` in the sibling frontend repository.
The generated [manifest](wave-four/manifest.json) hashes full English/Farsi OpenAPI,
inspector contracts, metric definitions and help metadata examples. Regenerate with:

```sh
PYTHONPATH=src LOG_OUTPUTS='["console"]' uv run --env-file .envs/.backend python scripts/export_wave_four_contracts.py
```

All new JSON contracts inherit BaseDTO and serialize snake_case. Existing success,
page and numeric error envelopes remain authoritative. All private responses use
`Cache-Control: private, no-store`. These artifacts freeze backend behavior for the
peer; they do not attest frontend implementation, browser acceptance or deployment.

## C01/C13: supported bootstrap

`scripts/bootstrap_application.py` owns supported system/install/demo operations;
runtime code imports application services, never test fixtures. Set explicit backend
environment configuration and apply `alembic upgrade head` before bootstrap.

```sh
PYTHONPATH=src LOG_OUTPUTS='["console"]' uv run --env-file .envs/.backend python scripts/bootstrap_application.py system --check
PYTHONPATH=src LOG_OUTPUTS='["console"]' uv run --env-file .envs/.backend python scripts/bootstrap_application.py system
PYTHONPATH=src LOG_OUTPUTS='["console"]' uv run --env-file .envs/.backend python scripts/bootstrap_application.py install --manifest /private/installation.json
PYTHONPATH=src LOG_OUTPUTS='["console"]' uv run --env-file .envs/.backend python scripts/bootstrap_application.py demo --enable-demo --manifest /private/demo.json
```

Install consumes an owner-provisioned 0600 regular file: `seed_version: 1`, a stable
`installation_id` UUID, exact `database` name, and 1–3 `accounts` with `persona`
(requester/reviewer/designer), `username`, and a private password of at least 16
characters. No example includes usable credentials. Demo creates a fresh private
manifest exclusively, persists random credentials before database writes and reuses
the same file on retry. Symlinks, hardlinks, non-owner files, files over 32 KiB,
concurrent file owners and database mismatches are refused. Keep this file private;
credentials are never printed. `--check` and `--dry-run` perform no writes and do not
create a missing manifest. Missing/conflicting configuration exits 2.

Demo requires explicit enablement, local/develop environment, loopback PostgreSQL
and a `bpms_demo_`/`bpms_flow_` database. It checks object-storage bucket access before
business writes. Provision the private bucket and Redis separately. Account and
definition creation is transactional; assets use their existing upload owner's
commit boundary afterward. An asset failure is repairable by rerunning the same
manifest and is not reported as overall success.

Ordinary users and deterministic requester/reviewer groups are installation-owned.
Repeat runs preserve passwords, names and revoked memberships/grants. A public web
client/release is registered through existing services. Two localized immutable
templates (purchase and service request) are published through actual form/workflow
owners. Five purchase cases represent draft, waiting, correction, rejection and
completion through actual commands, with explicit synthetic labels. Two private
synthetic assets have checked ownership and byte integrity. Changed/deleted template
roots, added versions and provenance conflicts are refused rather than overwritten.
Providers are not configured or marked verified. APP-BE-026/029 own later restore/reset.

## C02: personal settings/profile

GET/PATCH `/api/v1/me/preferences` and `/api/v1/me/profile` are self-only. Read never
inserts defaults. Preference defaults: system/blue/comfortable appearance;
en/UTC/gregory/latn locale; requests landing and 20 rows. Palette keys are blue,
indigo, violet, emerald, teal, rose, amber; density comfortable/compact; language
en/fa; digits latn/arabext; landing requests/work_items/studio/dashboard; size 1–100.
Valid IANA zones are required. A landing preference grants no route permission.

Use the GET `ref_id` for PATCH. Missing groups/fields preserve values, a null group
resets that group, and nested scalar nulls fail 422. Unknown/privilege/actor fields
fail validation. Stale writes fail 409 atomically; wrong actor references fail 404;
no-op preserves refs. Concurrent initial writes serialize using the live user row.

Profile changes only names and an owned live private image. Upload through existing
`/media/images`; avatar attachment requires a current image ref. Wrong owner, kind,
deleted or stale image returns 404. Null removes the binding, preserving the retained
upload. Contact/security/session changes remain in existing auth APIs. Preferences
are users-owned JSONB with bounded typed validation, FK and history; no shared cache.

## C03: search, selected values and durable links

Existing resource `/select` and `/designer/selectors/{kind}` endpoints remain search
owners; selected values outside a page use POST `/resource-links/selected` with at
most 50 `{kind, ref_id}` items, preserving request order. Missing/revoked/ineligible
items fail the whole request without partial titles. Read authorization and selection
eligibility are distinct; selection does not grant execution/use authority.

POST `/resource-links` creates a stable locator from an authorized reference;
POST `/resource-links/resolve` returns the current reference and an allowlisted
`route_key`. Browser routing maps keys locally; never interpolate a URL or table name.
The encrypted locator binds kind+UUID without storing an optimistic version. Every
resolution repeats live actor/permission/owner checks. Signing-key replacement
invalidates locators. Readable inactive/retired records report `available=false`;
deleted, forged and forbidden records return the same safe 404. Version links stay
on the named version, never advance to latest. Future favorites/calendar/notifications
must add adapters through their owning services rather than generic ORM dispatch.

| Kinds | Owner/read rule | Selection eligibility |
| --- | --- | --- |
| users, work_groups | Existing users/group detail, admin permission | Designer safe labels; live users/active groups |
| clients, client_releases | Client service; forms.manage | Active client/enabled release |
| forms, form_versions | Form service; forms.manage | Actor-owned/superuser, active root, published version |
| workflows, workflow_versions | Workflow service; workflows.manage plus view grant | Active root; published version |
| step_versions | Step type service; workflows.manage | Enabled live root, executable published snapshot |
| request_types | Request service; requests.manage for detail | Designer permission, active type and accessible active workflow |
| connections | Connection owner/use grants; integrations.manage for detail | Designer permission and use grant; ACTIVE/VERIFIED |
| agent_versions | Agent service plus workflows.manage | Owning published immutable agent |
| components, component_versions, data_types, data_type_versions | Library owner/grants plus forms.manage | Active root and published version |

## C05: frontend-owned help

Ship the frontend's metadata-only release file conforming to
`wave-four/help-release.schema.json`; configure `HELP_RELEASE_METADATA_FILE` to that
file. The synthetic example is a contract fixture, not shipped help content. Missing,
oversized (>64 KiB), invalid or stale metadata produces compatibility results without
state writes. Backend stores no help prose, HTML, duration, tracking events or form data.

GET `/me/help-state` is a bounded self-only page, not an acknowledgment. Explicit POST
`/seen` and `/dismiss` require exact help_key/revision/en-or-fa locale. First timestamps
are preserved; last-view time advances only on seen. Dismissal alone does not mean
read. Locale/revision tuples are independent. Maximum 512 records per user; POST
`/reset` with `{}` deletes only personal help metadata. Failed storage of an action
must not prevent local help display. Peer APP-FE-010 must supply actual release content.

## C10: registered metrics

GET `/analytics/catalog`, POST `/analytics/query` require requests.start and a live
actor. See `wave-four/metric-dictionary.json` for exact population, timestamp and unit.
Request metrics cover the actor's own live requests; work metrics use the existing
direct/group/archive cartable predicates. No cache is shared between identities.
Aggregate before paging; use returned drill-down query with `/business-requests/search`
or `/work-items/search` according to its route key.

Civil dates form a half-open 1–366 day window in a valid IANA zone; day buckets honor
DST, and nonexistent local midnights fail validation. Only none/status dimensions
are accepted. Active/claimable/claimed/overdue metrics are current-state cohorts,
not historical occupancy. Overdue means claimable OPEN work with a non-null deadline
before as_of. Correction counts actual RETURNED work decisions. Submission counts
include cancelled requests with real submitted_at. Terminal duration averages valid
submission-to-close timing of COMPLETED/FAILED/CANCELLED requests; missing/negative
timing contributes to unknown_count, not the mean. Empty count is zero; empty duration
is null. Business outcomes and integration receipts are explicitly unavailable until
their later configured owners exist; completion never implies approval. No money sum.
Controlled-fixture query plans are inspected without adding speculative indexes;
fixture timing is not a production performance guarantee. Exports stay in reporting.

## C11: authoring metadata

GET `/designer/inspector-contract` enumerates every deployed handler/version and all
20 primitive field types directly from code-owned registries. Generated en/fa files
are the complete matrix: schemas, enums/unions/conditional structures, ports,
fingerprints, outcome source, capabilities, help keys, samples and selector roles.
Fixed catalog metadata is now typed; genuinely extensible configuration remains
validated JSON Schema 2020-12. Existing stored published snapshots are not rewritten.

POST `/designer/config-validation` validates an exact handler/version without executing
anything. Configuration is bounded to 128 top-level properties and 16 KiB; diagnostics
return safe JSON pointers and codes, never values or exception text. Unknown names
and untrusted nested keys are omitted. Discovery does not imply published availability
or resource-use permission. Publication, selectors, completion, field inventory and
bounded pure synthetic previews remain their existing owners. The frontend must
round-trip hidden supported properties and render deliberate compatibility errors.

## C14: private transfer/report bounds

Upload and normalized image input: 10 MiB; image decode: 40 million pixels. Oversize
input fails 413 before object persistence. Report archive: 10 MiB by default,
configurable through MAX_REPORT_ARCHIVE_BYTES within 1–64 MiB; generation rejects an
oversized archive before S3 upload/READY. Peer boundary currently caps request bodies
at 11 MiB and upstream requests at 15 seconds. Increasing backend limits alone does
not create a supported paired limit. D05 browser/device/performance signoff remains open.

Private upload metadata and report list/detail/history/download are actor-authorized,
no-store; bytes additionally use nosniff and sanitized server-owned Content-Disposition.
Node forwards response headers, while a custom Content-Disposition *request* preference
needs APP-FE-036 forwarding work; backend defaults already work through the boundary.
Report READY denotes generated storage bytes; PENDING is not a completed job. Existing
resource POST `/report` search aliases are not generated archive jobs. Password-bearing
report details remain private. Downloads preflight size/type/checksum metadata before
recording an authorized start; download_count is a start attempt, not completed transfer.
New report objects carry SHA256 metadata; legacy objects without it retain size/type
compatibility and do not gain retrospective integrity assurance.

S3 downloads use 64 KiB chunks and close body/client contexts on generator closure.
Uploads/normalization buffer at most accepted input and bounded image pixels; report
generation retains existing row/chunk/parallelism and in-memory processing limits.
These bounds are not throughput guarantees. Verification starts only uniquely owned
local databases, broker/cache/storage containers, queue/bucket and worker, plus actual
Node/Uvicorn processes. The maximum report transport fixture is explicitly synthetic;
worker generation has a separate mandatory real encrypted-archive test. No shared
volume reset, published pin rewrite or browser token exposure is used.
