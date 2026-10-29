"""Retain declared binding schemas without rewriting legacy immutable graphs."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0004_binding_source_schema"
down_revision = "0003_arabic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable declarations; existing payloads, pins and checksums stay unchanged."""
    op.add_column(
        "WORKFLOW_STEP_INPUT_BINDING",
        sa.Column(
            "SOURCE_SCHEMA",
            postgresql.JSONB(none_as_null=True),
            nullable=True,
            comment="VALIDATED AUTHOR-DECLARED REQUEST/CONTEXT SCHEMA PINNED WITH THIS EXECUTABLE BINDING; NULL PRESERVES LEGACY ROWS.",
        ),
    )
    op.create_check_constraint(
        "ck_WORKFLOW_BINDING_source_schema",
        "WORKFLOW_STEP_INPUT_BINDING",
        "\"SOURCE_SCHEMA\" IS NULL OR (\"SOURCE_KIND\" IN ('REQUEST', 'CONTEXT') AND jsonb_typeof(\"SOURCE_SCHEMA\") = 'object')",
    )


def downgrade() -> None:
    """Refuse a data-losing partial rollback; full teardown remains disposable-only."""
    if (
        context.get_revision_argument() is not None
        and op.get_bind()
        .execute(
            sa.text(
                'SELECT EXISTS (SELECT 1 FROM "WORKFLOW_STEP_INPUT_BINDING" WHERE "SOURCE_SCHEMA" IS NOT NULL)'
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Declared binding schemas cannot be discarded; use a reviewed backup")
    op.drop_constraint(
        "ck_WORKFLOW_BINDING_source_schema", "WORKFLOW_STEP_INPUT_BINDING", type_="check"
    )
    op.drop_column("WORKFLOW_STEP_INPUT_BINDING", "SOURCE_SCHEMA")
