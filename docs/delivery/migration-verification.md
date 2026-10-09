# Current migration baseline

The 2026-10-09 owner request supersedes the additive-only repository policy: exactly two
revision files, `0001_schema -> 0002_required_data`. The schema revision contains all current
code tables and PostgreSQL guards without seed rows. The data revision contains required
handler catalogs/ports, permissions, maintenance schedules and optional configured admin
bootstrap. Operations are registered in code; no operation-record table exists.

The complete previous chain and new baseline have identical columns, constraints, indexes,
triggers, functions, comments, handler/port contracts and maintenance schedules in disposable
PostgreSQL. Thirteen permission definitions and four deployed extension handlers are newly installed
without assigning access or activating external providers. Catalog publication preserves unrelated
user-authored draft handlers.
Fresh install, full empty round trip, schema-only empty tables, populated pin/media/history
preservation and `alembic check` passed in the 18-test foundation profile. The complete fifteen-stage gate also passed; see
[migration split evidence](migration-split-gate.json).

Existing old revision markers are deliberately rejected. Upgrade old databases with the old
checkout, back up and rehearse a separately reviewed rebaseline on a restored copy before
changing a deployed database marker. No project database was reset or stamped.
See [DB-002](../changes/DB-002.md) and [deployment instructions](../../README.md#run-migrations).

## Historical additive migration verification

# D01 migration verification and proposed repair

The committed chain is `base -> b13a0c7d2e44 -> c24f913ab601`. Neither revision was edited. D01 owner acceptance remains pending; the delivery pack's one-file mandate conflicts with the already committed workspace revision.

`mise run delivery-foundation-test` creates a unique `bpms_flow_<uuid>` database, migrates it, and removes it in a finally block. Destructive tests additionally check the exact runner ownership token and a local host. The empty round trip runs before any subprocess runtime fixtures, respecting the initial revision's existing refusal to downgrade runtime data.

The populated fixture creates database-valid draft versions at the initial revision, publishes them through the database's lifecycle constraints, and inserts retained request/form/media metadata. It intentionally tests database preservation, not business workflow publication validation or S3 object persistence; the separate purchase/HTTP journeys test executable workflows at head. Upgrade assertions cover both version pins, submission values, checksums, media ownership, retained history triggers, current revision and workspace existence.

Observed result: 14 passes and one failure in the foundation profile. Data preservation assertions passed. The last assertion, `alembic check`, fails with five `modify_comment` operations on `WORKFLOW_WORKSPACE`: ID, VERSION, CREATED_AT, UPDATED_AT, DELETED_AT. No table, column type, constraint or index drift was reported. Evidence: `/tmp/app-be-foundation-final.log`.

After D01 approval, the minimal repair is a new additive revision descending from c24f913ab601, adding these exact existing model comments:

| Column | Comment |
| --- | --- |
| ID | TIME-SORTABLE UUIDV7 PRIMARY KEY. |
| VERSION | OPTIMISTIC-LOCK VERSION NUMBER. |
| CREATED_AT | UTC TIMESTAMP AT WHICH THE ROW WAS CREATED. |
| UPDATED_AT | UTC TIMESTAMP OF THE MOST RECENT UPDATE. |
| DELETED_AT | UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE. |

Its downgrade would remove only those comments. Both existing revisions remain byte-identical. Re-run the empty round trip, populated initial-to-head upgrade and `alembic check` against an owned database. Update the repository's existing exact-two-revisions test to validate the approved linear chain, without weakening immutability or schema-drift checks. This repair is proposed, not applied or approved. No shared database was downgraded, stamped or reset.

## Approved repair verification

On 2026-10-08 the owner explicitly approved preserving both applied revisions and additive revisions on one linear chain, including this repair. New revision d35b924ac712 changes only the five comments. The owned disposable foundation run passed all 16 tests with no skips and no emitted warnings; fresh round trip, populated upgrade and alembic check succeeded. Evidence: /tmp/app-be-approved-migration-foundation.log. Both applied migration hashes were compared byte-for-byte with HEAD and preserved. Previous pending/failure statements above describe pre-approval history.
