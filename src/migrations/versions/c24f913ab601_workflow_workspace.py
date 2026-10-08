"""Persist authoring WIP separately from executable workflow graphs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c24f913ab601"
down_revision = "b13a0c7d2e44"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "WORKFLOW_WORKSPACE",
        sa.Column("ID", sa.Uuid(), primary_key=True, server_default=sa.text("uuidv7()")),
        sa.Column("VERSION", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("UPDATED_AT", sa.DateTime(timezone=True)),
        sa.Column("DELETED_AT", sa.DateTime(timezone=True)),
        sa.Column(
            "WORKFLOW_VERSION_ID",
            sa.Uuid(),
            sa.ForeignKey("WORKFLOW_VERSION.ID", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("DOCUMENT", JSONB(), nullable=False),
        sa.Column("PROMOTED_GRAPH_CHECKSUM", sa.String(64)),
        sa.UniqueConstraint("WORKFLOW_VERSION_ID", name="uq_WORKFLOW_WORKSPACE_version"),
    )
    op.create_index("ix_WORKFLOW_WORKSPACE_CREATED_AT", "WORKFLOW_WORKSPACE", ["CREATED_AT"])
    from core.history import create_history_table

    metadata = sa.MetaData()
    source = sa.Table("WORKFLOW_WORKSPACE", metadata, autoload_with=op.get_bind())
    create_history_table(source, ondelete="RESTRICT", onupdate="RESTRICT").create(op.get_bind())


def downgrade():
    op.drop_table("WORKFLOW_WORKSPACE_HISTORY")
    op.drop_table("WORKFLOW_WORKSPACE")
