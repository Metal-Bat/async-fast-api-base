"""Add optional versioned object destinations without changing old bindings or pins."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0005_binding_object_fields"
down_revision = "0004_binding_source_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add null facts only; no inference, backfill or changes to existing graph payloads."""
    op.add_column(
        "WORKFLOW_STEP_INPUT_BINDING",
        sa.Column(
            "TARGET_PROJECTION_VERSION",
            sa.Integer(),
            nullable=True,
            comment="OBJECT FIELD PROJECTION CONTRACT VERSION; NULL PRESERVES LEGACY WHOLE-PORT/LIST BINDINGS.",
        ),
    )
    op.add_column(
        "WORKFLOW_STEP_INPUT_BINDING",
        sa.Column(
            "TARGET_PATH",
            sa.String(1024),
            nullable=True,
            comment="DECLARED OBJECT FIELD DESTINATION; MAXIMUM 1024 UTF-8 BYTES; NOT A RESOURCE REFERENCE.",
        ),
    )
    op.add_column(
        "WORKFLOW_STEP_INPUT_BINDING",
        sa.Column(
            "TARGET_SCHEMA",
            postgresql.JSONB(none_as_null=True),
            nullable=True,
            comment="PROJECTED SCALAR OBJECT ROOT DECLARATION PINNED WITH THIS BINDING; TYPE INFORMATION NEVER GRANTS AUTHORITY.",
        ),
    )
    op.create_check_constraint(
        "ck_WORKFLOW_BINDING_target_projection",
        "WORKFLOW_STEP_INPUT_BINDING",
        '("TARGET_PROJECTION_VERSION" IS NULL AND "TARGET_PATH" IS NULL AND "TARGET_SCHEMA" IS NULL) OR ("TARGET_PROJECTION_VERSION" IS NOT NULL AND "TARGET_PROJECTION_VERSION" = 1 AND "TARGET_PATH" IS NOT NULL AND "TARGET_SCHEMA" IS NOT NULL AND left("TARGET_PATH", 1) = \'/\' AND octet_length("TARGET_PATH") <= 1024 AND jsonb_typeof("TARGET_SCHEMA") = \'object\' AND "TARGET_SCHEMA" ? \'type\' AND "TARGET_SCHEMA" ->> \'type\' = \'object\' AND "TARGET_SCHEMA" ? \'properties\' AND jsonb_typeof("TARGET_SCHEMA" -> \'properties\') = \'object\')',
    )
    op.create_unique_constraint(
        "uq_WORKFLOW_BINDING_target_path",
        "WORKFLOW_STEP_INPUT_BINDING",
        ["WORKFLOW_STEP_ID", "TARGET_PORT_ID", "TARGET_PATH"],
    )


def downgrade() -> None:
    """An in-use projection cannot be discarded by a partial downgrade."""
    if (
        context.get_revision_argument() is not None
        and op.get_bind()
        .execute(
            sa.text(
                'SELECT EXISTS (SELECT 1 FROM "WORKFLOW_STEP_INPUT_BINDING" WHERE "TARGET_PROJECTION_VERSION" IS NOT NULL OR "TARGET_PATH" IS NOT NULL OR "TARGET_SCHEMA" IS NOT NULL)'
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Object field projections cannot be discarded; use a reviewed backup")
    op.drop_constraint(
        "uq_WORKFLOW_BINDING_target_path", "WORKFLOW_STEP_INPUT_BINDING", type_="unique"
    )
    op.drop_constraint(
        "ck_WORKFLOW_BINDING_target_projection", "WORKFLOW_STEP_INPUT_BINDING", type_="check"
    )
    op.drop_column("WORKFLOW_STEP_INPUT_BINDING", "TARGET_SCHEMA")
    op.drop_column("WORKFLOW_STEP_INPUT_BINDING", "TARGET_PATH")
    op.drop_column("WORKFLOW_STEP_INPUT_BINDING", "TARGET_PROJECTION_VERSION")
