"""Add Arabic help state and a new immutable notification handler contract."""

import sqlalchemy as sa
from alembic import context, op

revision = "0003_arabic"
down_revision = "0002_required_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_USER_HELP_STATE_locale", "USER_HELP_STATE", type_="check")
    op.create_check_constraint(
        "ck_USER_HELP_STATE_locale", "USER_HELP_STATE", "\"LOCALE\" IN ('en', 'fa', 'ar')"
    )
    connection = op.get_bind()
    identity = connection.execute(
        sa.text("""
        INSERT INTO "STEP_TYPE_VERSION" (
            "ID", "VERSION", "CREATED_AT", "STEP_TYPE_ID", "NUMBER", "STATUS",
            "HANDLER_KEY", "HANDLER_VERSION", "EXECUTION_MODE", "CONFIG_SCHEMA"
        )
        SELECT uuidv7(), 1, now(), "STEP_TYPE_ID", 3, 'DRAFT',
               'notification', '3', 'BACKGROUND',
               jsonb_set(jsonb_set("CONFIG_SCHEMA", '{title}', '"NotificationConfigV3"'),
                         '{properties,locale,enum}', '["en","fa","ar"]')
        FROM "STEP_TYPE_VERSION"
        WHERE "HANDLER_KEY" = 'notification' AND "HANDLER_VERSION" = '2'
        RETURNING "ID"
    """)
    ).scalar_one()
    connection.execute(
        sa.text("""
        INSERT INTO "STEP_TYPE_PORT" (
            "ID", "STEP_TYPE_VERSION_ID", "DIRECTION", "PORT_KEY", "VALUE_SCHEMA",
            "REQUIRED", "NULLABLE", "CARDINALITY", "CREATED_AT"
        )
        SELECT uuidv7(), :identity, p."DIRECTION", p."PORT_KEY", p."VALUE_SCHEMA",
               p."REQUIRED", p."NULLABLE", p."CARDINALITY", now()
        FROM "STEP_TYPE_PORT" p JOIN "STEP_TYPE_VERSION" v ON v."ID" = p."STEP_TYPE_VERSION_ID"
        WHERE v."HANDLER_KEY" = 'notification' AND v."HANDLER_VERSION" = '2'
    """),
        {"identity": identity},
    )
    connection.execute(
        sa.text("""
        UPDATE "STEP_TYPE_VERSION" SET "STATUS" = 'PUBLISHED', "PUBLISHED_AT" = now(),
            "UPDATED_AT" = now() WHERE "ID" = :identity
    """),
        {"identity": identity},
    )


def downgrade() -> None:
    if context.get_revision_argument() is not None:
        raise RuntimeError(
            "Required data cannot be downgraded independently; use a backup to roll back"
        )
