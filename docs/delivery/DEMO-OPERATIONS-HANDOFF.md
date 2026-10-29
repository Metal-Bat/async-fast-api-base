# Demo data and application acceptance

## Populate the current database

Run `mise run demo-seed` (also available as `mise run demo-prepare`) to populate
`.envs/.backend`'s current development database from a local one-shot script. There is
no Compose seed service or development image target. The default inserts the reusable
workflow control/type/component library and three ordinary installation accounts;
`--with-demo-cases` additionally generates the larger multilingual business dataset.
`--inspect` reads current business cases when that optional dataset has been inserted.
See the [seed guide](../guides/demo-seed.md) for purposes, credentials and rerun behavior.
`mise run workflow-library-test` verifies the lightweight library; `demo-seed-test`
verifies the optional rich dataset with disposable services.

Shared application tests still own disposable database/storage/worker fixtures for
real workflow, private transfer, recovery and browser acceptance. They remain in the
project gate. Exact D07 exceptions retain VERIFIED_WITH_EXCEPTION; local test results
do not attest hosted or user acceptance.

## Candidate pair, image and hosted checks

The producer authority is `consistency-2026-10-09/contracts/manifest.json`. Full en/fa/ar
paths/components/security are compared to actual consumer snapshots; matching operation
IDs alone is insufficient. Source inventory includes code, canonical notification
data, migrations, scenario, locked tooling and runtime/hosted configuration. Current
intake preserves historical decisions. A dirty source identity is required alongside
each HEAD; source-only snapshot verification does not attest live browser or hosted use.

```sh
uv run python -m scripts.verify_release_pair --frontend "$FRONTEND_CANDIDATE" --report "$FRESH_PAIR_REPORT"
mise run runtime-image-build -- --image app-be-runtime:reviewed --report "$FRESH_IMAGE_REPORT"
APP_RUNTIME_IMAGE=app-be-runtime:reviewed mise run runtime-image-test
mise run check
```

Runtime build uses the existing locked production Dockerfile and an explicit source
context, excluding environment files/private data. Image acceptance checks UID 1000,
actual lifespan/registry/storage, PostgreSQL health and exported real SQL/HTTP spans.
No image is published by these commands.

`.github/workflows/paired-delivery.yml` implements manual paired hosted checks with
pinned actions/tools, an exact reviewed peer commit, disposable GitHub-hosted services,
the unchanged backend gate, actual frontend gate, full contract comparison and rebuilt
image probe. The actual frontend repository resolves to `Metal-Bat/angular-base` (the prior
frontend URL redirects there). Private peers need an owner-provisioned read-only
`PEER_READ_TOKEN`; the currently selected repositories are public.
Provisioning refuses local/self-hosted runners, mutable refs and existing environment
files. Only sanitized summary JSON is uploaded; raw logs, credentials, accounts,
private references and business responses remain private. **No hosted run is attested.**
Publishing a reviewed pair/workflow and obtaining an actual run are separate actions.

## Restore and support

`mise run delivery-restore-test` uses a fresh owned source database and a separately
created restore database/bucket. It checks private object bytes/hash/access, workflow
and form pins, encrypted credential versions, personal preferences/help/views/favorite/
calendar/inbox and durable support incidents. The protected-order restore drill additionally keeps an accepted-but-unacknowledged
order UNKNOWN, denies generic resume and ordinary recovery, then uses authorized
original-identity lookup to confirm its existing receipt without a second purchase.
The restored outbox is not published before reconciliation. Do not start dispatch
on a restored protected workload before provider state is reconciled.

Operator, support and product-owner assignments: TBD. No production RPO/RTO, throughput,
tenancy, compliance, deployment, named-vendor certification or live-model quality is
claimed. The local HTTPS sandbox and scripted no-network AI remain explicitly labeled.
Owner acceptance is separate from test results. See the [capability ledger](BACKEND-CAPABILITY-LEDGER.md) and
[current developer seed verification](developer-seed-verification.json).

## Integration continuation — 2026-10-28

Current local schema head is `0005_binding_object_fields`. Calendar member-only selection, evidence-bound protected-operation notices, object-field bindings/redacted preview and the existing Agent authoring consumers are locally integrated. Internal event append now refreshes its locked current process row after concurrent commits, preserving client optimistic refs and exact replay. The local upgrade preserved all 103 tables / 191,225 rows after a private backup and restored-clone rehearsal; services were resumed, the event writer code fingerprint matched the local container, and health/readiness succeeded. The post-upgrade seeded leave draft was checked without submission or approval. Current complete gates/source identities and the 63 actual paired scenarios are in the peer `artifacts/integration-2026-10-28/completion.json`. Missing/stale/partial receipt evidence remains incomplete; hosted immutable-pair, deployed, live-provider, manual and product-owner gates remain separate. D07 is VERIFIED_WITH_EXCEPTION, never strict exception-free/demo readiness.
