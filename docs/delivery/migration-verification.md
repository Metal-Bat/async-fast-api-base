# Current migration policy

Reviewed 2026-10-28. The single chain is:

`0001_schema -> 0002_required_data -> 0003_arabic -> 0004_binding_source_schema -> 0005_binding_object_fields`

- `0001_schema` creates all application/history tables, constraints, indexes and PostgreSQL guards without seed rows.
- `0002_required_data` installs immutable handler/port catalogs, permission definitions, maintenance schedules and optional configured admin bootstrap. It does not grant ordinary users access or activate external providers.
- `0003_arabic` adds Arabic help state and notification handler version 3. Existing version-2 pins and application records are preserved.

- `0004_binding_source_schema` stores declared REQUEST/CONTEXT types without backfilling old rows or changing published pins/checksums. Its partial downgrade refuses loss of declarations. The dedicated owned upgrade/preservation/refusal scenario passes; complete current acceptance belongs to [APP-BE-019.UX02](../changes/APP-BE-019.UX02.md) and its exact receipt.

DB-002's two-file baseline remains unchanged. The later Arabic feature uses a forward
revision under the owner's explicit feature request; it does not authorize rewriting
applied revisions or restructuring unrelated migrations.

Historical 2026-10-11 evidence: fresh installation, empty round trip, populated pin/media/history preservation and
`alembic check` pass in the 18-test disposable foundation profile. The configured
Compose database upgraded to `0003_arabic` without a reset or stamp.

Existing legacy revision markers are deliberately rejected. Upgrade a legacy database
using its old checkout, back it up, and rehearse a separately reviewed transition on a
restored copy before changing a deployed revision marker. Never blindly stamp, reset or
downgrade shared data.

See [DB-002](../changes/DB-002.md), [approved decisions](approved-decisions.json),
[deployment commands](../../README.md#run-migrations) and
current local verification (`developer-seed-verification.json`).

## Object-field continuation — 2026-10-28

`0005_binding_object_fields` adds nullable atomic version/path/schema facts only. Old rows and canonical published payloads remain unchanged. The current owned foundation profile passes fresh/populated upgrade, legacy checksum/pin preservation, drift checks and refusal to discard in-use projection facts. The configured local development installation was privately backed up and rehearsed from its restored clone before the forward upgrade; exact digests retained all 103 business tables and 191,225 rows. No reset, stamp, historical revision rewrite or automatic human approval occurred. The final current-source evidence is linked by [APP-BE-019.UX03](../changes/APP-BE-019.UX03.md). Existing dated evidence above is historical and remains intact.
