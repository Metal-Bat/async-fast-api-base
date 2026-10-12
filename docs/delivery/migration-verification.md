# Current migration policy

Reviewed 2026-10-11. The single chain is:

`0001_schema -> 0002_required_data -> 0003_arabic`

- `0001_schema` creates all application/history tables, constraints, indexes and PostgreSQL guards without seed rows.
- `0002_required_data` installs immutable handler/port catalogs, permission definitions, maintenance schedules and optional configured admin bootstrap. It does not grant ordinary users access or activate external providers.
- `0003_arabic` adds Arabic help state and notification handler version 3. Existing version-2 pins and application records are preserved.

DB-002's two-file baseline remains unchanged. The later Arabic feature uses a forward
revision under the owner's explicit feature request; it does not authorize rewriting
applied revisions or restructuring unrelated migrations.

Fresh installation, empty round trip, populated pin/media/history preservation and
`alembic check` pass in the 18-test disposable foundation profile. The configured
Compose database upgraded to `0003_arabic` without a reset or stamp.

Existing legacy revision markers are deliberately rejected. Upgrade a legacy database
using its old checkout, back it up, and rehearse a separately reviewed transition on a
restored copy before changing a deployed revision marker. Never blindly stamp, reset or
downgrade shared data.

See [DB-002](../changes/DB-002.md), [approved decisions](approved-decisions.json),
[deployment commands](../../README.md#run-migrations) and
current local verification (`developer-seed-verification.json`).
