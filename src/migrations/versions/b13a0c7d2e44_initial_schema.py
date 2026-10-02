"""Complete initial schema, seeds and PostgreSQL guards.

Consolidates the former 33-revision chain. The former head ID is retained so
fully upgraded databases remain current. Domain stages preserve the original
operation order, including seed updates and trigger installation.
"""

import hashlib
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b13a0c7d2e44"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the complete schema and seed data from an empty database."""
    _upgrade_core()
    _upgrade_work_groups()
    _upgrade_versioned_step_types_and_typed_ports()
    _upgrade_versioned_forms_and_render_contracts()
    _upgrade_governed_integration_connections()
    _upgrade_versioned_workflow_authoring()
    _upgrade_typed_transform_handler_v2()
    _upgrade_request_types_and_business_request()
    _upgrade_durable_single_token_process_runtime()
    _upgrade_background_automation_snapshot()
    _upgrade_form_submission_attachments()
    _upgrade_claimable_human_work()
    _upgrade_durable_event_and_timer_waits()
    _upgrade_append_only_process_events()
    _upgrade_advanced_execution()
    _upgrade_durable_notifications()
    _upgrade_registered_client_releases()
    _upgrade_request_client_restrictions()
    _upgrade_versioned_form_design_variants()
    _upgrade_pin_request_presentation_design()
    _upgrade_explicit_request_cross_client_resume()
    _upgrade_audit_form_presentation_interactions()
    _upgrade_durable_ai_task_budget_reservations()
    _upgrade_versioned_ai_agents()
    _upgrade_record_actual_ai_reservation_model()
    _upgrade_ai_tool_approval_checkpoint()
    _upgrade_versioned_form_localization()
    _upgrade_authored_form_library_versions()
    _upgrade_form_behavior_and_collection_state()
    _upgrade_human_task_contract_and_corrections()
    _upgrade_subprocess_authoring_contract()
    _upgrade_subprocess_runtime()
    _upgrade_library_template_provenance()


def downgrade() -> None:
    """Remove the complete schema in reverse dependency order."""
    _downgrade_library_template_provenance()
    _downgrade_subprocess_runtime()
    _downgrade_subprocess_authoring_contract()
    _downgrade_human_task_contract_and_corrections()
    _downgrade_form_behavior_and_collection_state()
    _downgrade_authored_form_library_versions()
    _downgrade_versioned_form_localization()
    _downgrade_ai_tool_approval_checkpoint()
    _downgrade_record_actual_ai_reservation_model()
    _downgrade_versioned_ai_agents()
    _downgrade_durable_ai_task_budget_reservations()
    _downgrade_audit_form_presentation_interactions()
    _downgrade_explicit_request_cross_client_resume()
    _downgrade_pin_request_presentation_design()
    _downgrade_versioned_form_design_variants()
    _downgrade_request_client_restrictions()
    _downgrade_registered_client_releases()
    _downgrade_durable_notifications()
    _downgrade_advanced_execution()
    _downgrade_append_only_process_events()
    _downgrade_durable_event_and_timer_waits()
    _downgrade_claimable_human_work()
    _downgrade_form_submission_attachments()
    _downgrade_background_automation_snapshot()
    _downgrade_durable_single_token_process_runtime()
    _downgrade_request_types_and_business_request()
    _downgrade_typed_transform_handler_v2()
    _downgrade_versioned_workflow_authoring()
    _downgrade_governed_integration_connections()
    _downgrade_versioned_forms_and_render_contracts()
    _downgrade_versioned_step_types_and_typed_ports()
    _downgrade_work_groups()
    _downgrade_core()


# Core


def _create_initial_admin() -> None:
    username = os.getenv("INITIAL_ADMIN_USERNAME")
    password = os.getenv("INITIAL_ADMIN_PASSWORD")
    if not username and not password:
        return
    if not username or not password:
        raise RuntimeError(
            "INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD must be configured together"
        )
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    user = sa.table(
        "USER",
        sa.column("VERSION", sa.Integer()),
        sa.column("CREATED_AT", sa.DateTime(timezone=True)),
        sa.column("USERNAME", sa.String(length=255)),
        sa.column("EMAIL", sa.String(length=255)),
        sa.column("IS_SUPERUSER", sa.Boolean()),
        sa.column("FIRST_NAME", sa.String(length=255)),
        sa.column("LAST_NAME", sa.String(length=255)),
        sa.column("HASHED_PASSWORD", sa.String()),
    )
    op.bulk_insert(
        user,
        [
            {
                "VERSION": 1,
                "CREATED_AT": datetime.now(UTC),
                "USERNAME": username,
                "EMAIL": None,
                "IS_SUPERUSER": True,
                "FIRST_NAME": None,
                "LAST_NAME": None,
                "HASHED_PASSWORD": (salt + key).hex(),
            }
        ],
    )


def _create_report_cleanup_schedule() -> None:
    schedule = sa.table(
        "PERIODIC_TASK",
        sa.column("VERSION", sa.Integer()),
        sa.column("CREATED_AT", sa.DateTime(timezone=True)),
        sa.column("NAME", sa.String(length=255)),
        sa.column("TASK_NAME", sa.String(length=255)),
        sa.column("QUEUE", sa.String(length=255)),
        sa.column("SCHEDULE_TYPE", sa.String(length=32)),
        sa.column("INTERVAL_SECONDS", sa.Float()),
        sa.column("ARGS", sa.JSON()),
        sa.column("KWARGS", sa.JSON()),
        sa.column("HEADERS", sa.JSON()),
        sa.column("ENABLED", sa.Boolean()),
        sa.column("ONE_OFF", sa.Boolean()),
        sa.column("TOTAL_RUN_COUNT", sa.Integer()),
    )
    op.bulk_insert(
        schedule,
        [
            {
                "VERSION": 1,
                "CREATED_AT": datetime.now(UTC),
                "NAME": "report-cleanup-hourly",
                "TASK_NAME": "reporting.cleanup_expired",
                "QUEUE": os.getenv("CELERY_REPORT_QUEUE", "reporting"),
                "SCHEDULE_TYPE": "interval",
                "INTERVAL_SECONDS": 3600.0,
                "ARGS": [],
                "KWARGS": {},
                "HEADERS": {},
                "ENABLED": True,
                "ONE_OFF": False,
                "TOTAL_RUN_COUNT": 0,
            }
        ],
    )


def _upgrade_core() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "LOGIN_FAILURE",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column(
            "IDENTIFIER",
            sa.String(length=255),
            nullable=False,
            comment="NORMALIZED ATTEMPTED LOGIN IDENTIFIER.",
        ),
        sa.Column("FAILURE_COUNT", sa.Integer(), nullable=False),
        sa.Column("LOCKED_UNTIL", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_LOGIN_FAILURE_CREATED_AT"), "LOGIN_FAILURE", ["CREATED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_LOGIN_FAILURE_IDENTIFIER"), "LOGIN_FAILURE", ["IDENTIFIER"], unique=True
    )
    op.create_index(
        op.f("ix_LOGIN_FAILURE_LOCKED_UNTIL"), "LOGIN_FAILURE", ["LOCKED_UNTIL"], unique=False
    )
    op.create_table(
        "PERIODIC_TASK",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("NAME", sa.String(length=255), nullable=False, comment="UNIQUE SCHEDULE NAME."),
        sa.Column(
            "TASK_NAME",
            sa.String(length=255),
            nullable=False,
            comment="REGISTERED CELERY TASK NAME.",
        ),
        sa.Column("QUEUE", sa.String(length=255), nullable=False, comment="DESTINATION QUEUE."),
        sa.Column(
            "SCHEDULE_TYPE",
            sa.String(length=32),
            nullable=False,
            comment="INTERVAL, CRONTAB, OR CLOCKED.",
        ),
        sa.Column("INTERVAL_SECONDS", sa.Float(), nullable=True, comment="INTERVAL IN SECONDS."),
        sa.Column(
            "CRON_MINUTE", sa.String(length=64), nullable=True, comment="CRON MINUTE EXPRESSION."
        ),
        sa.Column(
            "CRON_HOUR", sa.String(length=64), nullable=True, comment="CRON HOUR EXPRESSION."
        ),
        sa.Column(
            "CRON_DAY_OF_WEEK",
            sa.String(length=64),
            nullable=True,
            comment="CRON WEEKDAY EXPRESSION.",
        ),
        sa.Column(
            "CRON_DAY_OF_MONTH",
            sa.String(length=64),
            nullable=True,
            comment="CRON DAY-OF-MONTH EXPRESSION.",
        ),
        sa.Column(
            "CRON_MONTH_OF_YEAR",
            sa.String(length=64),
            nullable=True,
            comment="CRON MONTH EXPRESSION.",
        ),
        sa.Column(
            "CLOCKED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="ONE-OFF EXECUTION TIMESTAMP.",
        ),
        sa.Column("ARGS", sa.JSON(), nullable=False, comment="POSITIONAL TASK ARGUMENTS."),
        sa.Column("KWARGS", sa.JSON(), nullable=False, comment="KEYWORD TASK ARGUMENTS."),
        sa.Column("HEADERS", sa.JSON(), nullable=False, comment="AMQP MESSAGE HEADERS."),
        sa.Column(
            "ENABLED", sa.Boolean(), nullable=False, comment="WHETHER THIS SCHEDULE IS ACTIVE."
        ),
        sa.Column("ONE_OFF", sa.Boolean(), nullable=False, comment="DISABLE AFTER ONE EXECUTION."),
        sa.Column(
            "START_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="EARLIEST EXECUTION TIMESTAMP.",
        ),
        sa.Column(
            "EXPIRES_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="LATEST EXECUTION TIMESTAMP.",
        ),
        sa.Column(
            "LAST_RUN_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="MOST RECENT DISPATCH TIMESTAMP.",
        ),
        sa.Column("TOTAL_RUN_COUNT", sa.Integer(), nullable=False, comment="NUMBER OF DISPATCHES."),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("NAME"),
    )
    op.create_index(
        op.f("ix_PERIODIC_TASK_CREATED_AT"), "PERIODIC_TASK", ["CREATED_AT"], unique=False
    )
    op.create_index(op.f("ix_PERIODIC_TASK_ENABLED"), "PERIODIC_TASK", ["ENABLED"], unique=False)
    op.create_table(
        "PERMISSION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("NAME", sa.String(length=255), nullable=False, comment="UNIQUE PERMISSION NAME."),
        sa.Column("DESCRIPTION", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(op.f("ix_PERMISSION_CREATED_AT"), "PERMISSION", ["CREATED_AT"], unique=False)
    op.create_index(op.f("ix_PERMISSION_NAME"), "PERMISSION", ["NAME"], unique=True)
    op.create_table(
        "ROLE",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("NAME", sa.String(length=255), nullable=False, comment="UNIQUE ROLE NAME."),
        sa.Column("DESCRIPTION", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(op.f("ix_ROLE_CREATED_AT"), "ROLE", ["CREATED_AT"], unique=False)
    op.create_index(op.f("ix_ROLE_NAME"), "ROLE", ["NAME"], unique=True)
    op.create_table(
        "SCHEDULER_LEASE",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column(
            "NAME", sa.String(length=255), nullable=False, comment="UNIQUE SCHEDULER LEASE NAME."
        ),
        sa.Column(
            "OWNER_ID",
            sa.Uuid(),
            nullable=False,
            comment="UUIDV7 OF THE SCHEDULER PROCESS HOLDING THE LEASE.",
        ),
        sa.Column(
            "EXPIRES_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC DEADLINE AFTER WHICH ANOTHER SCHEDULER MAY CLAIM THE LEASE.",
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_SCHEDULER_LEASE_CREATED_AT"), "SCHEDULER_LEASE", ["CREATED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_SCHEDULER_LEASE_EXPIRES_AT"), "SCHEDULER_LEASE", ["EXPIRES_AT"], unique=False
    )
    op.create_index(op.f("ix_SCHEDULER_LEASE_NAME"), "SCHEDULER_LEASE", ["NAME"], unique=True)
    op.create_index(
        op.f("ix_SCHEDULER_LEASE_OWNER_ID"), "SCHEDULER_LEASE", ["OWNER_ID"], unique=False
    )
    op.create_table(
        "TASK_EXECUTION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column(
            "TASK_ID", sa.String(length=255), nullable=False, comment="CELERY TASK IDENTIFIER."
        ),
        sa.Column(
            "TASK_NAME", sa.String(length=255), nullable=False, comment="REGISTERED TASK NAME."
        ),
        sa.Column(
            "QUEUE", sa.String(length=255), nullable=True, comment="QUEUE USED FOR EXECUTION."
        ),
        sa.Column(
            "STATUS", sa.String(length=32), nullable=False, comment="CURRENT CELERY TASK STATE."
        ),
        sa.Column("ARGS", sa.JSON(), nullable=True, comment="SUBMITTED POSITIONAL ARGUMENTS."),
        sa.Column("KWARGS", sa.JSON(), nullable=True, comment="SUBMITTED KEYWORD ARGUMENTS."),
        sa.Column("RESULT", sa.JSON(), nullable=True, comment="JSON-COMPATIBLE TASK RESULT."),
        sa.Column("TRACEBACK", sa.Text(), nullable=True, comment="FAILURE TRACEBACK."),
        sa.Column("WORKER", sa.String(length=255), nullable=True, comment="WORKER HOSTNAME."),
        sa.Column("RETRIES", sa.Integer(), nullable=False, comment="RETRY COUNT."),
        sa.Column(
            "STARTED_AT", sa.DateTime(timezone=True), nullable=True, comment="UTC EXECUTION START."
        ),
        sa.Column(
            "FINISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC EXECUTION FINISH.",
        ),
        sa.Column(
            "DURATION_SECONDS", sa.Float(), nullable=True, comment="EXECUTION DURATION IN SECONDS."
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_TASK_EXECUTION_CREATED_AT"), "TASK_EXECUTION", ["CREATED_AT"], unique=False
    )
    op.create_index(op.f("ix_TASK_EXECUTION_STATUS"), "TASK_EXECUTION", ["STATUS"], unique=False)
    op.create_index(op.f("ix_TASK_EXECUTION_TASK_ID"), "TASK_EXECUTION", ["TASK_ID"], unique=True)
    op.create_index(
        op.f("ix_TASK_EXECUTION_TASK_NAME"), "TASK_EXECUTION", ["TASK_NAME"], unique=False
    )
    op.create_table(
        "TASK_IDEMPOTENCY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column(
            "KEY",
            sa.Uuid(),
            nullable=False,
            comment="INTERNAL TIME-SORTABLE UUIDV7 IDEMPOTENCY KEY.",
        ),
        sa.Column(
            "TASK_ID", sa.String(length=255), nullable=False, comment="TASK THAT OWNS THE CLAIM."
        ),
        sa.Column("OWNER_TOKEN", sa.Uuid(), nullable=True),
        sa.Column("STATUS", sa.String(length=32), nullable=False),
        sa.Column("RESULT", sa.JSON(), nullable=True),
        sa.Column(
            "EXPIRES_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC CLAIM EXPIRATION.",
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_TASK_IDEMPOTENCY_CREATED_AT"), "TASK_IDEMPOTENCY", ["CREATED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_TASK_IDEMPOTENCY_EXPIRES_AT"), "TASK_IDEMPOTENCY", ["EXPIRES_AT"], unique=False
    )
    op.create_index(op.f("ix_TASK_IDEMPOTENCY_KEY"), "TASK_IDEMPOTENCY", ["KEY"], unique=True)
    op.create_table(
        "TASK_OUTBOX",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("TASK_ID", sa.String(length=255), nullable=False),
        sa.Column("TASK_NAME", sa.String(length=255), nullable=False),
        sa.Column("QUEUE", sa.String(length=255), nullable=False),
        sa.Column("ARGS", sa.JSON(), nullable=False),
        sa.Column("KWARGS", sa.JSON(), nullable=False),
        sa.Column("HEADERS", sa.JSON(), nullable=False),
        sa.Column("PRIORITY", sa.Integer(), nullable=False, comment="AMQP MESSAGE PRIORITY."),
        sa.Column("AVAILABLE_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("PUBLISHED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ATTEMPTS", sa.Integer(), nullable=False),
        sa.Column("LAST_ERROR", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("TASK_ID"),
    )
    op.create_index(
        op.f("ix_TASK_OUTBOX_AVAILABLE_AT"), "TASK_OUTBOX", ["AVAILABLE_AT"], unique=False
    )
    op.create_index(op.f("ix_TASK_OUTBOX_CREATED_AT"), "TASK_OUTBOX", ["CREATED_AT"], unique=False)
    op.create_index(
        op.f("ix_TASK_OUTBOX_PUBLISHED_AT"), "TASK_OUTBOX", ["PUBLISHED_AT"], unique=False
    )
    op.create_table(
        "USER",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column(
            "USERNAME",
            sa.String(length=255),
            nullable=False,
            comment="UNIQUE USERNAME USED TO IDENTIFY THE USER.",
        ),
        sa.Column(
            "EMAIL",
            sa.String(length=255),
            nullable=True,
            comment="UNIQUE EMAIL ADDRESS FOR THE USER.",
        ),
        sa.Column(
            "IS_SUPERUSER",
            sa.Boolean(),
            nullable=False,
            comment="WHETHER THE USER HAS ADMINISTRATIVE PRIVILEGES.",
        ),
        sa.Column("FIRST_NAME", sa.String(length=255), nullable=True, comment="USER'S GIVEN NAME."),
        sa.Column("LAST_NAME", sa.String(length=255), nullable=True, comment="USER'S FAMILY NAME."),
        sa.Column(
            "HASHED_PASSWORD",
            sa.String(),
            nullable=False,
            comment="ONE-WAY PASSWORD HASH; A PLAINTEXT PASSWORD IS NEVER STORED.",
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("EMAIL"),
    )
    op.create_index(op.f("ix_USER_CREATED_AT"), "USER", ["CREATED_AT"], unique=False)
    op.create_index(op.f("ix_USER_USERNAME"), "USER", ["USERNAME"], unique=True)
    op.create_table(
        "AUTH_AUDIT_EVENT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("USER_ID", sa.Uuid(), nullable=True),
        sa.Column("EVENT_TYPE", sa.String(length=64), nullable=False),
        sa.Column("SUCCESS", sa.Boolean(), nullable=False),
        sa.Column("REQUEST_ID", sa.String(length=64), nullable=True),
        sa.Column("IP_ADDRESS", sa.String(length=64), nullable=True),
        sa.Column("USER_AGENT", sa.String(length=1024), nullable=True),
        sa.Column("DETAILS", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["USER_ID"],
            ["USER.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_AUTH_AUDIT_EVENT_CREATED_AT"), "AUTH_AUDIT_EVENT", ["CREATED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_AUTH_AUDIT_EVENT_EVENT_TYPE"), "AUTH_AUDIT_EVENT", ["EVENT_TYPE"], unique=False
    )
    op.create_index(
        op.f("ix_AUTH_AUDIT_EVENT_USER_ID"), "AUTH_AUDIT_EVENT", ["USER_ID"], unique=False
    )
    op.create_table(
        "AUTH_SESSION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column(
            "USER_ID", sa.Uuid(), nullable=False, comment="USER THAT OWNS THIS DEVICE SESSION."
        ),
        sa.Column(
            "FAMILY_ID",
            sa.Uuid(),
            nullable=False,
            comment="REFRESH-TOKEN ROTATION FAMILY IDENTIFIER.",
        ),
        sa.Column(
            "REFRESH_TOKEN_HASH",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 DIGEST OF THE OPAQUE REFRESH TOKEN.",
        ),
        sa.Column("DEVICE_NAME", sa.String(length=255), nullable=True),
        sa.Column("IP_ADDRESS", sa.String(length=64), nullable=True),
        sa.Column("USER_AGENT", sa.String(length=1024), nullable=True),
        sa.Column("LAST_USED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("EXPIRES_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("REVOKED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["USER_ID"],
            ["USER.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_AUTH_SESSION_CREATED_AT"), "AUTH_SESSION", ["CREATED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_AUTH_SESSION_EXPIRES_AT"), "AUTH_SESSION", ["EXPIRES_AT"], unique=False
    )
    op.create_index(op.f("ix_AUTH_SESSION_FAMILY_ID"), "AUTH_SESSION", ["FAMILY_ID"], unique=False)
    op.create_index(
        op.f("ix_AUTH_SESSION_REFRESH_TOKEN_HASH"),
        "AUTH_SESSION",
        ["REFRESH_TOKEN_HASH"],
        unique=True,
    )
    op.create_index(
        op.f("ix_AUTH_SESSION_REVOKED_AT"), "AUTH_SESSION", ["REVOKED_AT"], unique=False
    )
    op.create_index(op.f("ix_AUTH_SESSION_USER_ID"), "AUTH_SESSION", ["USER_ID"], unique=False)
    op.create_table(
        "PASSWORD_RESET_TOKEN",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column(
            "USER_ID", sa.Uuid(), nullable=False, comment="USER REQUESTING PASSWORD RECOVERY."
        ),
        sa.Column("TOKEN_HASH", sa.String(length=64), nullable=False),
        sa.Column(
            "EXPIRES_AT", sa.DateTime(timezone=True), nullable=False, comment="UTC TOKEN EXPIRY."
        ),
        sa.Column("USED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["USER_ID"],
            ["USER.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_PASSWORD_RESET_TOKEN_CREATED_AT"),
        "PASSWORD_RESET_TOKEN",
        ["CREATED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_PASSWORD_RESET_TOKEN_TOKEN_HASH"),
        "PASSWORD_RESET_TOKEN",
        ["TOKEN_HASH"],
        unique=True,
    )
    op.create_index(
        op.f("ix_PASSWORD_RESET_TOKEN_USER_ID"), "PASSWORD_RESET_TOKEN", ["USER_ID"], unique=False
    )
    op.create_table(
        "PERIODIC_TASK_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_TASK_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF TASK_NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_TASK_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF TASK_NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_QUEUE",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF QUEUE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_QUEUE",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF QUEUE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SCHEDULE_TYPE",
            sa.String(length=32),
            nullable=True,
            comment="FROM VALUE OF SCHEDULE_TYPE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SCHEDULE_TYPE",
            sa.String(length=32),
            nullable=True,
            comment="TO VALUE OF SCHEDULE_TYPE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_INTERVAL_SECONDS",
            sa.Float(),
            nullable=True,
            comment="FROM VALUE OF INTERVAL_SECONDS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_INTERVAL_SECONDS",
            sa.Float(),
            nullable=True,
            comment="TO VALUE OF INTERVAL_SECONDS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CRON_MINUTE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CRON_MINUTE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CRON_MINUTE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CRON_MINUTE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CRON_HOUR",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CRON_HOUR FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CRON_HOUR",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CRON_HOUR FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CRON_DAY_OF_WEEK",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CRON_DAY_OF_WEEK FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CRON_DAY_OF_WEEK",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CRON_DAY_OF_WEEK FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CRON_DAY_OF_MONTH",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CRON_DAY_OF_MONTH FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CRON_DAY_OF_MONTH",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CRON_DAY_OF_MONTH FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CRON_MONTH_OF_YEAR",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CRON_MONTH_OF_YEAR FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CRON_MONTH_OF_YEAR",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CRON_MONTH_OF_YEAR FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CLOCKED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF CLOCKED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CLOCKED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF CLOCKED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ARGS", sa.JSON(), nullable=True, comment="FROM VALUE OF ARGS FOR THIS CHANGE."
        ),
        sa.Column("TO_ARGS", sa.JSON(), nullable=True, comment="TO VALUE OF ARGS FOR THIS CHANGE."),
        sa.Column(
            "FROM_KWARGS", sa.JSON(), nullable=True, comment="FROM VALUE OF KWARGS FOR THIS CHANGE."
        ),
        sa.Column(
            "TO_KWARGS", sa.JSON(), nullable=True, comment="TO VALUE OF KWARGS FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_HEADERS",
            sa.JSON(),
            nullable=True,
            comment="FROM VALUE OF HEADERS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_HEADERS", sa.JSON(), nullable=True, comment="TO VALUE OF HEADERS FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_ENABLED",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF ENABLED FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ENABLED",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF ENABLED FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ONE_OFF",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF ONE_OFF FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ONE_OFF",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF ONE_OFF FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_START_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF START_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_START_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF START_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_EXPIRES_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF EXPIRES_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_EXPIRES_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF EXPIRES_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_LAST_RUN_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF LAST_RUN_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_LAST_RUN_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF LAST_RUN_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_TOTAL_RUN_COUNT",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF TOTAL_RUN_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_TOTAL_RUN_COUNT",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF TOTAL_RUN_COUNT FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"],
            ["PERIODIC_TASK.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_PERIODIC_TASK_HISTORY_CHANGED_AT"),
        "PERIODIC_TASK_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_PERIODIC_TASK_HISTORY_ENTITY_ID"),
        "PERIODIC_TASK_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_PERIODIC_TASK_HISTORY_REQUEST_ID"),
        "PERIODIC_TASK_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_PERIODIC_TASK_HISTORY_TRACE_ID"),
        "PERIODIC_TASK_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_table(
        "PERMISSION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DESCRIPTION",
            sa.Text(),
            nullable=True,
            comment="FROM VALUE OF DESCRIPTION FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DESCRIPTION",
            sa.Text(),
            nullable=True,
            comment="TO VALUE OF DESCRIPTION FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"],
            ["PERMISSION.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_PERMISSION_HISTORY_CHANGED_AT"), "PERMISSION_HISTORY", ["CHANGED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_PERMISSION_HISTORY_ENTITY_ID"), "PERMISSION_HISTORY", ["ENTITY_ID"], unique=False
    )
    op.create_index(
        op.f("ix_PERMISSION_HISTORY_REQUEST_ID"), "PERMISSION_HISTORY", ["REQUEST_ID"], unique=False
    )
    op.create_index(
        op.f("ix_PERMISSION_HISTORY_TRACE_ID"), "PERMISSION_HISTORY", ["TRACE_ID"], unique=False
    )
    op.create_table(
        "REPORT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column(
            "OWNER_ID",
            sa.Uuid(),
            nullable=False,
            comment="USER THAT REQUESTED AND OWNS THE REPORT.",
        ),
        sa.Column("DEFINITION_KEY", sa.String(length=100), nullable=False),
        sa.Column("DEFINITION_VERSION", sa.Integer(), nullable=False),
        sa.Column(
            "STATUS", sa.String(length=20), nullable=False, comment="REPORT LIFECYCLE STATUS."
        ),
        sa.Column("FILTERS", sa.JSON(), nullable=False),
        sa.Column("SORT_ORDERS", sa.JSON(), nullable=False),
        sa.Column("LANGUAGE", sa.String(length=10), nullable=False),
        sa.Column("ROW_COUNT", sa.Integer(), nullable=True),
        sa.Column("EXPORTED_ROW_COUNT", sa.Integer(), nullable=False),
        sa.Column("MAX_ROWS", sa.Integer(), nullable=False),
        sa.Column("CHUNK_SIZE", sa.Integer(), nullable=False),
        sa.Column("PARALLELISM", sa.Integer(), nullable=False),
        sa.Column("PRIORITY", sa.Integer(), nullable=False),
        sa.Column("TASK_ID", sa.String(length=255), nullable=False),
        sa.Column("STORAGE_KEY", sa.String(length=1024), nullable=True),
        sa.Column("FILE_NAME", sa.String(length=255), nullable=True),
        sa.Column("CONTENT_TYPE", sa.String(length=255), nullable=True),
        sa.Column("FILE_SIZE", sa.BigInteger(), nullable=True),
        sa.Column("CHECKSUM_SHA256", sa.String(length=64), nullable=True),
        sa.Column(
            "ZIP_PASSWORD",
            sa.String(length=255),
            nullable=True,
            comment="PASSWORD FOR THE AES-ENCRYPTED ARCHIVE; REDACTED FROM HISTORY.",
        ),
        sa.Column("STARTED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("COMPLETED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("EXPIRES_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ERROR_CODE", sa.String(length=255), nullable=True),
        sa.Column("ERROR_MESSAGE", sa.Text(), nullable=True),
        sa.Column("ATTEMPT_COUNT", sa.Integer(), nullable=False),
        sa.Column("DOWNLOAD_COUNT", sa.Integer(), nullable=False),
        sa.Column("LAST_DOWNLOADED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('"CHUNK_SIZE" > 0', name="ck_report_chunk_size"),
        sa.CheckConstraint('"EXPORTED_ROW_COUNT" >= 0', name="ck_report_exported_row_count"),
        sa.CheckConstraint('"MAX_ROWS" > 0', name="ck_report_max_rows"),
        sa.CheckConstraint('"PARALLELISM" > 0', name="ck_report_parallelism"),
        sa.CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_report_priority"),
        sa.CheckConstraint('"ROW_COUNT" IS NULL OR "ROW_COUNT" >= 0', name="ck_report_row_count"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('PENDING', 'PROCESSING', 'READY', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="ck_report_status",
        ),
        sa.ForeignKeyConstraint(["OWNER_ID"], ["USER.ID"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("STORAGE_KEY"),
    )
    op.create_index(op.f("ix_REPORT_CREATED_AT"), "REPORT", ["CREATED_AT"], unique=False)
    op.create_index(op.f("ix_REPORT_DEFINITION_KEY"), "REPORT", ["DEFINITION_KEY"], unique=False)
    op.create_index(op.f("ix_REPORT_EXPIRES_AT"), "REPORT", ["EXPIRES_AT"], unique=False)
    op.create_index(op.f("ix_REPORT_OWNER_ID"), "REPORT", ["OWNER_ID"], unique=False)
    op.create_index(
        "ix_REPORT_OWNER_CREATED_AT", "REPORT", ["OWNER_ID", "CREATED_AT"], unique=False
    )
    op.create_index("ix_REPORT_OWNER_STATUS", "REPORT", ["OWNER_ID", "STATUS"], unique=False)
    op.create_index(op.f("ix_REPORT_STATUS"), "REPORT", ["STATUS"], unique=False)
    op.create_index(op.f("ix_REPORT_TASK_ID"), "REPORT", ["TASK_ID"], unique=True)
    op.create_table(
        "ROLE_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DESCRIPTION",
            sa.Text(),
            nullable=True,
            comment="FROM VALUE OF DESCRIPTION FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DESCRIPTION",
            sa.Text(),
            nullable=True,
            comment="TO VALUE OF DESCRIPTION FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"],
            ["ROLE.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_ROLE_HISTORY_CHANGED_AT"), "ROLE_HISTORY", ["CHANGED_AT"], unique=False
    )
    op.create_index(op.f("ix_ROLE_HISTORY_ENTITY_ID"), "ROLE_HISTORY", ["ENTITY_ID"], unique=False)
    op.create_index(
        op.f("ix_ROLE_HISTORY_REQUEST_ID"), "ROLE_HISTORY", ["REQUEST_ID"], unique=False
    )
    op.create_index(op.f("ix_ROLE_HISTORY_TRACE_ID"), "ROLE_HISTORY", ["TRACE_ID"], unique=False)
    op.create_table(
        "ROLE_PERMISSION",
        sa.Column("ROLE_ID", sa.Uuid(), nullable=False),
        sa.Column("PERMISSION_ID", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["PERMISSION_ID"], ["PERMISSION.ID"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ROLE_ID"], ["ROLE.ID"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ROLE_ID", "PERMISSION_ID"),
    )
    op.create_table(
        "USER_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_USERNAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF USERNAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_USERNAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF USERNAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_EMAIL",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF EMAIL FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_EMAIL",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF EMAIL FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_SUPERUSER",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_SUPERUSER FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_SUPERUSER",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_SUPERUSER FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_FIRST_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF FIRST_NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_FIRST_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF FIRST_NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_LAST_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF LAST_NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_LAST_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF LAST_NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_HASHED_PASSWORD",
            sa.String(),
            nullable=True,
            comment="FROM VALUE OF HASHED_PASSWORD FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_HASHED_PASSWORD",
            sa.String(),
            nullable=True,
            comment="TO VALUE OF HASHED_PASSWORD FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"],
            ["USER.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_USER_HISTORY_CHANGED_AT"), "USER_HISTORY", ["CHANGED_AT"], unique=False
    )
    op.create_index(op.f("ix_USER_HISTORY_ENTITY_ID"), "USER_HISTORY", ["ENTITY_ID"], unique=False)
    op.create_index(
        op.f("ix_USER_HISTORY_REQUEST_ID"), "USER_HISTORY", ["REQUEST_ID"], unique=False
    )
    op.create_index(op.f("ix_USER_HISTORY_TRACE_ID"), "USER_HISTORY", ["TRACE_ID"], unique=False)
    op.create_table(
        "USER_ROLE",
        sa.Column("USER_ID", sa.Uuid(), nullable=False),
        sa.Column("ROLE_ID", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["ROLE_ID"], ["ROLE.ID"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["USER_ID"], ["USER.ID"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("USER_ID", "ROLE_ID"),
    )
    op.create_table(
        "USER_UPLOAD",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("USER_ID", sa.Uuid(), nullable=False, comment="USER THAT OWNS THE UPLOAD."),
        sa.Column("KIND", sa.String(length=16), nullable=False, comment="UPLOAD KIND."),
        sa.Column(
            "OBJECT_KEY", sa.String(length=1024), nullable=False, comment="PRIVATE S3 OBJECT KEY."
        ),
        sa.Column(
            "ORIGINAL_FILENAME",
            sa.String(length=255),
            nullable=False,
            comment="CLIENT-PROVIDED FILENAME.",
        ),
        sa.Column(
            "CONTENT_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="VALIDATED STORED MEDIA TYPE.",
        ),
        sa.Column(
            "SIZE_BYTES", sa.BigInteger(), nullable=False, comment="STORED OBJECT SIZE IN BYTES."
        ),
        sa.Column(
            "SHA256",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 DIGEST OF THE STORED BYTES.",
        ),
        sa.Column("WIDTH", sa.Integer(), nullable=True, comment="IMAGE WIDTH IN PIXELS."),
        sa.Column("HEIGHT", sa.Integer(), nullable=True, comment="IMAGE HEIGHT IN PIXELS."),
        sa.ForeignKeyConstraint(
            ["USER_ID"],
            ["USER.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("OBJECT_KEY"),
    )
    op.create_index(op.f("ix_USER_UPLOAD_CREATED_AT"), "USER_UPLOAD", ["CREATED_AT"], unique=False)
    op.create_index(op.f("ix_USER_UPLOAD_KIND"), "USER_UPLOAD", ["KIND"], unique=False)
    op.create_index(op.f("ix_USER_UPLOAD_SHA256"), "USER_UPLOAD", ["SHA256"], unique=False)
    op.create_index(op.f("ix_USER_UPLOAD_USER_ID"), "USER_UPLOAD", ["USER_ID"], unique=False)
    op.create_table(
        "REPORT_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_OWNER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF OWNER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_OWNER_ID", sa.Uuid(), nullable=True, comment="TO VALUE OF OWNER_ID FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_DEFINITION_KEY",
            sa.String(length=100),
            nullable=True,
            comment="FROM VALUE OF DEFINITION_KEY FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DEFINITION_KEY",
            sa.String(length=100),
            nullable=True,
            comment="TO VALUE OF DEFINITION_KEY FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DEFINITION_VERSION",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF DEFINITION_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DEFINITION_VERSION",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF DEFINITION_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=20),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=20),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_FILTERS",
            sa.JSON(),
            nullable=True,
            comment="FROM VALUE OF FILTERS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_FILTERS", sa.JSON(), nullable=True, comment="TO VALUE OF FILTERS FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_SORT_ORDERS",
            sa.JSON(),
            nullable=True,
            comment="FROM VALUE OF SORT_ORDERS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SORT_ORDERS",
            sa.JSON(),
            nullable=True,
            comment="TO VALUE OF SORT_ORDERS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_LANGUAGE",
            sa.String(length=10),
            nullable=True,
            comment="FROM VALUE OF LANGUAGE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_LANGUAGE",
            sa.String(length=10),
            nullable=True,
            comment="TO VALUE OF LANGUAGE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ROW_COUNT",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF ROW_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ROW_COUNT",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF ROW_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_EXPORTED_ROW_COUNT",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF EXPORTED_ROW_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_EXPORTED_ROW_COUNT",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF EXPORTED_ROW_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_MAX_ROWS",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF MAX_ROWS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_MAX_ROWS",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF MAX_ROWS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CHUNK_SIZE",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF CHUNK_SIZE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CHUNK_SIZE",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF CHUNK_SIZE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PARALLELISM",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF PARALLELISM FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PARALLELISM",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF PARALLELISM FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PRIORITY",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF PRIORITY FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PRIORITY",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF PRIORITY FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_TASK_ID",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF TASK_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_TASK_ID",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF TASK_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_STORAGE_KEY",
            sa.String(length=1024),
            nullable=True,
            comment="FROM VALUE OF STORAGE_KEY FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STORAGE_KEY",
            sa.String(length=1024),
            nullable=True,
            comment="TO VALUE OF STORAGE_KEY FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_FILE_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF FILE_NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_FILE_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF FILE_NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CONTENT_TYPE",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF CONTENT_TYPE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CONTENT_TYPE",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF CONTENT_TYPE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_FILE_SIZE",
            sa.BigInteger(),
            nullable=True,
            comment="FROM VALUE OF FILE_SIZE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_FILE_SIZE",
            sa.BigInteger(),
            nullable=True,
            comment="TO VALUE OF FILE_SIZE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CHECKSUM_SHA256",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CHECKSUM_SHA256 FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CHECKSUM_SHA256",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CHECKSUM_SHA256 FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ZIP_PASSWORD",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF ZIP_PASSWORD FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ZIP_PASSWORD",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF ZIP_PASSWORD FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_STARTED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF STARTED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STARTED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF STARTED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_COMPLETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF COMPLETED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_COMPLETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF COMPLETED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_EXPIRES_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF EXPIRES_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_EXPIRES_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF EXPIRES_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ERROR_CODE",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF ERROR_CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ERROR_CODE",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF ERROR_CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ERROR_MESSAGE",
            sa.Text(),
            nullable=True,
            comment="FROM VALUE OF ERROR_MESSAGE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ERROR_MESSAGE",
            sa.Text(),
            nullable=True,
            comment="TO VALUE OF ERROR_MESSAGE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ATTEMPT_COUNT",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF ATTEMPT_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ATTEMPT_COUNT",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF ATTEMPT_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DOWNLOAD_COUNT",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF DOWNLOAD_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DOWNLOAD_COUNT",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF DOWNLOAD_COUNT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_LAST_DOWNLOADED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF LAST_DOWNLOADED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_LAST_DOWNLOADED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF LAST_DOWNLOADED_AT FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"],
            ["REPORT.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_REPORT_HISTORY_CHANGED_AT"), "REPORT_HISTORY", ["CHANGED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_REPORT_HISTORY_ENTITY_ID"), "REPORT_HISTORY", ["ENTITY_ID"], unique=False
    )
    op.create_index(
        op.f("ix_REPORT_HISTORY_REQUEST_ID"), "REPORT_HISTORY", ["REQUEST_ID"], unique=False
    )
    op.create_index(
        op.f("ix_REPORT_HISTORY_TRACE_ID"), "REPORT_HISTORY", ["TRACE_ID"], unique=False
    )
    op.create_table(
        "USER_UPLOAD_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_USER_ID", sa.Uuid(), nullable=True, comment="TO VALUE OF USER_ID FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_KIND",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF KIND FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_KIND",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF KIND FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_OBJECT_KEY",
            sa.String(length=1024),
            nullable=True,
            comment="FROM VALUE OF OBJECT_KEY FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_OBJECT_KEY",
            sa.String(length=1024),
            nullable=True,
            comment="TO VALUE OF OBJECT_KEY FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ORIGINAL_FILENAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF ORIGINAL_FILENAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ORIGINAL_FILENAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF ORIGINAL_FILENAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CONTENT_TYPE",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF CONTENT_TYPE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CONTENT_TYPE",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF CONTENT_TYPE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SIZE_BYTES",
            sa.BigInteger(),
            nullable=True,
            comment="FROM VALUE OF SIZE_BYTES FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SIZE_BYTES",
            sa.BigInteger(),
            nullable=True,
            comment="TO VALUE OF SIZE_BYTES FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SHA256",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF SHA256 FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SHA256",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF SHA256 FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_WIDTH",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF WIDTH FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_WIDTH", sa.Integer(), nullable=True, comment="TO VALUE OF WIDTH FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_HEIGHT",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF HEIGHT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_HEIGHT", sa.Integer(), nullable=True, comment="TO VALUE OF HEIGHT FOR THIS CHANGE."
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"],
            ["USER_UPLOAD.ID"],
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_USER_UPLOAD_HISTORY_CHANGED_AT"),
        "USER_UPLOAD_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_USER_UPLOAD_HISTORY_ENTITY_ID"), "USER_UPLOAD_HISTORY", ["ENTITY_ID"], unique=False
    )
    op.create_index(
        op.f("ix_USER_UPLOAD_HISTORY_REQUEST_ID"),
        "USER_UPLOAD_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_USER_UPLOAD_HISTORY_TRACE_ID"), "USER_UPLOAD_HISTORY", ["TRACE_ID"], unique=False
    )
    _create_initial_admin()
    _create_report_cleanup_schedule()


def _downgrade_core() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_USER_UPLOAD_HISTORY_TRACE_ID"), table_name="USER_UPLOAD_HISTORY")
    op.drop_index(op.f("ix_USER_UPLOAD_HISTORY_REQUEST_ID"), table_name="USER_UPLOAD_HISTORY")
    op.drop_index(op.f("ix_USER_UPLOAD_HISTORY_ENTITY_ID"), table_name="USER_UPLOAD_HISTORY")
    op.drop_index(op.f("ix_USER_UPLOAD_HISTORY_CHANGED_AT"), table_name="USER_UPLOAD_HISTORY")
    op.drop_table("USER_UPLOAD_HISTORY")
    op.drop_index(op.f("ix_REPORT_HISTORY_TRACE_ID"), table_name="REPORT_HISTORY")
    op.drop_index(op.f("ix_REPORT_HISTORY_REQUEST_ID"), table_name="REPORT_HISTORY")
    op.drop_index(op.f("ix_REPORT_HISTORY_ENTITY_ID"), table_name="REPORT_HISTORY")
    op.drop_index(op.f("ix_REPORT_HISTORY_CHANGED_AT"), table_name="REPORT_HISTORY")
    op.drop_table("REPORT_HISTORY")
    op.drop_index(op.f("ix_USER_UPLOAD_USER_ID"), table_name="USER_UPLOAD")
    op.drop_index(op.f("ix_USER_UPLOAD_SHA256"), table_name="USER_UPLOAD")
    op.drop_index(op.f("ix_USER_UPLOAD_KIND"), table_name="USER_UPLOAD")
    op.drop_index(op.f("ix_USER_UPLOAD_CREATED_AT"), table_name="USER_UPLOAD")
    op.drop_table("USER_UPLOAD")
    op.drop_table("USER_ROLE")
    op.drop_index(op.f("ix_USER_HISTORY_TRACE_ID"), table_name="USER_HISTORY")
    op.drop_index(op.f("ix_USER_HISTORY_REQUEST_ID"), table_name="USER_HISTORY")
    op.drop_index(op.f("ix_USER_HISTORY_ENTITY_ID"), table_name="USER_HISTORY")
    op.drop_index(op.f("ix_USER_HISTORY_CHANGED_AT"), table_name="USER_HISTORY")
    op.drop_table("USER_HISTORY")
    op.drop_table("ROLE_PERMISSION")
    op.drop_index(op.f("ix_ROLE_HISTORY_TRACE_ID"), table_name="ROLE_HISTORY")
    op.drop_index(op.f("ix_ROLE_HISTORY_REQUEST_ID"), table_name="ROLE_HISTORY")
    op.drop_index(op.f("ix_ROLE_HISTORY_ENTITY_ID"), table_name="ROLE_HISTORY")
    op.drop_index(op.f("ix_ROLE_HISTORY_CHANGED_AT"), table_name="ROLE_HISTORY")
    op.drop_table("ROLE_HISTORY")
    op.drop_index(op.f("ix_REPORT_TASK_ID"), table_name="REPORT")
    op.drop_index(op.f("ix_REPORT_STATUS"), table_name="REPORT")
    op.drop_index(op.f("ix_REPORT_OWNER_ID"), table_name="REPORT")
    op.drop_index("ix_REPORT_OWNER_STATUS", table_name="REPORT")
    op.drop_index("ix_REPORT_OWNER_CREATED_AT", table_name="REPORT")
    op.drop_index(op.f("ix_REPORT_EXPIRES_AT"), table_name="REPORT")
    op.drop_index(op.f("ix_REPORT_DEFINITION_KEY"), table_name="REPORT")
    op.drop_index(op.f("ix_REPORT_CREATED_AT"), table_name="REPORT")
    op.drop_table("REPORT")
    op.drop_index(op.f("ix_PERMISSION_HISTORY_TRACE_ID"), table_name="PERMISSION_HISTORY")
    op.drop_index(op.f("ix_PERMISSION_HISTORY_REQUEST_ID"), table_name="PERMISSION_HISTORY")
    op.drop_index(op.f("ix_PERMISSION_HISTORY_ENTITY_ID"), table_name="PERMISSION_HISTORY")
    op.drop_index(op.f("ix_PERMISSION_HISTORY_CHANGED_AT"), table_name="PERMISSION_HISTORY")
    op.drop_table("PERMISSION_HISTORY")
    op.drop_index(op.f("ix_PERIODIC_TASK_HISTORY_TRACE_ID"), table_name="PERIODIC_TASK_HISTORY")
    op.drop_index(op.f("ix_PERIODIC_TASK_HISTORY_REQUEST_ID"), table_name="PERIODIC_TASK_HISTORY")
    op.drop_index(op.f("ix_PERIODIC_TASK_HISTORY_ENTITY_ID"), table_name="PERIODIC_TASK_HISTORY")
    op.drop_index(op.f("ix_PERIODIC_TASK_HISTORY_CHANGED_AT"), table_name="PERIODIC_TASK_HISTORY")
    op.drop_table("PERIODIC_TASK_HISTORY")
    op.drop_index(op.f("ix_PASSWORD_RESET_TOKEN_USER_ID"), table_name="PASSWORD_RESET_TOKEN")
    op.drop_index(op.f("ix_PASSWORD_RESET_TOKEN_TOKEN_HASH"), table_name="PASSWORD_RESET_TOKEN")
    op.drop_index(op.f("ix_PASSWORD_RESET_TOKEN_CREATED_AT"), table_name="PASSWORD_RESET_TOKEN")
    op.drop_table("PASSWORD_RESET_TOKEN")
    op.drop_index(op.f("ix_AUTH_SESSION_USER_ID"), table_name="AUTH_SESSION")
    op.drop_index(op.f("ix_AUTH_SESSION_REVOKED_AT"), table_name="AUTH_SESSION")
    op.drop_index(op.f("ix_AUTH_SESSION_REFRESH_TOKEN_HASH"), table_name="AUTH_SESSION")
    op.drop_index(op.f("ix_AUTH_SESSION_FAMILY_ID"), table_name="AUTH_SESSION")
    op.drop_index(op.f("ix_AUTH_SESSION_EXPIRES_AT"), table_name="AUTH_SESSION")
    op.drop_index(op.f("ix_AUTH_SESSION_CREATED_AT"), table_name="AUTH_SESSION")
    op.drop_table("AUTH_SESSION")
    op.drop_index(op.f("ix_AUTH_AUDIT_EVENT_USER_ID"), table_name="AUTH_AUDIT_EVENT")
    op.drop_index(op.f("ix_AUTH_AUDIT_EVENT_EVENT_TYPE"), table_name="AUTH_AUDIT_EVENT")
    op.drop_index(op.f("ix_AUTH_AUDIT_EVENT_CREATED_AT"), table_name="AUTH_AUDIT_EVENT")
    op.drop_table("AUTH_AUDIT_EVENT")
    op.drop_index(op.f("ix_USER_USERNAME"), table_name="USER")
    op.drop_index(op.f("ix_USER_CREATED_AT"), table_name="USER")
    op.drop_table("USER")
    op.drop_index(op.f("ix_TASK_OUTBOX_PUBLISHED_AT"), table_name="TASK_OUTBOX")
    op.drop_index(op.f("ix_TASK_OUTBOX_CREATED_AT"), table_name="TASK_OUTBOX")
    op.drop_index(op.f("ix_TASK_OUTBOX_AVAILABLE_AT"), table_name="TASK_OUTBOX")
    op.drop_table("TASK_OUTBOX")
    op.drop_index(op.f("ix_TASK_IDEMPOTENCY_KEY"), table_name="TASK_IDEMPOTENCY")
    op.drop_index(op.f("ix_TASK_IDEMPOTENCY_EXPIRES_AT"), table_name="TASK_IDEMPOTENCY")
    op.drop_index(op.f("ix_TASK_IDEMPOTENCY_CREATED_AT"), table_name="TASK_IDEMPOTENCY")
    op.drop_table("TASK_IDEMPOTENCY")
    op.drop_index(op.f("ix_TASK_EXECUTION_TASK_NAME"), table_name="TASK_EXECUTION")
    op.drop_index(op.f("ix_TASK_EXECUTION_TASK_ID"), table_name="TASK_EXECUTION")
    op.drop_index(op.f("ix_TASK_EXECUTION_STATUS"), table_name="TASK_EXECUTION")
    op.drop_index(op.f("ix_TASK_EXECUTION_CREATED_AT"), table_name="TASK_EXECUTION")
    op.drop_table("TASK_EXECUTION")
    op.drop_index(op.f("ix_SCHEDULER_LEASE_OWNER_ID"), table_name="SCHEDULER_LEASE")
    op.drop_index(op.f("ix_SCHEDULER_LEASE_NAME"), table_name="SCHEDULER_LEASE")
    op.drop_index(op.f("ix_SCHEDULER_LEASE_EXPIRES_AT"), table_name="SCHEDULER_LEASE")
    op.drop_index(op.f("ix_SCHEDULER_LEASE_CREATED_AT"), table_name="SCHEDULER_LEASE")
    op.drop_table("SCHEDULER_LEASE")
    op.drop_index(op.f("ix_ROLE_NAME"), table_name="ROLE")
    op.drop_index(op.f("ix_ROLE_CREATED_AT"), table_name="ROLE")
    op.drop_table("ROLE")
    op.drop_index(op.f("ix_PERMISSION_NAME"), table_name="PERMISSION")
    op.drop_index(op.f("ix_PERMISSION_CREATED_AT"), table_name="PERMISSION")
    op.drop_table("PERMISSION")
    op.drop_index(op.f("ix_PERIODIC_TASK_ENABLED"), table_name="PERIODIC_TASK")
    op.drop_index(op.f("ix_PERIODIC_TASK_CREATED_AT"), table_name="PERIODIC_TASK")
    op.drop_table("PERIODIC_TASK")
    op.drop_index(op.f("ix_LOGIN_FAILURE_LOCKED_UNTIL"), table_name="LOGIN_FAILURE")
    op.drop_index(op.f("ix_LOGIN_FAILURE_IDENTIFIER"), table_name="LOGIN_FAILURE")
    op.drop_index(op.f("ix_LOGIN_FAILURE_CREATED_AT"), table_name="LOGIN_FAILURE")
    op.drop_table("LOGIN_FAILURE")


# Work groups


def _upgrade_work_groups() -> None:
    op.create_table(
        "WORK_GROUP",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(64), nullable=False),
        sa.Column("NAME", sa.String(255), nullable=False),
        sa.Column("DESCRIPTION", sa.String(1024)),
        sa.Column("IS_ACTIVE", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("ID"),
        sa.CheckConstraint('length("CODE") > 0', name="ck_WORK_GROUP_code_nonempty"),
        sa.CheckConstraint('length("NAME") > 0', name="ck_WORK_GROUP_name_nonempty"),
    )
    op.create_index("ix_WORK_GROUP_CREATED_AT", "WORK_GROUP", ["CREATED_AT"])
    op.create_index(
        "uq_WORK_GROUP_CODE_active",
        "WORK_GROUP",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_index(
        "ix_WORK_GROUP_active_code",
        "WORK_GROUP",
        ["IS_ACTIVE", "CODE"],
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )

    op.create_table(
        "WORK_GROUP_MEMBER",
        sa.Column("WORK_GROUP_ID", sa.Uuid(), nullable=False),
        sa.Column("USER_ID", sa.Uuid(), nullable=False),
        sa.Column("IS_ACTIVE", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("JOINED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("LEFT_AT", sa.DateTime(timezone=True)),
        sa.Column("ADDED_BY_USER_ID", sa.Uuid()),
        sa.Column("UPDATED_AT", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("WORK_GROUP_ID", "USER_ID"),
        sa.ForeignKeyConstraint(
            ["WORK_GROUP_ID"], ["WORK_GROUP.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["ADDED_BY_USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.CheckConstraint(
            '("IS_ACTIVE" AND "LEFT_AT" IS NULL) OR NOT "IS_ACTIVE"',
            name="ck_WORK_GROUP_MEMBER_lifecycle",
        ),
    )
    op.create_index(
        "ix_WORK_GROUP_MEMBER_user_active_group",
        "WORK_GROUP_MEMBER",
        ["USER_ID", "IS_ACTIVE", "WORK_GROUP_ID"],
    )
    op.create_index("ix_WORK_GROUP_MEMBER_added_by", "WORK_GROUP_MEMBER", ["ADDED_BY_USER_ID"])

    history = [
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column("REQUEST_ID", sa.String(64), comment="REQUEST CORRELATION ID."),
        sa.Column("TRACE_ID", sa.String(64), comment="OPENTELEMETRY TRACE ID."),
        sa.Column("REASON", sa.String(1024), comment="OPTIONAL BUSINESS REASON FOR THE CHANGE."),
        sa.Column("SOURCE_IP", sa.String(64), comment="ORIGINATING CLIENT IP WHEN AVAILABLE."),
        sa.Column("USER_AGENT", sa.String(1024), comment="ORIGINATING USER AGENT WHEN AVAILABLE."),
    ]
    for name, column_type in (
        ("CODE", sa.String(64)),
        ("NAME", sa.String(255)),
        ("DESCRIPTION", sa.String(1024)),
        ("IS_ACTIVE", sa.Boolean()),
    ):
        history.extend(
            (
                sa.Column(
                    f"FROM_{name}", column_type, comment=f"FROM VALUE OF {name} FOR THIS CHANGE."
                ),
                sa.Column(
                    f"TO_{name}", column_type, comment=f"TO VALUE OF {name} FOR THIS CHANGE."
                ),
            )
        )
    op.create_table(
        "WORK_GROUP_HISTORY",
        *history,
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["WORK_GROUP.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
    )
    op.create_index("ix_WORK_GROUP_HISTORY_ENTITY_ID", "WORK_GROUP_HISTORY", ["ENTITY_ID"])
    op.create_index("ix_WORK_GROUP_HISTORY_CHANGED_AT", "WORK_GROUP_HISTORY", ["CHANGED_AT"])
    op.create_index("ix_WORK_GROUP_HISTORY_REQUEST_ID", "WORK_GROUP_HISTORY", ["REQUEST_ID"])
    op.create_index("ix_WORK_GROUP_HISTORY_TRACE_ID", "WORK_GROUP_HISTORY", ["TRACE_ID"])
    op.create_index(
        "ix_WORK_GROUP_HISTORY_entity_changed", "WORK_GROUP_HISTORY", ["ENTITY_ID", "CHANGED_AT"]
    )


def _downgrade_work_groups() -> None:
    op.drop_index("ix_WORK_GROUP_HISTORY_entity_changed", table_name="WORK_GROUP_HISTORY")
    op.drop_index("ix_WORK_GROUP_HISTORY_TRACE_ID", table_name="WORK_GROUP_HISTORY")
    op.drop_index("ix_WORK_GROUP_HISTORY_REQUEST_ID", table_name="WORK_GROUP_HISTORY")
    op.drop_index("ix_WORK_GROUP_HISTORY_CHANGED_AT", table_name="WORK_GROUP_HISTORY")
    op.drop_index("ix_WORK_GROUP_HISTORY_ENTITY_ID", table_name="WORK_GROUP_HISTORY")
    op.drop_table("WORK_GROUP_HISTORY")
    op.drop_index("ix_WORK_GROUP_MEMBER_added_by", table_name="WORK_GROUP_MEMBER")
    op.drop_index("ix_WORK_GROUP_MEMBER_user_active_group", table_name="WORK_GROUP_MEMBER")
    op.drop_table("WORK_GROUP_MEMBER")
    op.drop_index("ix_WORK_GROUP_active_code", table_name="WORK_GROUP")
    op.drop_index("uq_WORK_GROUP_CODE_active", table_name="WORK_GROUP")
    op.drop_index("ix_WORK_GROUP_CREATED_AT", table_name="WORK_GROUP")
    op.drop_table("WORK_GROUP")


# Versioned step types and typed ports


def _seed_catalog() -> None:
    payload = json.dumps(_INITIAL_CATALOG)
    op.execute(
        sa.text("""
        WITH seeds AS (
            SELECT value AS data FROM jsonb_array_elements(CAST(:payload AS jsonb))
        ), roots AS (
            INSERT INTO "STEP_TYPE" ("CODE", "NAME", "IS_ENABLED", "VERSION", "CREATED_AT")
            SELECT data->>'code', data->>'name', true, 1, now() FROM seeds
            RETURNING "ID", "CODE", "NAME"
        ), history AS (
            INSERT INTO "STEP_TYPE_HISTORY"
                ("ENTITY_ID", "MODIFIER_TYPE", "MODIFIER_ID", "CHANGED_AT", "OPERATION",
                 "TO_CODE", "TO_NAME", "TO_IS_ENABLED")
            SELECT "ID", 'system', 'migration:b8d982c92b94', now(), 'insert',
                   "CODE", "NAME", true FROM roots
        ), versions AS (
            INSERT INTO "STEP_TYPE_VERSION"
                ("STEP_TYPE_ID", "NUMBER", "STATUS", "HANDLER_KEY", "HANDLER_VERSION",
                 "EXECUTION_MODE", "CONFIG_SCHEMA", "PUBLISHED_AT", "VERSION", "CREATED_AT")
            SELECT roots."ID", 1, 'PUBLISHED', data->>'handler_key', data->>'handler_version',
                   data->>'execution_mode', data->'config_schema', now(), 1, now()
            FROM roots JOIN seeds ON roots."CODE" = data->>'code'
            RETURNING "ID", "HANDLER_KEY"
        )
        INSERT INTO "STEP_TYPE_PORT"
            ("STEP_TYPE_VERSION_ID", "DIRECTION", "PORT_KEY", "VALUE_SCHEMA",
             "REQUIRED", "NULLABLE", "CARDINALITY", "CREATED_AT")
        SELECT versions."ID", port->>'direction', port->>'port_key', port->'value_schema',
               (port->>'required')::boolean, (port->>'nullable')::boolean,
               port->>'cardinality', now()
        FROM versions JOIN seeds ON versions."HANDLER_KEY" = data->>'handler_key'
        CROSS JOIN LATERAL jsonb_array_elements(data->'ports') AS port
    """).bindparams(sa.bindparam("payload", value=payload, type_=sa.Text()))
    )


def _install_immutability_versioned_step_types_and_typed_ports() -> None:
    op.execute("""
        CREATE FUNCTION protect_step_type_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW."STATUS" <> 'DRAFT' THEN
                    RAISE EXCEPTION 'New step type versions must be drafts' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD."STATUS" <> 'DRAFT' THEN
                IF TG_OP = 'UPDATE' AND OLD."STATUS" = 'PUBLISHED'
                    AND NEW."STATUS" = 'RETIRED'
                    AND (to_jsonb(NEW) - ARRAY['STATUS', 'VERSION', 'UPDATED_AT']) =
                        (to_jsonb(OLD) - ARRAY['STATUS', 'VERSION', 'UPDATED_AT']) THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Published step type version is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            IF NEW."STATUS" = 'RETIRED' THEN
                RAISE EXCEPTION 'Draft cannot be retired' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""CREATE TRIGGER step_type_version_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON "STEP_TYPE_VERSION"
        FOR EACH ROW EXECUTE FUNCTION protect_step_type_version()""")
    op.execute("""
        CREATE FUNCTION protect_step_type_port() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_id uuid; parent_status text;
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW."STEP_TYPE_VERSION_ID" <> OLD."STEP_TYPE_VERSION_ID" THEN
                RAISE EXCEPTION 'Port parent is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN parent_id := OLD."STEP_TYPE_VERSION_ID";
            ELSE parent_id := NEW."STEP_TYPE_VERSION_ID"; END IF;
            SELECT "STATUS" INTO parent_status FROM "STEP_TYPE_VERSION"
                WHERE "ID" = parent_id FOR UPDATE;
            IF parent_status <> 'DRAFT' THEN
                RAISE EXCEPTION 'Published step type ports are immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""CREATE TRIGGER step_type_port_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON "STEP_TYPE_PORT"
        FOR EACH ROW EXECUTE FUNCTION protect_step_type_port()""")


def _upgrade_versioned_step_types_and_typed_ports() -> None:
    """Upgrade schema."""
    op.create_table(
        "STEP_TYPE",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("IS_ENABLED", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint('length("CODE") > 0', name="ck_STEP_TYPE_code"),
        sa.CheckConstraint('length("NAME") > 0', name="ck_STEP_TYPE_name"),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(op.f("ix_STEP_TYPE_CREATED_AT"), "STEP_TYPE", ["CREATED_AT"], unique=False)
    op.create_index("ix_STEP_TYPE_enabled_code", "STEP_TYPE", ["IS_ENABLED", "CODE"], unique=False)
    op.create_index(
        "uq_STEP_TYPE_CODE_active",
        "STEP_TYPE",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "STEP_TYPE_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_ENABLED",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_ENABLED FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_ENABLED",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_ENABLED FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["STEP_TYPE.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_STEP_TYPE_HISTORY_CHANGED_AT"), "STEP_TYPE_HISTORY", ["CHANGED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_STEP_TYPE_HISTORY_ENTITY_ID"), "STEP_TYPE_HISTORY", ["ENTITY_ID"], unique=False
    )
    op.create_index(
        op.f("ix_STEP_TYPE_HISTORY_REQUEST_ID"), "STEP_TYPE_HISTORY", ["REQUEST_ID"], unique=False
    )
    op.create_index(
        op.f("ix_STEP_TYPE_HISTORY_TRACE_ID"), "STEP_TYPE_HISTORY", ["TRACE_ID"], unique=False
    )
    op.create_table(
        "STEP_TYPE_VERSION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("STEP_TYPE_ID", sa.Uuid(), nullable=False),
        sa.Column("NUMBER", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("HANDLER_KEY", sa.String(length=64), nullable=False),
        sa.Column("HANDLER_VERSION", sa.String(length=64), nullable=False),
        sa.Column("EXECUTION_MODE", sa.String(length=16), nullable=False),
        sa.Column("CONFIG_SCHEMA", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("PUBLISHED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "\"EXECUTION_MODE\" IN ('SYNC', 'HUMAN', 'BACKGROUND', 'WAIT')",
            name="ck_STEP_TYPE_VERSION_mode",
        ),
        sa.CheckConstraint('"NUMBER" > 0', name="ck_STEP_TYPE_VERSION_number"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="ck_STEP_TYPE_VERSION_status"
        ),
        sa.CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "PUBLISHED_AT" IS NULL) OR ("STATUS" IN (\'PUBLISHED\', \'RETIRED\') AND "PUBLISHED_AT" IS NOT NULL)',
            name="ck_STEP_TYPE_VERSION_publication",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(\"CONFIG_SCHEMA\") = 'object'", name="ck_STEP_TYPE_VERSION_schema"
        ),
        sa.ForeignKeyConstraint(
            ["STEP_TYPE_ID"], ["STEP_TYPE.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("STEP_TYPE_ID", "NUMBER", name="uq_STEP_TYPE_VERSION_number"),
    )
    op.create_index(
        op.f("ix_STEP_TYPE_VERSION_CREATED_AT"), "STEP_TYPE_VERSION", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_STEP_TYPE_VERSION_type_status",
        "STEP_TYPE_VERSION",
        ["STEP_TYPE_ID", "STATUS"],
        unique=False,
    )
    op.create_table(
        "STEP_TYPE_PORT",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("STEP_TYPE_VERSION_ID", sa.Uuid(), nullable=False),
        sa.Column("DIRECTION", sa.String(length=8), nullable=False),
        sa.Column("PORT_KEY", sa.String(length=64), nullable=False),
        sa.Column("VALUE_SCHEMA", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("REQUIRED", sa.Boolean(), nullable=False),
        sa.Column("NULLABLE", sa.Boolean(), nullable=False),
        sa.Column("CARDINALITY", sa.String(length=8), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "\"CARDINALITY\" IN ('SCALAR', 'LIST')", name="ck_STEP_TYPE_PORT_cardinality"
        ),
        sa.CheckConstraint(
            "\"DIRECTION\" IN ('INPUT', 'OUTPUT')", name="ck_STEP_TYPE_PORT_direction"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(\"VALUE_SCHEMA\") = 'object'", name="ck_STEP_TYPE_PORT_schema"
        ),
        sa.CheckConstraint('length("PORT_KEY") > 0', name="ck_STEP_TYPE_PORT_key"),
        sa.ForeignKeyConstraint(
            ["STEP_TYPE_VERSION_ID"],
            ["STEP_TYPE_VERSION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint(
            "STEP_TYPE_VERSION_ID", "DIRECTION", "PORT_KEY", name="uq_STEP_TYPE_PORT_key"
        ),
    )
    op.create_index(
        "ix_STEP_TYPE_PORT_version_direction",
        "STEP_TYPE_PORT",
        ["STEP_TYPE_VERSION_ID", "DIRECTION"],
        unique=False,
    )

    op.create_index(
        "ix_STEP_TYPE_HISTORY_entity_changed", "STEP_TYPE_HISTORY", ["ENTITY_ID", "CHANGED_AT"]
    )
    op.create_check_constraint(
        "ck_STEP_TYPE_VERSION_not_deleted",
        "STEP_TYPE_VERSION",
        '"STATUS" = \'DRAFT\' OR "DELETED_AT" IS NULL',
    )
    _seed_catalog()
    _install_immutability_versioned_step_types_and_typed_ports()


def _downgrade_versioned_step_types_and_typed_ports() -> None:
    """Downgrade schema."""
    op.drop_index("ix_STEP_TYPE_PORT_version_direction", table_name="STEP_TYPE_PORT")
    op.drop_table("STEP_TYPE_PORT")
    op.execute("DROP FUNCTION protect_step_type_port()")
    op.drop_index("ix_STEP_TYPE_VERSION_type_status", table_name="STEP_TYPE_VERSION")
    op.drop_index(op.f("ix_STEP_TYPE_VERSION_CREATED_AT"), table_name="STEP_TYPE_VERSION")
    op.drop_table("STEP_TYPE_VERSION")
    op.execute("DROP FUNCTION protect_step_type_version()")
    op.drop_index(op.f("ix_STEP_TYPE_HISTORY_TRACE_ID"), table_name="STEP_TYPE_HISTORY")
    op.drop_index(op.f("ix_STEP_TYPE_HISTORY_REQUEST_ID"), table_name="STEP_TYPE_HISTORY")
    op.drop_index(op.f("ix_STEP_TYPE_HISTORY_ENTITY_ID"), table_name="STEP_TYPE_HISTORY")
    op.drop_index(op.f("ix_STEP_TYPE_HISTORY_CHANGED_AT"), table_name="STEP_TYPE_HISTORY")
    op.drop_table("STEP_TYPE_HISTORY")
    op.drop_index(
        "uq_STEP_TYPE_CODE_active",
        table_name="STEP_TYPE",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index("ix_STEP_TYPE_enabled_code", table_name="STEP_TYPE")
    op.drop_index(op.f("ix_STEP_TYPE_CREATED_AT"), table_name="STEP_TYPE")
    op.drop_table("STEP_TYPE")


_INITIAL_CATALOG = [
    {
        "code": "DECISION",
        "name": "Decision",
        "handler_key": "decision",
        "handler_version": "1",
        "execution_mode": "SYNC",
        "config_schema": {
            "additionalProperties": False,
            "properties": {
                "expression": {
                    "maxLength": 4096,
                    "minLength": 1,
                    "title": "Expression",
                    "type": "string",
                }
            },
            "required": ["expression"],
            "title": "DecisionConfig",
            "type": "object",
        },
        "ports": [
            {
                "port_key": "data",
                "direction": "INPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                    "type": "object",
                    "not": {"type": "null"},
                },
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "outcome",
                "direction": "OUTPUT",
                "value_schema": {"type": "string", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
        ],
    },
    {
        "code": "FINISH",
        "name": "Finish",
        "handler_key": "finish",
        "handler_version": "1",
        "execution_mode": "SYNC",
        "config_schema": {
            "additionalProperties": False,
            "properties": {},
            "title": "EmptyConfig",
            "type": "object",
        },
        "ports": [],
    },
    {
        "code": "FUNCTION",
        "name": "Function",
        "handler_key": "function",
        "handler_version": "1",
        "execution_mode": "SYNC",
        "config_schema": {
            "$defs": {"Reference": {"maxLength": 512, "minLength": 1, "type": "string"}},
            "additionalProperties": False,
            "properties": {"function_key": {"$ref": "#/$defs/Reference"}},
            "required": ["function_key"],
            "title": "FunctionConfig",
            "type": "object",
        },
        "ports": [
            {
                "port_key": "arguments",
                "direction": "INPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                    "type": "object",
                    "not": {"type": "null"},
                },
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "result",
                "direction": "OUTPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "anyOf": [{"$ref": "#/$defs/JsonValue"}, {"type": "null"}],
                },
                "required": True,
                "nullable": True,
                "cardinality": "SCALAR",
            },
        ],
    },
    {
        "code": "HUMAN_TASK",
        "name": "Human task",
        "handler_key": "human_task",
        "handler_version": "1",
        "execution_mode": "HUMAN",
        "config_schema": {
            "$defs": {"Reference": {"maxLength": 512, "minLength": 1, "type": "string"}},
            "additionalProperties": False,
            "properties": {"form_version_ref": {"$ref": "#/$defs/Reference"}},
            "required": ["form_version_ref"],
            "title": "HumanConfig",
            "type": "object",
        },
        "ports": [
            {
                "port_key": "initial_data",
                "direction": "INPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                    "type": "object",
                    "not": {"type": "null"},
                },
                "required": False,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "submission",
                "direction": "OUTPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                    "type": "object",
                    "not": {"type": "null"},
                },
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "outcome",
                "direction": "OUTPUT",
                "value_schema": {"type": "string", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
        ],
    },
    {
        "code": "NOTIFICATION",
        "name": "Notification",
        "handler_key": "notification",
        "handler_version": "1",
        "execution_mode": "BACKGROUND",
        "config_schema": {
            "$defs": {"Reference": {"maxLength": 512, "minLength": 1, "type": "string"}},
            "additionalProperties": False,
            "properties": {
                "connection_ref": {"$ref": "#/$defs/Reference"},
                "template_key": {"$ref": "#/$defs/Reference"},
            },
            "required": ["connection_ref", "template_key"],
            "title": "NotificationConfig",
            "type": "object",
        },
        "ports": [
            {
                "port_key": "recipients",
                "direction": "INPUT",
                "value_schema": {
                    "$defs": {"Reference": {"maxLength": 512, "minLength": 1, "type": "string"}},
                    "items": {"$ref": "#/$defs/Reference"},
                    "type": "array",
                    "not": {"type": "null"},
                    "x-reference-kind": "user",
                },
                "required": True,
                "nullable": False,
                "cardinality": "LIST",
            },
            {
                "port_key": "data",
                "direction": "INPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                    "type": "object",
                    "not": {"type": "null"},
                },
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "notification",
                "direction": "OUTPUT",
                "value_schema": {
                    "maxLength": 512,
                    "minLength": 1,
                    "type": "string",
                    "not": {"type": "null"},
                    "x-reference-kind": "notification",
                },
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
        ],
    },
    {
        "code": "SERVICE_TASK",
        "name": "Service task",
        "handler_key": "service_task",
        "handler_version": "1",
        "execution_mode": "BACKGROUND",
        "config_schema": {
            "$defs": {"Reference": {"maxLength": 512, "minLength": 1, "type": "string"}},
            "additionalProperties": False,
            "properties": {
                "connection_ref": {"$ref": "#/$defs/Reference"},
                "operation_key": {"$ref": "#/$defs/Reference"},
            },
            "required": ["connection_ref", "operation_key"],
            "title": "ServiceConfig",
            "type": "object",
        },
        "ports": [
            {
                "port_key": "payload",
                "direction": "INPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                    "type": "object",
                    "not": {"type": "null"},
                },
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "result",
                "direction": "OUTPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "anyOf": [{"$ref": "#/$defs/JsonValue"}, {"type": "null"}],
                },
                "required": True,
                "nullable": True,
                "cardinality": "SCALAR",
            },
        ],
    },
    {
        "code": "START",
        "name": "Start",
        "handler_key": "start",
        "handler_version": "1",
        "execution_mode": "SYNC",
        "config_schema": {
            "additionalProperties": False,
            "properties": {},
            "title": "EmptyConfig",
            "type": "object",
        },
        "ports": [],
    },
    {
        "code": "TRANSFORM",
        "name": "Transform",
        "handler_key": "transform",
        "handler_version": "1",
        "execution_mode": "SYNC",
        "config_schema": {
            "$defs": {"Reference": {"maxLength": 512, "minLength": 1, "type": "string"}},
            "additionalProperties": False,
            "properties": {"conversion_key": {"$ref": "#/$defs/Reference"}},
            "required": ["conversion_key"],
            "title": "TransformConfig",
            "type": "object",
        },
        "ports": [
            {
                "port_key": "value",
                "direction": "INPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "anyOf": [{"$ref": "#/$defs/JsonValue"}, {"type": "null"}],
                },
                "required": True,
                "nullable": True,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "result",
                "direction": "OUTPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "anyOf": [{"$ref": "#/$defs/JsonValue"}, {"type": "null"}],
                },
                "required": True,
                "nullable": True,
                "cardinality": "SCALAR",
            },
        ],
    },
]


# Versioned forms and render contracts


def _upgrade_versioned_forms_and_render_contracts() -> None:
    """Upgrade schema."""
    op.create_table(
        "FORM_DEFINITION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("OWNER_USER_ID", sa.Uuid(), nullable=False),
        sa.Column("IS_ACTIVE", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            'length("CODE") > 0 AND length("NAME") > 0', name="ck_FORM_DEFINITION_names"
        ),
        sa.ForeignKeyConstraint(
            ["OWNER_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_DEFINITION_CREATED_AT"), "FORM_DEFINITION", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_FORM_DEFINITION_owner_created",
        "FORM_DEFINITION",
        ["OWNER_USER_ID", "CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "uq_FORM_DEFINITION_CODE_active",
        "FORM_DEFINITION",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "FORM_DEFINITION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["FORM_DEFINITION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_DEFINITION_HISTORY_CHANGED_AT"),
        "FORM_DEFINITION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DEFINITION_HISTORY_ENTITY_ID"),
        "FORM_DEFINITION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DEFINITION_HISTORY_REQUEST_ID"),
        "FORM_DEFINITION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DEFINITION_HISTORY_TRACE_ID"),
        "FORM_DEFINITION_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_DEFINITION_HISTORY_entity_changed",
        "FORM_DEFINITION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "FORM_VERSION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("FORM_DEFINITION_ID", sa.Uuid(), nullable=False),
        sa.Column("NUMBER", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("DATA_DIALECT", sa.String(length=128), nullable=False),
        sa.Column("RENDER_DIALECT", sa.String(length=64), nullable=False),
        sa.Column("DATA_SCHEMA", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("RENDER_SCHEMA", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("CHECKSUM", sa.String(length=64), nullable=True),
        sa.Column("PUBLISHED_BY_USER_ID", sa.Uuid(), nullable=True),
        sa.Column("PUBLISHED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('"NUMBER" > 0', name="ck_FORM_VERSION_number"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="ck_FORM_VERSION_status"
        ),
        sa.CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "CHECKSUM" IS NULL AND "PUBLISHED_AT" IS NULL AND "PUBLISHED_BY_USER_ID" IS NULL) OR ("STATUS" IN (\'PUBLISHED\', \'RETIRED\') AND "CHECKSUM" IS NOT NULL AND length("CHECKSUM") = 64 AND "PUBLISHED_AT" IS NOT NULL AND "PUBLISHED_BY_USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL)',
            name="ck_FORM_VERSION_publication",
        ),
        sa.ForeignKeyConstraint(
            ["FORM_DEFINITION_ID"], ["FORM_DEFINITION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["PUBLISHED_BY_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("FORM_DEFINITION_ID", "NUMBER", name="uq_FORM_VERSION_number"),
    )
    op.create_index(
        op.f("ix_FORM_VERSION_CREATED_AT"), "FORM_VERSION", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_FORM_VERSION_definition_status_number",
        "FORM_VERSION",
        ["FORM_DEFINITION_ID", "STATUS", "NUMBER"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_VERSION_publisher", "FORM_VERSION", ["PUBLISHED_BY_USER_ID"], unique=False
    )
    op.create_table(
        "FORM_VERSION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_FORM_DEFINITION_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF FORM_DEFINITION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_FORM_DEFINITION_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF FORM_DEFINITION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NUMBER",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF NUMBER FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NUMBER", sa.Integer(), nullable=True, comment="TO VALUE OF NUMBER FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DATA_DIALECT",
            sa.String(length=128),
            nullable=True,
            comment="FROM VALUE OF DATA_DIALECT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DATA_DIALECT",
            sa.String(length=128),
            nullable=True,
            comment="TO VALUE OF DATA_DIALECT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_RENDER_DIALECT",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF RENDER_DIALECT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_RENDER_DIALECT",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF RENDER_DIALECT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DATA_SCHEMA",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF DATA_SCHEMA FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DATA_SCHEMA",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF DATA_SCHEMA FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_RENDER_SCHEMA",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF RENDER_SCHEMA FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_RENDER_SCHEMA",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF RENDER_SCHEMA FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["FORM_VERSION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_VERSION_HISTORY_CHANGED_AT"),
        "FORM_VERSION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_VERSION_HISTORY_ENTITY_ID"),
        "FORM_VERSION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_VERSION_HISTORY_REQUEST_ID"),
        "FORM_VERSION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_VERSION_HISTORY_TRACE_ID"), "FORM_VERSION_HISTORY", ["TRACE_ID"], unique=False
    )
    op.create_index(
        "ix_FORM_VERSION_HISTORY_entity_changed",
        "FORM_VERSION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )

    _protect_published_versions()


def _downgrade_versioned_forms_and_render_contracts() -> None:
    """Downgrade schema."""
    op.drop_index("ix_FORM_VERSION_HISTORY_entity_changed", table_name="FORM_VERSION_HISTORY")
    op.drop_index(op.f("ix_FORM_VERSION_HISTORY_TRACE_ID"), table_name="FORM_VERSION_HISTORY")
    op.drop_index(op.f("ix_FORM_VERSION_HISTORY_REQUEST_ID"), table_name="FORM_VERSION_HISTORY")
    op.drop_index(op.f("ix_FORM_VERSION_HISTORY_ENTITY_ID"), table_name="FORM_VERSION_HISTORY")
    op.drop_index(op.f("ix_FORM_VERSION_HISTORY_CHANGED_AT"), table_name="FORM_VERSION_HISTORY")
    op.drop_table("FORM_VERSION_HISTORY")
    op.drop_index("ix_FORM_VERSION_publisher", table_name="FORM_VERSION")
    op.drop_index("ix_FORM_VERSION_definition_status_number", table_name="FORM_VERSION")
    op.drop_index(op.f("ix_FORM_VERSION_CREATED_AT"), table_name="FORM_VERSION")
    op.drop_table("FORM_VERSION")
    op.execute("DROP FUNCTION protect_form_version()")
    op.drop_index("ix_FORM_DEFINITION_HISTORY_entity_changed", table_name="FORM_DEFINITION_HISTORY")
    op.drop_index(op.f("ix_FORM_DEFINITION_HISTORY_TRACE_ID"), table_name="FORM_DEFINITION_HISTORY")
    op.drop_index(
        op.f("ix_FORM_DEFINITION_HISTORY_REQUEST_ID"), table_name="FORM_DEFINITION_HISTORY"
    )
    op.drop_index(
        op.f("ix_FORM_DEFINITION_HISTORY_ENTITY_ID"), table_name="FORM_DEFINITION_HISTORY"
    )
    op.drop_index(
        op.f("ix_FORM_DEFINITION_HISTORY_CHANGED_AT"), table_name="FORM_DEFINITION_HISTORY"
    )
    op.drop_table("FORM_DEFINITION_HISTORY")
    op.drop_index(
        "uq_FORM_DEFINITION_CODE_active",
        table_name="FORM_DEFINITION",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index("ix_FORM_DEFINITION_owner_created", table_name="FORM_DEFINITION")
    op.drop_index(op.f("ix_FORM_DEFINITION_CREATED_AT"), table_name="FORM_DEFINITION")
    op.drop_table("FORM_DEFINITION")


def _protect_published_versions() -> None:
    op.execute("""
        CREATE FUNCTION protect_form_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW."STATUS" <> 'DRAFT' THEN
                    RAISE EXCEPTION 'New form versions must be drafts' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD."STATUS" <> 'DRAFT' THEN
                IF TG_OP = 'UPDATE' AND OLD."STATUS" = 'PUBLISHED'
                    AND NEW."STATUS" = 'RETIRED'
                    AND (to_jsonb(NEW) - ARRAY['STATUS', 'VERSION', 'UPDATED_AT']) =
                        (to_jsonb(OLD) - ARRAY['STATUS', 'VERSION', 'UPDATED_AT']) THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Published form version is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            IF NEW."STATUS" = 'RETIRED' THEN
                RAISE EXCEPTION 'Draft cannot be retired' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""CREATE TRIGGER form_version_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON "FORM_VERSION"
        FOR EACH ROW EXECUTE FUNCTION protect_form_version()""")


# Governed integration connections


def _upgrade_governed_integration_connections() -> None:
    """Upgrade schema."""
    op.create_table(
        "INTEGRATION_CONNECTION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("PROVIDER", sa.String(length=64), nullable=False),
        sa.Column("KIND", sa.String(length=32), nullable=False),
        sa.Column(
            "NON_SECRET_CONFIG",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("SECRET_REF", sa.String(length=64), nullable=False),
        sa.Column("SECRET_VERSION", sa.String(length=64), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("VERIFICATION_STATUS", sa.String(length=16), nullable=False),
        sa.Column("OWNER_USER_ID", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "\"STATUS\" IN ('ACTIVE', 'DISABLED', 'REVOKED')",
            name="ck_INTEGRATION_CONNECTION_status",
        ),
        sa.CheckConstraint(
            "\"VERIFICATION_STATUS\" IN ('UNVERIFIED', 'VERIFIED', 'FAILED')",
            name="ck_INTEGRATION_CONNECTION_verified",
        ),
        sa.ForeignKeyConstraint(
            ["OWNER_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_INTEGRATION_CONNECTION_CREATED_AT"),
        "INTEGRATION_CONNECTION",
        ["CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "ix_INTEGRATION_CONNECTION_owner", "INTEGRATION_CONNECTION", ["OWNER_USER_ID"], unique=False
    )
    op.create_index(
        "ix_INTEGRATION_CONNECTION_provider_kind_status",
        "INTEGRATION_CONNECTION",
        ["PROVIDER", "KIND", "STATUS"],
        unique=False,
    )
    op.create_index(
        "uq_INTEGRATION_CONNECTION_CODE_active",
        "INTEGRATION_CONNECTION",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "INTEGRATION_CONNECTION_GRANT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("INTEGRATION_CONNECTION_ID", sa.Uuid(), nullable=False),
        sa.Column("USER_ID", sa.Uuid(), nullable=True),
        sa.Column("WORK_GROUP_ID", sa.Uuid(), nullable=True),
        sa.Column("CAN_USE", sa.Boolean(), nullable=False),
        sa.Column("CAN_MANAGE", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            '"CAN_USE" OR "CAN_MANAGE"', name="ck_INTEGRATION_CONNECTION_GRANT_capability"
        ),
        sa.CheckConstraint(
            '("USER_ID" IS NOT NULL)::int + ("WORK_GROUP_ID" IS NOT NULL)::int = 1',
            name="ck_INTEGRATION_CONNECTION_GRANT_target",
        ),
        sa.ForeignKeyConstraint(
            ["INTEGRATION_CONNECTION_ID"],
            ["INTEGRATION_CONNECTION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["WORK_GROUP_ID"], ["WORK_GROUP.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_INTEGRATION_CONNECTION_GRANT_CREATED_AT"),
        "INTEGRATION_CONNECTION_GRANT",
        ["CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "ix_INTEGRATION_CONNECTION_GRANT_group",
        "INTEGRATION_CONNECTION_GRANT",
        ["WORK_GROUP_ID"],
        unique=False,
    )
    op.create_index(
        "ix_INTEGRATION_CONNECTION_GRANT_user",
        "INTEGRATION_CONNECTION_GRANT",
        ["USER_ID"],
        unique=False,
    )
    op.create_index(
        "uq_INTEGRATION_CONNECTION_GRANT_group",
        "INTEGRATION_CONNECTION_GRANT",
        ["INTEGRATION_CONNECTION_ID", "WORK_GROUP_ID"],
        unique=True,
        postgresql_where=sa.text('"WORK_GROUP_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
    )
    op.create_index(
        "uq_INTEGRATION_CONNECTION_GRANT_user",
        "INTEGRATION_CONNECTION_GRANT",
        ["INTEGRATION_CONNECTION_ID", "USER_ID"],
        unique=True,
        postgresql_where=sa.text('"USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
    )
    op.create_table(
        "INTEGRATION_CONNECTION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PROVIDER",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF PROVIDER FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PROVIDER",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF PROVIDER FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_KIND",
            sa.String(length=32),
            nullable=True,
            comment="FROM VALUE OF KIND FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_KIND",
            sa.String(length=32),
            nullable=True,
            comment="TO VALUE OF KIND FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NON_SECRET_CONFIG",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF NON_SECRET_CONFIG FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NON_SECRET_CONFIG",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF NON_SECRET_CONFIG FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SECRET_REF",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF SECRET_REF FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SECRET_REF",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF SECRET_REF FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SECRET_VERSION",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF SECRET_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SECRET_VERSION",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF SECRET_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_VERIFICATION_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF VERIFICATION_STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_VERIFICATION_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF VERIFICATION_STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["INTEGRATION_CONNECTION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_INTEGRATION_CONNECTION_HISTORY_CHANGED_AT"),
        "INTEGRATION_CONNECTION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_INTEGRATION_CONNECTION_HISTORY_ENTITY_ID"),
        "INTEGRATION_CONNECTION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_INTEGRATION_CONNECTION_HISTORY_REQUEST_ID"),
        "INTEGRATION_CONNECTION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_INTEGRATION_CONNECTION_HISTORY_TRACE_ID"),
        "INTEGRATION_CONNECTION_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_INTEGRATION_CONNECTION_HISTORY_entity_changed",
        "INTEGRATION_CONNECTION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )


def _downgrade_governed_integration_connections() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_INTEGRATION_CONNECTION_HISTORY_entity_changed",
        table_name="INTEGRATION_CONNECTION_HISTORY",
    )
    op.drop_index(
        op.f("ix_INTEGRATION_CONNECTION_HISTORY_TRACE_ID"),
        table_name="INTEGRATION_CONNECTION_HISTORY",
    )
    op.drop_index(
        op.f("ix_INTEGRATION_CONNECTION_HISTORY_REQUEST_ID"),
        table_name="INTEGRATION_CONNECTION_HISTORY",
    )
    op.drop_index(
        op.f("ix_INTEGRATION_CONNECTION_HISTORY_ENTITY_ID"),
        table_name="INTEGRATION_CONNECTION_HISTORY",
    )
    op.drop_index(
        op.f("ix_INTEGRATION_CONNECTION_HISTORY_CHANGED_AT"),
        table_name="INTEGRATION_CONNECTION_HISTORY",
    )
    op.drop_table("INTEGRATION_CONNECTION_HISTORY")
    op.drop_index(
        "uq_INTEGRATION_CONNECTION_GRANT_user",
        table_name="INTEGRATION_CONNECTION_GRANT",
        postgresql_where=sa.text('"USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
    )
    op.drop_index(
        "uq_INTEGRATION_CONNECTION_GRANT_group",
        table_name="INTEGRATION_CONNECTION_GRANT",
        postgresql_where=sa.text('"WORK_GROUP_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
    )
    op.drop_index("ix_INTEGRATION_CONNECTION_GRANT_user", table_name="INTEGRATION_CONNECTION_GRANT")
    op.drop_index(
        "ix_INTEGRATION_CONNECTION_GRANT_group", table_name="INTEGRATION_CONNECTION_GRANT"
    )
    op.drop_index(
        op.f("ix_INTEGRATION_CONNECTION_GRANT_CREATED_AT"),
        table_name="INTEGRATION_CONNECTION_GRANT",
    )
    op.drop_table("INTEGRATION_CONNECTION_GRANT")
    op.drop_index(
        "uq_INTEGRATION_CONNECTION_CODE_active",
        table_name="INTEGRATION_CONNECTION",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index(
        "ix_INTEGRATION_CONNECTION_provider_kind_status", table_name="INTEGRATION_CONNECTION"
    )
    op.drop_index("ix_INTEGRATION_CONNECTION_owner", table_name="INTEGRATION_CONNECTION")
    op.drop_index(op.f("ix_INTEGRATION_CONNECTION_CREATED_AT"), table_name="INTEGRATION_CONNECTION")
    op.drop_table("INTEGRATION_CONNECTION")


# Versioned workflow authoring


def _install_immutability_versioned_workflow_authoring() -> None:
    op.execute("""
        CREATE FUNCTION protect_workflow_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW."STATUS" <> 'DRAFT' THEN
                    RAISE EXCEPTION 'New workflow versions must be drafts' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD."STATUS" <> 'DRAFT' THEN
                IF TG_OP = 'UPDATE' AND OLD."STATUS" = 'PUBLISHED'
                    AND NEW."STATUS" = 'RETIRED'
                    AND (to_jsonb(NEW) - ARRAY['STATUS', 'VERSION', 'UPDATED_AT']) =
                        (to_jsonb(OLD) - ARRAY['STATUS', 'VERSION', 'UPDATED_AT']) THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Published workflow version is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            IF NEW."STATUS" = 'RETIRED' THEN
                RAISE EXCEPTION 'Draft cannot be retired' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""CREATE TRIGGER workflow_version_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON "WORKFLOW_VERSION"
        FOR EACH ROW EXECUTE FUNCTION protect_workflow_version()""")
    op.execute("""
        CREATE FUNCTION protect_workflow_graph() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_id uuid; parent_status text; step_id uuid;
        BEGIN
            IF TG_ARGV[0] = 'version' THEN
                IF TG_OP = 'DELETE' THEN parent_id := OLD."WORKFLOW_VERSION_ID";
                ELSE parent_id := NEW."WORKFLOW_VERSION_ID"; END IF;
                IF TG_OP = 'UPDATE' AND NEW."WORKFLOW_VERSION_ID" <> OLD."WORKFLOW_VERSION_ID" THEN
                    RAISE EXCEPTION 'Workflow graph parent is immutable' USING ERRCODE = '23514';
                END IF;
            ELSE
                IF TG_OP = 'DELETE' THEN step_id := OLD."WORKFLOW_STEP_ID";
                ELSE step_id := NEW."WORKFLOW_STEP_ID"; END IF;
                IF TG_OP = 'UPDATE' AND NEW."WORKFLOW_STEP_ID" <> OLD."WORKFLOW_STEP_ID" THEN
                    RAISE EXCEPTION 'Workflow graph parent is immutable' USING ERRCODE = '23514';
                END IF;
                SELECT "WORKFLOW_VERSION_ID" INTO parent_id FROM "WORKFLOW_STEP"
                    WHERE "ID" = step_id;
            END IF;
            SELECT "STATUS" INTO parent_status FROM "WORKFLOW_VERSION"
                WHERE "ID" = parent_id FOR UPDATE;
            IF parent_status <> 'DRAFT' THEN
                RAISE EXCEPTION 'Published workflow graph is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$
    """)
    for table, mode in (
        ("WORKFLOW_STEP", "version"),
        ("WORKFLOW_TRANSITION", "version"),
        ("WORKFLOW_STEP_INPUT_BINDING", "step"),
        ("WORKFLOW_STEP_TARGET", "step"),
    ):
        op.execute(f'''CREATE TRIGGER {table.lower()}_immutable
            BEFORE INSERT OR UPDATE OR DELETE ON "{table}"
            FOR EACH ROW EXECUTE FUNCTION protect_workflow_graph('{mode}')''')


def _upgrade_versioned_workflow_authoring() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "WORKFLOW_DEFINITION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("OWNER_USER_ID", sa.Uuid(), nullable=False),
        sa.Column("ACCESS_MODE", sa.String(length=16), nullable=False),
        sa.Column("IS_ACTIVE", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "\"ACCESS_MODE\" IN ('OPEN', 'RESTRICTED')", name="ck_WORKFLOW_DEFINITION_access"
        ),
        sa.CheckConstraint(
            'length("CODE") > 0 AND length("NAME") > 0', name="ck_WORKFLOW_DEFINITION_names"
        ),
        sa.ForeignKeyConstraint(
            ["OWNER_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_WORKFLOW_DEFINITION_CREATED_AT"),
        "WORKFLOW_DEFINITION",
        ["CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "ix_WORKFLOW_DEFINITION_access_active",
        "WORKFLOW_DEFINITION",
        ["ACCESS_MODE", "IS_ACTIVE"],
        unique=False,
    )
    op.create_index(
        "ix_WORKFLOW_DEFINITION_owner_active",
        "WORKFLOW_DEFINITION",
        ["OWNER_USER_ID", "IS_ACTIVE"],
        unique=False,
    )
    op.create_index(
        "uq_WORKFLOW_DEFINITION_code_active",
        "WORKFLOW_DEFINITION",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "WORKFLOW_ACCESS_GRANT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("WORKFLOW_DEFINITION_ID", sa.Uuid(), nullable=False),
        sa.Column("USER_ID", sa.Uuid(), nullable=True),
        sa.Column("WORK_GROUP_ID", sa.Uuid(), nullable=True),
        sa.Column("CAN_VIEW", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("CAN_START", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            '("CAN_VIEW" OR "CAN_START")', name="ck_WORKFLOW_ACCESS_GRANT_capability"
        ),
        sa.CheckConstraint(
            '(NOT "CAN_START" OR "CAN_VIEW")',
            name="ck_WORKFLOW_ACCESS_GRANT_start_implies_view",
        ),
        sa.CheckConstraint(
            '(num_nonnulls("USER_ID", "WORK_GROUP_ID") = 1)', name="ck_WORKFLOW_ACCESS_GRANT_target"
        ),
        sa.ForeignKeyConstraint(["USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_DEFINITION_ID"],
            ["WORKFLOW_DEFINITION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["WORK_GROUP_ID"], ["WORK_GROUP.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_WORKFLOW_ACCESS_GRANT_CREATED_AT"),
        "WORKFLOW_ACCESS_GRANT",
        ["CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "uq_WORKFLOW_ACCESS_GRANT_group",
        "WORKFLOW_ACCESS_GRANT",
        ["WORKFLOW_DEFINITION_ID", "WORK_GROUP_ID"],
        unique=True,
        postgresql_where=sa.text('"WORK_GROUP_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
    )
    op.create_index(
        "uq_WORKFLOW_ACCESS_GRANT_user",
        "WORKFLOW_ACCESS_GRANT",
        ["WORKFLOW_DEFINITION_ID", "USER_ID"],
        unique=True,
        postgresql_where=sa.text('"USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
    )
    op.create_index(
        "ix_WORKFLOW_ACCESS_GRANT_user_definition",
        "WORKFLOW_ACCESS_GRANT",
        ["USER_ID", "WORKFLOW_DEFINITION_ID"],
    )
    op.create_index(
        "ix_WORKFLOW_ACCESS_GRANT_group_definition",
        "WORKFLOW_ACCESS_GRANT",
        ["WORK_GROUP_ID", "WORKFLOW_DEFINITION_ID"],
    )
    op.create_table(
        "WORKFLOW_DEFINITION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ACCESS_MODE",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF ACCESS_MODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ACCESS_MODE",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF ACCESS_MODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["WORKFLOW_DEFINITION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_WORKFLOW_DEFINITION_HISTORY_CHANGED_AT"),
        "WORKFLOW_DEFINITION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_WORKFLOW_DEFINITION_HISTORY_ENTITY_ID"),
        "WORKFLOW_DEFINITION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_WORKFLOW_DEFINITION_HISTORY_REQUEST_ID"),
        "WORKFLOW_DEFINITION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_WORKFLOW_DEFINITION_HISTORY_TRACE_ID"),
        "WORKFLOW_DEFINITION_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_WORKFLOW_DEFINITION_HISTORY_entity_changed",
        "WORKFLOW_DEFINITION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "WORKFLOW_VERSION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("WORKFLOW_DEFINITION_ID", sa.Uuid(), nullable=False),
        sa.Column("NUMBER", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("DEFAULT_PRIORITY", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("GRAPH_CHECKSUM", sa.String(length=64), nullable=True),
        sa.Column("PUBLISHED_BY_USER_ID", sa.Uuid(), nullable=True),
        sa.Column("PUBLISHED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            '"DEFAULT_PRIORITY" BETWEEN 0 AND 9', name="ck_WORKFLOW_VERSION_priority"
        ),
        sa.CheckConstraint('"NUMBER" > 0', name="ck_WORKFLOW_VERSION_number"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="ck_WORKFLOW_VERSION_status"
        ),
        sa.CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "GRAPH_CHECKSUM" IS NULL AND "PUBLISHED_AT" IS NULL AND "PUBLISHED_BY_USER_ID" IS NULL) OR ("STATUS" IN (\'PUBLISHED\', \'RETIRED\') AND length("GRAPH_CHECKSUM") = 64 AND "PUBLISHED_AT" IS NOT NULL AND "PUBLISHED_BY_USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL)',
            name="ck_WORKFLOW_VERSION_publication",
        ),
        sa.ForeignKeyConstraint(
            ["PUBLISHED_BY_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_DEFINITION_ID"],
            ["WORKFLOW_DEFINITION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("WORKFLOW_DEFINITION_ID", "NUMBER", name="uq_WORKFLOW_VERSION_number"),
    )
    op.create_index(
        op.f("ix_WORKFLOW_VERSION_CREATED_AT"), "WORKFLOW_VERSION", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_WORKFLOW_VERSION_definition_status",
        "WORKFLOW_VERSION",
        ["WORKFLOW_DEFINITION_ID", "STATUS", "NUMBER"],
        unique=False,
    )
    op.create_index("ix_WORKFLOW_VERSION_publisher", "WORKFLOW_VERSION", ["PUBLISHED_BY_USER_ID"])
    op.create_table(
        "WORKFLOW_STEP",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("WORKFLOW_VERSION_ID", sa.Uuid(), nullable=False),
        sa.Column("STEP_TYPE_VERSION_ID", sa.Uuid(), nullable=False),
        sa.Column("STEP_KEY", sa.String(length=64), nullable=False),
        sa.Column(
            "CONFIG",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("FORM_VERSION_ID", sa.Uuid(), nullable=True),
        sa.Column("FIELD_POLICY", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("DEFAULT_PRIORITY", sa.Integer(), nullable=True),
        sa.Column("TIMEOUT_SECONDS", sa.Integer(), nullable=True),
        sa.Column("DISPLAY_ORDER", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            '"DEFAULT_PRIORITY" IS NULL OR "DEFAULT_PRIORITY" BETWEEN 0 AND 9',
            name="ck_WORKFLOW_STEP_priority",
        ),
        sa.CheckConstraint(
            '"TIMEOUT_SECONDS" IS NULL OR "TIMEOUT_SECONDS" > 0', name="ck_WORKFLOW_STEP_timeout"
        ),
        sa.CheckConstraint('"DISPLAY_ORDER" >= 0', name="ck_WORKFLOW_STEP_order"),
        sa.CheckConstraint(
            '("FORM_VERSION_ID" IS NULL AND "FIELD_POLICY" IS NULL) OR ("FORM_VERSION_ID" IS NOT NULL AND "FIELD_POLICY" IS NOT NULL)',
            name="ck_WORKFLOW_STEP_form_policy",
        ),
        sa.CheckConstraint('length("STEP_KEY") > 0', name="ck_WORKFLOW_STEP_key"),
        sa.ForeignKeyConstraint(
            ["FORM_VERSION_ID"], ["FORM_VERSION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["STEP_TYPE_VERSION_ID"],
            ["STEP_TYPE_VERSION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_VERSION_ID"],
            ["WORKFLOW_VERSION.ID"],
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("WORKFLOW_VERSION_ID", "ID", name="uq_WORKFLOW_STEP_version_id"),
        sa.UniqueConstraint("WORKFLOW_VERSION_ID", "STEP_KEY", name="uq_WORKFLOW_STEP_key"),
    )
    op.create_index(
        op.f("ix_WORKFLOW_STEP_CREATED_AT"), "WORKFLOW_STEP", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_WORKFLOW_STEP_version_order",
        "WORKFLOW_STEP",
        ["WORKFLOW_VERSION_ID", "DISPLAY_ORDER"],
        unique=False,
    )
    op.create_index("ix_WORKFLOW_STEP_type", "WORKFLOW_STEP", ["STEP_TYPE_VERSION_ID"])
    op.create_index("ix_WORKFLOW_STEP_form", "WORKFLOW_STEP", ["FORM_VERSION_ID"])
    op.create_table(
        "WORKFLOW_VERSION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_WORKFLOW_DEFINITION_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF WORKFLOW_DEFINITION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_WORKFLOW_DEFINITION_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF WORKFLOW_DEFINITION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NUMBER",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF NUMBER FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NUMBER", sa.Integer(), nullable=True, comment="TO VALUE OF NUMBER FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DEFAULT_PRIORITY",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF DEFAULT_PRIORITY FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DEFAULT_PRIORITY",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF DEFAULT_PRIORITY FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_GRAPH_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF GRAPH_CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_GRAPH_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF GRAPH_CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["WORKFLOW_VERSION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_WORKFLOW_VERSION_HISTORY_CHANGED_AT"),
        "WORKFLOW_VERSION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_WORKFLOW_VERSION_HISTORY_ENTITY_ID"),
        "WORKFLOW_VERSION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_WORKFLOW_VERSION_HISTORY_REQUEST_ID"),
        "WORKFLOW_VERSION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_WORKFLOW_VERSION_HISTORY_TRACE_ID"),
        "WORKFLOW_VERSION_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_WORKFLOW_VERSION_HISTORY_entity_changed",
        "WORKFLOW_VERSION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "WORKFLOW_STEP_INPUT_BINDING",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("WORKFLOW_STEP_ID", sa.Uuid(), nullable=False),
        sa.Column("TARGET_PORT_ID", sa.Uuid(), nullable=False),
        sa.Column("ORDINAL", sa.Integer(), nullable=False),
        sa.Column("SOURCE_KIND", sa.String(length=16), nullable=False),
        sa.Column("SOURCE_PATH", sa.String(length=1024), nullable=True),
        sa.Column("SOURCE_STEP_ID", sa.Uuid(), nullable=True),
        sa.Column("SOURCE_PORT_ID", sa.Uuid(), nullable=True),
        sa.Column("CONSTANT_VALUE", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "\"SOURCE_KIND\" IN ('REQUEST', 'CONTEXT', 'CONSTANT', 'STEP_OUTPUT')",
            name="ck_WORKFLOW_BINDING_kind",
        ),
        sa.CheckConstraint(
            '("SOURCE_KIND" = \'CONSTANT\') = ("CONSTANT_VALUE" IS NOT NULL)',
            name="ck_WORKFLOW_BINDING_constant",
        ),
        sa.CheckConstraint(
            '("SOURCE_KIND" = \'STEP_OUTPUT\') = ("SOURCE_STEP_ID" IS NOT NULL AND "SOURCE_PORT_ID" IS NOT NULL)',
            name="ck_WORKFLOW_BINDING_step_source",
        ),
        sa.CheckConstraint('"ORDINAL" >= 0', name="ck_WORKFLOW_BINDING_ordinal"),
        sa.CheckConstraint(
            '("SOURCE_KIND" IN (\'REQUEST\', \'CONTEXT\')) = ("SOURCE_PATH" IS NOT NULL AND "SOURCE_STEP_ID" IS NULL AND "SOURCE_PORT_ID" IS NULL AND "CONSTANT_VALUE" IS NULL)',
            name="ck_WORKFLOW_BINDING_request_context",
        ),
        sa.CheckConstraint(
            '"SOURCE_KIND" <> \'CONSTANT\' OR "SOURCE_PATH" IS NULL',
            name="ck_WORKFLOW_BINDING_constant_path",
        ),
        sa.ForeignKeyConstraint(
            ["SOURCE_PORT_ID"], ["STEP_TYPE_PORT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["SOURCE_STEP_ID"], ["WORKFLOW_STEP.ID"], onupdate="RESTRICT", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["TARGET_PORT_ID"], ["STEP_TYPE_PORT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_STEP_ID"], ["WORKFLOW_STEP.ID"], onupdate="RESTRICT", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint(
            "WORKFLOW_STEP_ID",
            "TARGET_PORT_ID",
            "ORDINAL",
            name="uq_WORKFLOW_BINDING_target_ordinal",
        ),
    )
    op.create_index(
        "ix_WORKFLOW_BINDING_target_port", "WORKFLOW_STEP_INPUT_BINDING", ["TARGET_PORT_ID"]
    )
    op.create_index(
        "ix_WORKFLOW_BINDING_source_step", "WORKFLOW_STEP_INPUT_BINDING", ["SOURCE_STEP_ID"]
    )
    op.create_index(
        "ix_WORKFLOW_BINDING_source_port", "WORKFLOW_STEP_INPUT_BINDING", ["SOURCE_PORT_ID"]
    )
    op.create_table(
        "WORKFLOW_STEP_TARGET",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("WORKFLOW_STEP_ID", sa.Uuid(), nullable=False),
        sa.Column("USER_ID", sa.Uuid(), nullable=True),
        sa.Column("WORK_GROUP_ID", sa.Uuid(), nullable=True),
        sa.Column("CONDITION", sa.String(length=1024), nullable=True),
        sa.Column("PRIORITY", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_WORKFLOW_TARGET_priority"),
        sa.CheckConstraint(
            '(num_nonnulls("USER_ID", "WORK_GROUP_ID") = 1)', name="ck_WORKFLOW_TARGET_principal"
        ),
        sa.ForeignKeyConstraint(["USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_STEP_ID"], ["WORKFLOW_STEP.ID"], onupdate="RESTRICT", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["WORK_GROUP_ID"], ["WORK_GROUP.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("WORKFLOW_STEP_ID", "USER_ID", name="uq_WORKFLOW_TARGET_user"),
        sa.UniqueConstraint("WORKFLOW_STEP_ID", "WORK_GROUP_ID", name="uq_WORKFLOW_TARGET_group"),
    )
    op.create_index("ix_WORKFLOW_TARGET_user", "WORKFLOW_STEP_TARGET", ["USER_ID"])
    op.create_index("ix_WORKFLOW_TARGET_group", "WORKFLOW_STEP_TARGET", ["WORK_GROUP_ID"])
    op.create_table(
        "WORKFLOW_TRANSITION",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("WORKFLOW_VERSION_ID", sa.Uuid(), nullable=False),
        sa.Column("SOURCE_STEP_ID", sa.Uuid(), nullable=False),
        sa.Column("TARGET_STEP_ID", sa.Uuid(), nullable=False),
        sa.Column("OUTCOME", sa.String(length=64), nullable=False),
        sa.Column("CONDITION", sa.String(length=1024), nullable=True),
        sa.Column("IS_DEFAULT", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("PRIORITY", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            '"SOURCE_STEP_ID" <> "TARGET_STEP_ID"', name="ck_WORKFLOW_TRANSITION_no_self"
        ),
        sa.CheckConstraint('"PRIORITY" >= 0', name="ck_WORKFLOW_TRANSITION_priority"),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_VERSION_ID", "SOURCE_STEP_ID"],
            ["WORKFLOW_STEP.WORKFLOW_VERSION_ID", "WORKFLOW_STEP.ID"],
            name="fk_WORKFLOW_TRANSITION_source",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_VERSION_ID", "TARGET_STEP_ID"],
            ["WORKFLOW_STEP.WORKFLOW_VERSION_ID", "WORKFLOW_STEP.ID"],
            name="fk_WORKFLOW_TRANSITION_target",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_VERSION_ID"],
            ["WORKFLOW_VERSION.ID"],
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint(
            "SOURCE_STEP_ID", "OUTCOME", "PRIORITY", name="uq_WORKFLOW_TRANSITION_choice"
        ),
    )
    op.create_index(
        "uq_WORKFLOW_TRANSITION_default",
        "WORKFLOW_TRANSITION",
        ["SOURCE_STEP_ID", "OUTCOME"],
        unique=True,
        postgresql_where=sa.text('"IS_DEFAULT"'),
    )
    op.create_index("ix_WORKFLOW_TRANSITION_target", "WORKFLOW_TRANSITION", ["TARGET_STEP_ID"])
    op.create_index(
        "ix_WORKFLOW_TRANSITION_choice",
        "WORKFLOW_TRANSITION",
        ["SOURCE_STEP_ID", "OUTCOME", sa.text('"PRIORITY" DESC'), "ID"],
    )
    _install_immutability_versioned_workflow_authoring()


def _downgrade_versioned_workflow_authoring() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        "uq_WORKFLOW_TRANSITION_default",
        table_name="WORKFLOW_TRANSITION",
        postgresql_where=sa.text('"IS_DEFAULT"'),
    )
    op.drop_table("WORKFLOW_TRANSITION")
    op.drop_table("WORKFLOW_STEP_TARGET")
    op.drop_table("WORKFLOW_STEP_INPUT_BINDING")
    op.drop_index(
        "ix_WORKFLOW_VERSION_HISTORY_entity_changed", table_name="WORKFLOW_VERSION_HISTORY"
    )
    op.drop_index(
        op.f("ix_WORKFLOW_VERSION_HISTORY_TRACE_ID"), table_name="WORKFLOW_VERSION_HISTORY"
    )
    op.drop_index(
        op.f("ix_WORKFLOW_VERSION_HISTORY_REQUEST_ID"), table_name="WORKFLOW_VERSION_HISTORY"
    )
    op.drop_index(
        op.f("ix_WORKFLOW_VERSION_HISTORY_ENTITY_ID"), table_name="WORKFLOW_VERSION_HISTORY"
    )
    op.drop_index(
        op.f("ix_WORKFLOW_VERSION_HISTORY_CHANGED_AT"), table_name="WORKFLOW_VERSION_HISTORY"
    )
    op.drop_table("WORKFLOW_VERSION_HISTORY")
    op.drop_index("ix_WORKFLOW_STEP_version_order", table_name="WORKFLOW_STEP")
    op.drop_index(op.f("ix_WORKFLOW_STEP_CREATED_AT"), table_name="WORKFLOW_STEP")
    op.drop_table("WORKFLOW_STEP")
    op.drop_index("ix_WORKFLOW_VERSION_definition_status", table_name="WORKFLOW_VERSION")
    op.drop_index(op.f("ix_WORKFLOW_VERSION_CREATED_AT"), table_name="WORKFLOW_VERSION")
    op.drop_table("WORKFLOW_VERSION")
    op.drop_index(
        "ix_WORKFLOW_DEFINITION_HISTORY_entity_changed", table_name="WORKFLOW_DEFINITION_HISTORY"
    )
    op.drop_index(
        op.f("ix_WORKFLOW_DEFINITION_HISTORY_TRACE_ID"), table_name="WORKFLOW_DEFINITION_HISTORY"
    )
    op.drop_index(
        op.f("ix_WORKFLOW_DEFINITION_HISTORY_REQUEST_ID"), table_name="WORKFLOW_DEFINITION_HISTORY"
    )
    op.drop_index(
        op.f("ix_WORKFLOW_DEFINITION_HISTORY_ENTITY_ID"), table_name="WORKFLOW_DEFINITION_HISTORY"
    )
    op.drop_index(
        op.f("ix_WORKFLOW_DEFINITION_HISTORY_CHANGED_AT"), table_name="WORKFLOW_DEFINITION_HISTORY"
    )
    op.drop_table("WORKFLOW_DEFINITION_HISTORY")
    op.drop_index(
        "uq_WORKFLOW_ACCESS_GRANT_user",
        table_name="WORKFLOW_ACCESS_GRANT",
        postgresql_where=sa.text('"USER_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
    )
    op.drop_index(
        "uq_WORKFLOW_ACCESS_GRANT_group",
        table_name="WORKFLOW_ACCESS_GRANT",
        postgresql_where=sa.text('"WORK_GROUP_ID" IS NOT NULL AND "DELETED_AT" IS NULL'),
    )
    op.drop_index(op.f("ix_WORKFLOW_ACCESS_GRANT_CREATED_AT"), table_name="WORKFLOW_ACCESS_GRANT")
    op.drop_table("WORKFLOW_ACCESS_GRANT")
    op.drop_index(
        "uq_WORKFLOW_DEFINITION_code_active",
        table_name="WORKFLOW_DEFINITION",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index("ix_WORKFLOW_DEFINITION_owner_active", table_name="WORKFLOW_DEFINITION")
    op.drop_index("ix_WORKFLOW_DEFINITION_access_active", table_name="WORKFLOW_DEFINITION")
    op.drop_index(op.f("ix_WORKFLOW_DEFINITION_CREATED_AT"), table_name="WORKFLOW_DEFINITION")
    op.drop_table("WORKFLOW_DEFINITION")
    op.execute("DROP FUNCTION protect_workflow_graph()")
    op.execute("DROP FUNCTION protect_workflow_version()")


# Typed transform handler v2

_CONFIG_SCHEMA = {
    "$defs": {"JsonValue": {}},
    "additionalProperties": False,
    "properties": {
        "conversion_key": {
            "enum": [
                "string",
                "integer",
                "decimal",
                "boolean",
                "date",
                "date_time",
                "array",
                "object",
            ],
            "title": "Conversion Key",
            "type": "string",
        },
        "null_behavior": {
            "default": "error",
            "enum": ["error", "preserve", "default"],
            "title": "Null Behavior",
            "type": "string",
        },
        "default": {
            "anyOf": [{"$ref": "#/$defs/JsonValue"}, {"type": "null"}],
            "default": None,
        },
        "format": {
            "anyOf": [{"maxLength": 128, "type": "string"}, {"type": "null"}],
            "default": None,
            "title": "Format",
        },
        "projection": {
            "anyOf": [
                {
                    "additionalProperties": {"type": "string"},
                    "maxProperties": 64,
                    "type": "object",
                },
                {"type": "null"},
            ],
            "default": None,
            "title": "Projection",
        },
    },
    "required": ["conversion_key"],
    "title": "TransformConfigV2",
    "type": "object",
}


_VALUE_SCHEMA = {
    "$defs": {"JsonValue": {}},
    "anyOf": [{"$ref": "#/$defs/JsonValue"}, {"type": "null"}],
}


def _upgrade_typed_transform_handler_v2() -> None:
    """Publish the additive transform contract without changing version 1."""
    connection = op.get_bind()
    version_id = connection.execute(
        sa.text("""
            INSERT INTO "STEP_TYPE_VERSION"
                ("STEP_TYPE_ID", "NUMBER", "STATUS", "HANDLER_KEY", "HANDLER_VERSION",
                 "EXECUTION_MODE", "CONFIG_SCHEMA", "VERSION", "CREATED_AT")
            SELECT "ID", 2, 'DRAFT', 'transform', '2', 'SYNC',
                   CAST(:config_schema AS jsonb), 1, now()
            FROM "STEP_TYPE" WHERE "CODE" = 'TRANSFORM' AND "DELETED_AT" IS NULL
            RETURNING "ID"
        """).bindparams(config_schema=json.dumps(_CONFIG_SCHEMA))
    ).scalar_one()
    for direction, key in (("INPUT", "value"), ("OUTPUT", "result")):
        connection.execute(
            sa.text("""
                INSERT INTO "STEP_TYPE_PORT"
                    ("STEP_TYPE_VERSION_ID", "DIRECTION", "PORT_KEY", "VALUE_SCHEMA",
                     "REQUIRED", "NULLABLE", "CARDINALITY", "CREATED_AT")
                VALUES (:version_id, :direction, :port_key, CAST(:value_schema AS jsonb),
                        true, true, 'SCALAR', now())
            """).bindparams(
                version_id=version_id,
                direction=direction,
                port_key=key,
                value_schema=json.dumps(_VALUE_SCHEMA),
            )
        )
    connection.execute(
        sa.text("""
            UPDATE "STEP_TYPE_VERSION"
            SET "STATUS" = 'PUBLISHED', "PUBLISHED_AT" = now(), "UPDATED_AT" = now()
            WHERE "ID" = :version_id
        """).bindparams(version_id=version_id)
    )


def _downgrade_typed_transform_handler_v2() -> None:
    """Remove only transform v2, retaining the original published contract."""
    op.execute('DROP TRIGGER step_type_port_immutable ON "STEP_TYPE_PORT"')
    op.execute('DROP TRIGGER step_type_version_immutable ON "STEP_TYPE_VERSION"')
    op.execute("""
        DELETE FROM "STEP_TYPE_PORT"
        WHERE "STEP_TYPE_VERSION_ID" IN (
            SELECT "ID" FROM "STEP_TYPE_VERSION"
            WHERE "HANDLER_KEY" = 'transform' AND "HANDLER_VERSION" = '2'
        )
    """)
    op.execute("""
        DELETE FROM "STEP_TYPE_VERSION"
        WHERE "HANDLER_KEY" = 'transform' AND "HANDLER_VERSION" = '2'
    """)
    op.execute("""CREATE TRIGGER step_type_version_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON "STEP_TYPE_VERSION"
        FOR EACH ROW EXECUTE FUNCTION protect_step_type_version()""")
    op.execute("""CREATE TRIGGER step_type_port_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON "STEP_TYPE_PORT"
        FOR EACH ROW EXECUTE FUNCTION protect_step_type_port()""")


# Request types and business request


def _upgrade_request_types_and_business_request() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "REQUEST_TYPE",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("WORKFLOW_DEFINITION_ID", sa.Uuid(), nullable=False),
        sa.Column("FORM_DEFINITION_ID", sa.Uuid(), nullable=False),
        sa.Column("IS_ACTIVE", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("DEFAULT_PRIORITY", sa.Integer(), nullable=True),
        sa.Column("EXTENSION_CONTRACT", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            '"DEFAULT_PRIORITY" IS NULL OR "DEFAULT_PRIORITY" BETWEEN 0 AND 9',
            name="ck_REQUEST_TYPE_priority",
        ),
        sa.CheckConstraint(
            'length("CODE") > 0 AND length("NAME") > 0', name="ck_REQUEST_TYPE_names"
        ),
        sa.ForeignKeyConstraint(
            ["FORM_DEFINITION_ID"], ["FORM_DEFINITION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_DEFINITION_ID"],
            ["WORKFLOW_DEFINITION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_CREATED_AT"), "REQUEST_TYPE", ["CREATED_AT"], unique=False
    )
    op.create_index("ix_REQUEST_TYPE_form", "REQUEST_TYPE", ["FORM_DEFINITION_ID"], unique=False)
    op.create_index(
        "ix_REQUEST_TYPE_workflow_active",
        "REQUEST_TYPE",
        ["WORKFLOW_DEFINITION_ID", "IS_ACTIVE"],
        unique=False,
    )
    op.create_index(
        "uq_REQUEST_TYPE_code_active",
        "REQUEST_TYPE",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "BUSINESS_REQUEST",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("REQUEST_TYPE_ID", sa.Uuid(), nullable=False),
        sa.Column("REQUESTER_USER_ID", sa.Uuid(), nullable=False),
        sa.Column("WORKFLOW_VERSION_ID", sa.Uuid(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("PRIORITY", sa.Integer(), nullable=False),
        sa.Column("SUBMITTED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("CLOSED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("SUBMIT_KEY", sa.String(length=128), nullable=True),
        sa.Column("SUBMIT_PAYLOAD_HASH", sa.String(length=64), nullable=True),
        sa.Column(
            "START_COMMAND",
            postgresql.JSONB(astext_type=sa.Text(), none_as_null=True),
            nullable=True,
        ),
        sa.CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_BUSINESS_REQUEST_priority"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('DRAFT','SUBMITTED','RUNNING','COMPLETED','FAILED','CANCELLED')",
            name="ck_BUSINESS_REQUEST_status",
        ),
        sa.CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "SUBMITTED_AT" IS NULL AND "CLOSED_AT" IS NULL AND "START_COMMAND" IS NULL) OR ("STATUS" IN (\'SUBMITTED\',\'RUNNING\') AND "SUBMITTED_AT" IS NOT NULL AND "CLOSED_AT" IS NULL AND "START_COMMAND" IS NOT NULL) OR ("STATUS" IN (\'COMPLETED\',\'FAILED\',\'CANCELLED\') AND "CLOSED_AT" IS NOT NULL)',
            name="ck_BUSINESS_REQUEST_lifecycle",
        ),
        sa.CheckConstraint(
            '("SUBMIT_KEY" IS NULL) = ("SUBMIT_PAYLOAD_HASH" IS NULL)',
            name="ck_BUSINESS_REQUEST_submit_pair",
        ),
        sa.ForeignKeyConstraint(
            ["REQUESTER_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["REQUEST_TYPE_ID"], ["REQUEST_TYPE.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_VERSION_ID"],
            ["WORKFLOW_VERSION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_BUSINESS_REQUEST_CREATED_AT"), "BUSINESS_REQUEST", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_BUSINESS_REQUEST_requester_status_created",
        "BUSINESS_REQUEST",
        ["REQUESTER_USER_ID", "STATUS", sa.literal_column('"CREATED_AT" DESC'), "ID"],
        unique=False,
    )
    op.create_index(
        "ix_BUSINESS_REQUEST_status_priority_created",
        "BUSINESS_REQUEST",
        ["STATUS", sa.literal_column('"PRIORITY" DESC'), "CREATED_AT", "ID"],
        unique=False,
    )
    op.create_index(
        "ix_BUSINESS_REQUEST_type", "BUSINESS_REQUEST", ["REQUEST_TYPE_ID"], unique=False
    )
    op.create_index(
        "ix_BUSINESS_REQUEST_workflow_version",
        "BUSINESS_REQUEST",
        ["WORKFLOW_VERSION_ID"],
        unique=False,
    )
    op.create_index(
        "uq_BUSINESS_REQUEST_submit",
        "BUSINESS_REQUEST",
        ["REQUESTER_USER_ID", "SUBMIT_KEY"],
        unique=True,
        postgresql_where=sa.text('"SUBMIT_KEY" IS NOT NULL'),
    )
    op.create_table(
        "REQUEST_TYPE_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_WORKFLOW_DEFINITION_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF WORKFLOW_DEFINITION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_WORKFLOW_DEFINITION_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF WORKFLOW_DEFINITION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_FORM_DEFINITION_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF FORM_DEFINITION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_FORM_DEFINITION_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF FORM_DEFINITION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DEFAULT_PRIORITY",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF DEFAULT_PRIORITY FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DEFAULT_PRIORITY",
            sa.Integer(),
            nullable=True,
            comment="TO VALUE OF DEFAULT_PRIORITY FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_EXTENSION_CONTRACT",
            sa.String(length=128),
            nullable=True,
            comment="FROM VALUE OF EXTENSION_CONTRACT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_EXTENSION_CONTRACT",
            sa.String(length=128),
            nullable=True,
            comment="TO VALUE OF EXTENSION_CONTRACT FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["REQUEST_TYPE.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_HISTORY_CHANGED_AT"),
        "REQUEST_TYPE_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_HISTORY_ENTITY_ID"),
        "REQUEST_TYPE_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_HISTORY_REQUEST_ID"),
        "REQUEST_TYPE_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_HISTORY_TRACE_ID"), "REQUEST_TYPE_HISTORY", ["TRACE_ID"], unique=False
    )
    op.create_index(
        "ix_REQUEST_TYPE_HISTORY_entity_changed",
        "REQUEST_TYPE_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "FORM_SUBMISSION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("BUSINESS_REQUEST_ID", sa.Uuid(), nullable=False),
        sa.Column("FORM_VERSION_ID", sa.Uuid(), nullable=False),
        sa.Column("STEP_EXECUTION_ID", sa.Uuid(), nullable=True),
        sa.Column("SUBMITTED_BY_USER_ID", sa.Uuid(), nullable=True),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column(
            "DATA",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("SUBMITTED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "\"STATUS\" IN ('DRAFT','SUBMITTED','ABANDONED')", name="ck_FORM_SUBMISSION_status"
        ),
        sa.CheckConstraint(
            '("STATUS" = \'DRAFT\' AND "SUBMITTED_AT" IS NULL AND "SUBMITTED_BY_USER_ID" IS NULL) OR ("STATUS" = \'SUBMITTED\' AND "SUBMITTED_AT" IS NOT NULL AND "SUBMITTED_BY_USER_ID" IS NOT NULL) OR "STATUS" = \'ABANDONED\'',
            name="ck_FORM_SUBMISSION_lifecycle",
        ),
        sa.ForeignKeyConstraint(
            ["BUSINESS_REQUEST_ID"],
            ["BUSINESS_REQUEST.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["FORM_VERSION_ID"], ["FORM_VERSION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["SUBMITTED_BY_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("BUSINESS_REQUEST_ID", name="uq_FORM_SUBMISSION_request"),
    )
    op.create_index(
        op.f("ix_FORM_SUBMISSION_CREATED_AT"), "FORM_SUBMISSION", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_FORM_SUBMISSION_actor", "FORM_SUBMISSION", ["SUBMITTED_BY_USER_ID"], unique=False
    )
    op.create_index("ix_FORM_SUBMISSION_form", "FORM_SUBMISSION", ["FORM_VERSION_ID"], unique=False)
    op.execute("""
        CREATE FUNCTION protect_business_request_pins() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD."STATUS" <> 'DRAFT' THEN
                RAISE EXCEPTION 'Submitted business request is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD."STATUS" <> 'DRAFT' AND (
                NEW."REQUEST_TYPE_ID" IS DISTINCT FROM OLD."REQUEST_TYPE_ID" OR
                NEW."REQUESTER_USER_ID" IS DISTINCT FROM OLD."REQUESTER_USER_ID" OR
                NEW."WORKFLOW_VERSION_ID" IS DISTINCT FROM OLD."WORKFLOW_VERSION_ID" OR
                NEW."PRIORITY" IS DISTINCT FROM OLD."PRIORITY" OR
                NEW."SUBMITTED_AT" IS DISTINCT FROM OLD."SUBMITTED_AT" OR
                NEW."SUBMIT_KEY" IS DISTINCT FROM OLD."SUBMIT_KEY" OR
                NEW."SUBMIT_PAYLOAD_HASH" IS DISTINCT FROM OLD."SUBMIT_PAYLOAD_HASH" OR
                NEW."START_COMMAND" IS DISTINCT FROM OLD."START_COMMAND"
            ) THEN
                RAISE EXCEPTION 'Submitted business request pins are immutable' USING ERRCODE = '23514';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$;
    """)
    op.execute("""CREATE TRIGGER business_request_pins_immutable
        BEFORE UPDATE OR DELETE ON "BUSINESS_REQUEST"
        FOR EACH ROW EXECUTE FUNCTION protect_business_request_pins()""")
    op.execute("""
        CREATE FUNCTION protect_form_submission() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD."STATUS" <> 'DRAFT' THEN
                RAISE EXCEPTION 'Submitted form data is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD."STATUS" <> 'DRAFT' AND (
                NEW."BUSINESS_REQUEST_ID" IS DISTINCT FROM OLD."BUSINESS_REQUEST_ID" OR
                NEW."FORM_VERSION_ID" IS DISTINCT FROM OLD."FORM_VERSION_ID" OR
                NEW."SUBMITTED_BY_USER_ID" IS DISTINCT FROM OLD."SUBMITTED_BY_USER_ID" OR
                NEW."STATUS" IS DISTINCT FROM OLD."STATUS" OR
                NEW."DATA" IS DISTINCT FROM OLD."DATA" OR
                NEW."SUBMITTED_AT" IS DISTINCT FROM OLD."SUBMITTED_AT"
            ) THEN
                RAISE EXCEPTION 'Submitted form data and version pin are immutable' USING ERRCODE = '23514';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$;
    """)
    op.execute("""CREATE TRIGGER form_submission_immutable
        BEFORE UPDATE OR DELETE ON "FORM_SUBMISSION"
        FOR EACH ROW EXECUTE FUNCTION protect_form_submission()""")


def _downgrade_request_types_and_business_request() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute('DROP TRIGGER form_submission_immutable ON "FORM_SUBMISSION"')
    op.execute("DROP FUNCTION protect_form_submission()")
    op.execute('DROP TRIGGER business_request_pins_immutable ON "BUSINESS_REQUEST"')
    op.execute("DROP FUNCTION protect_business_request_pins()")
    op.drop_index("ix_FORM_SUBMISSION_form", table_name="FORM_SUBMISSION")
    op.drop_index("ix_FORM_SUBMISSION_actor", table_name="FORM_SUBMISSION")
    op.drop_index(op.f("ix_FORM_SUBMISSION_CREATED_AT"), table_name="FORM_SUBMISSION")
    op.drop_table("FORM_SUBMISSION")
    op.drop_index("ix_REQUEST_TYPE_HISTORY_entity_changed", table_name="REQUEST_TYPE_HISTORY")
    op.drop_index(op.f("ix_REQUEST_TYPE_HISTORY_TRACE_ID"), table_name="REQUEST_TYPE_HISTORY")
    op.drop_index(op.f("ix_REQUEST_TYPE_HISTORY_REQUEST_ID"), table_name="REQUEST_TYPE_HISTORY")
    op.drop_index(op.f("ix_REQUEST_TYPE_HISTORY_ENTITY_ID"), table_name="REQUEST_TYPE_HISTORY")
    op.drop_index(op.f("ix_REQUEST_TYPE_HISTORY_CHANGED_AT"), table_name="REQUEST_TYPE_HISTORY")
    op.drop_table("REQUEST_TYPE_HISTORY")
    op.drop_index(
        "uq_BUSINESS_REQUEST_submit",
        table_name="BUSINESS_REQUEST",
        postgresql_where=sa.text('"SUBMIT_KEY" IS NOT NULL'),
    )
    op.drop_index("ix_BUSINESS_REQUEST_workflow_version", table_name="BUSINESS_REQUEST")
    op.drop_index("ix_BUSINESS_REQUEST_type", table_name="BUSINESS_REQUEST")
    op.drop_index("ix_BUSINESS_REQUEST_status_priority_created", table_name="BUSINESS_REQUEST")
    op.drop_index("ix_BUSINESS_REQUEST_requester_status_created", table_name="BUSINESS_REQUEST")
    op.drop_index(op.f("ix_BUSINESS_REQUEST_CREATED_AT"), table_name="BUSINESS_REQUEST")
    op.drop_table("BUSINESS_REQUEST")
    op.drop_index(
        "uq_REQUEST_TYPE_code_active",
        table_name="REQUEST_TYPE",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index("ix_REQUEST_TYPE_workflow_active", table_name="REQUEST_TYPE")
    op.drop_index("ix_REQUEST_TYPE_form", table_name="REQUEST_TYPE")
    op.drop_index(op.f("ix_REQUEST_TYPE_CREATED_AT"), table_name="REQUEST_TYPE")
    op.drop_table("REQUEST_TYPE")


# Durable single token process runtime


def _upgrade_durable_single_token_process_runtime() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "PROCESS_INSTANCE",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("BUSINESS_REQUEST_ID", sa.Uuid(), nullable=False),
        sa.Column("WORKFLOW_VERSION_ID", sa.Uuid(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("STARTED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ENDED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("LAST_ERROR_CODE", sa.String(length=128), nullable=True),
        sa.Column("EVENT_SEQUENCE", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint('"DELETED_AT" IS NULL', name="ck_PROCESS_INSTANCE_not_deleted"),
        sa.CheckConstraint('"EVENT_SEQUENCE" >= 0', name="ck_PROCESS_INSTANCE_sequence"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('RUNNING','WAITING','PAUSED','COMPLETED','FAILED','CANCELLED')",
            name="ck_PROCESS_INSTANCE_status",
        ),
        sa.CheckConstraint(
            "(\"STATUS\" IN ('COMPLETED','FAILED','CANCELLED')) = (\"ENDED_AT\" IS NOT NULL)",
            name="ck_PROCESS_INSTANCE_terminal",
        ),
        sa.ForeignKeyConstraint(
            ["BUSINESS_REQUEST_ID"],
            ["BUSINESS_REQUEST.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_VERSION_ID"],
            ["WORKFLOW_VERSION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("BUSINESS_REQUEST_ID", name="uq_PROCESS_INSTANCE_request"),
    )
    op.create_index(
        op.f("ix_PROCESS_INSTANCE_CREATED_AT"), "PROCESS_INSTANCE", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_PROCESS_INSTANCE_status_started",
        "PROCESS_INSTANCE",
        ["STATUS", "STARTED_AT", "ID"],
        unique=False,
    )
    op.create_index(
        "ix_PROCESS_INSTANCE_workflow", "PROCESS_INSTANCE", ["WORKFLOW_VERSION_ID"], unique=False
    )
    op.create_table(
        "EXECUTION_TOKEN",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("PROCESS_INSTANCE_ID", sa.Uuid(), nullable=False),
        sa.Column("CURRENT_STEP_ID", sa.Uuid(), nullable=True),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("BRANCH_KEY", sa.String(length=128), nullable=True),
        sa.Column("PARENT_TOKEN_ID", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            '"BRANCH_KEY" IS NULL AND "PARENT_TOKEN_ID" IS NULL',
            name="ck_EXECUTION_TOKEN_phase1_single_path",
        ),
        sa.CheckConstraint('"DELETED_AT" IS NULL', name="ck_EXECUTION_TOKEN_not_deleted"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('ACTIVE','WAITING','COMPLETED','CANCELLED','FAILED')",
            name="ck_EXECUTION_TOKEN_status",
        ),
        sa.ForeignKeyConstraint(
            ["CURRENT_STEP_ID"], ["WORKFLOW_STEP.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["PARENT_TOKEN_ID"], ["EXECUTION_TOKEN.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["PROCESS_INSTANCE_ID"],
            ["PROCESS_INSTANCE.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_EXECUTION_TOKEN_CREATED_AT"), "EXECUTION_TOKEN", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_EXECUTION_TOKEN_parent", "EXECUTION_TOKEN", ["PARENT_TOKEN_ID"], unique=False
    )
    op.create_index(
        "ix_EXECUTION_TOKEN_process_status",
        "EXECUTION_TOKEN",
        ["PROCESS_INSTANCE_ID", "STATUS", "ID"],
        unique=False,
    )
    op.create_index("ix_EXECUTION_TOKEN_step", "EXECUTION_TOKEN", ["CURRENT_STEP_ID"], unique=False)
    op.create_index(
        "uq_EXECUTION_TOKEN_live_process",
        "EXECUTION_TOKEN",
        ["PROCESS_INSTANCE_ID"],
        unique=True,
        postgresql_where=sa.text("\"STATUS\" IN ('ACTIVE','WAITING')"),
    )
    op.create_table(
        "STEP_EXECUTION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("PROCESS_INSTANCE_ID", sa.Uuid(), nullable=False),
        sa.Column("EXECUTION_TOKEN_ID", sa.Uuid(), nullable=False),
        sa.Column("WORKFLOW_STEP_ID", sa.Uuid(), nullable=False),
        sa.Column("VISIT_NUMBER", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("WAIT_KIND", sa.String(length=16), nullable=True),
        sa.Column(
            "INPUT_SNAPSHOT",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "OUTPUT_SNAPSHOT",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("STARTED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ENDED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("LAST_ERROR_CODE", sa.String(length=128), nullable=True),
        sa.CheckConstraint('"DELETED_AT" IS NULL', name="ck_STEP_EXECUTION_not_deleted"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('PENDING','RUNNING','WAITING','COMPLETED','FAILED','CANCELLED','TIMED_OUT')",
            name="ck_STEP_EXECUTION_status",
        ),
        sa.CheckConstraint('"VISIT_NUMBER" > 0', name="ck_STEP_EXECUTION_visit"),
        sa.CheckConstraint(
            "\"WAIT_KIND\" IS NULL OR \"WAIT_KIND\" IN ('HUMAN','EVENT','TIMER','BACKGROUND')",
            name="ck_STEP_EXECUTION_wait_kind",
        ),
        sa.ForeignKeyConstraint(
            ["EXECUTION_TOKEN_ID"], ["EXECUTION_TOKEN.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["PROCESS_INSTANCE_ID"],
            ["PROCESS_INSTANCE.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_STEP_ID"], ["WORKFLOW_STEP.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint(
            "EXECUTION_TOKEN_ID", "WORKFLOW_STEP_ID", "VISIT_NUMBER", name="uq_STEP_EXECUTION_visit"
        ),
    )
    op.create_index(
        op.f("ix_STEP_EXECUTION_CREATED_AT"), "STEP_EXECUTION", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_STEP_EXECUTION_process_status",
        "STEP_EXECUTION",
        ["PROCESS_INSTANCE_ID", "STATUS", "ID"],
        unique=False,
    )
    op.create_index(
        "ix_STEP_EXECUTION_step_status",
        "STEP_EXECUTION",
        ["WORKFLOW_STEP_ID", "STATUS"],
        unique=False,
    )
    op.create_index(
        "ix_STEP_EXECUTION_token", "STEP_EXECUTION", ["EXECUTION_TOKEN_ID"], unique=False
    )
    op.create_table(
        "PROCESS_TRANSITION",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("PROCESS_INSTANCE_ID", sa.Uuid(), nullable=False),
        sa.Column("FROM_STEP_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("TO_STEP_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("WORKFLOW_TRANSITION_ID", sa.Uuid(), nullable=False),
        sa.Column("OUTCOME_KEY", sa.String(length=64), nullable=False),
        sa.Column("TAKEN_AT", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["FROM_STEP_EXECUTION_ID"],
            ["STEP_EXECUTION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["PROCESS_INSTANCE_ID"],
            ["PROCESS_INSTANCE.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["TO_STEP_EXECUTION_ID"],
            ["STEP_EXECUTION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["WORKFLOW_TRANSITION_ID"],
            ["WORKFLOW_TRANSITION.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint(
            "FROM_STEP_EXECUTION_ID", "WORKFLOW_TRANSITION_ID", name="uq_PROCESS_TRANSITION_once"
        ),
    )
    op.create_index(
        "ix_PROCESS_TRANSITION_process_taken",
        "PROCESS_TRANSITION",
        ["PROCESS_INSTANCE_ID", "TAKEN_AT", "ID"],
        unique=False,
    )
    op.create_index(
        "ix_PROCESS_TRANSITION_to", "PROCESS_TRANSITION", ["TO_STEP_EXECUTION_ID"], unique=False
    )
    op.create_index(
        "ix_PROCESS_TRANSITION_workflow",
        "PROCESS_TRANSITION",
        ["WORKFLOW_TRANSITION_ID"],
        unique=False,
    )
    op.create_table(
        "STEP_EXECUTION_ATTEMPT",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("STEP_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("NUMBER", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("DISPATCH_KEY", sa.String(length=160), nullable=False),
        sa.Column("STARTED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ENDED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ERROR_CODE", sa.String(length=128), nullable=True),
        sa.Column(
            "ERROR_DETAILS",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("TASK_EXECUTION_ID", sa.Uuid(), nullable=True),
        sa.CheckConstraint('"NUMBER" > 0', name="ck_STEP_EXECUTION_ATTEMPT_number"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('RUNNING','WAITING','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')",
            name="ck_STEP_EXECUTION_ATTEMPT_status",
        ),
        sa.ForeignKeyConstraint(
            ["STEP_EXECUTION_ID"], ["STEP_EXECUTION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["TASK_EXECUTION_ID"], ["TASK_EXECUTION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("DISPATCH_KEY", name="uq_STEP_EXECUTION_ATTEMPT_dispatch"),
        sa.UniqueConstraint("STEP_EXECUTION_ID", "NUMBER", name="uq_STEP_EXECUTION_ATTEMPT_number"),
    )
    op.create_index(
        "ix_STEP_EXECUTION_ATTEMPT_status_started",
        "STEP_EXECUTION_ATTEMPT",
        ["STATUS", "STARTED_AT"],
        unique=False,
    )
    op.create_index(
        "ix_STEP_EXECUTION_ATTEMPT_task",
        "STEP_EXECUTION_ATTEMPT",
        ["TASK_EXECUTION_ID"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_FORM_SUBMISSION_step_execution",
        "FORM_SUBMISSION",
        "STEP_EXECUTION",
        ["STEP_EXECUTION_ID"],
        ["ID"],
        onupdate="RESTRICT",
        ondelete="RESTRICT",
    )
    op.execute("""
        CREATE FUNCTION protect_runtime_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Runtime rows cannot be deleted' USING ERRCODE = '23514';
        END $$
    """)
    for table in (
        "PROCESS_INSTANCE",
        "EXECUTION_TOKEN",
        "STEP_EXECUTION",
        "STEP_EXECUTION_ATTEMPT",
    ):
        op.execute(f'''CREATE TRIGGER {table.lower()}_no_delete
            BEFORE DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION protect_runtime_delete()''')
    op.execute("""
        CREATE FUNCTION protect_process_transition() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Process transitions are append-only' USING ERRCODE = '23514';
        END $$
    """)
    op.execute("""CREATE TRIGGER process_transition_append_only
        BEFORE UPDATE OR DELETE ON "PROCESS_TRANSITION"
        FOR EACH ROW EXECUTE FUNCTION protect_process_transition()""")
    op.execute("""
        CREATE FUNCTION protect_terminal_step() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD."STATUS" IN ('COMPLETED','FAILED','TIMED_OUT','CANCELLED')
                AND (NEW."INPUT_SNAPSHOT" IS DISTINCT FROM OLD."INPUT_SNAPSHOT"
                    OR NEW."OUTPUT_SNAPSHOT" IS DISTINCT FROM OLD."OUTPUT_SNAPSHOT"
                    OR NEW."WORKFLOW_STEP_ID" IS DISTINCT FROM OLD."WORKFLOW_STEP_ID") THEN
                RAISE EXCEPTION 'Terminal step snapshots are immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""CREATE TRIGGER step_execution_terminal_immutable
        BEFORE UPDATE ON "STEP_EXECUTION"
        FOR EACH ROW EXECUTE FUNCTION protect_terminal_step()""")
    op.execute("""
        CREATE FUNCTION protect_terminal_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD."STATUS" IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED') THEN
                RAISE EXCEPTION 'Terminal execution attempt is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""CREATE TRIGGER step_attempt_terminal_immutable
        BEFORE UPDATE ON "STEP_EXECUTION_ATTEMPT"
        FOR EACH ROW EXECUTE FUNCTION protect_terminal_attempt()""")


def _downgrade_durable_single_token_process_runtime() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute('DROP TRIGGER step_attempt_terminal_immutable ON "STEP_EXECUTION_ATTEMPT"')
    op.execute("DROP FUNCTION protect_terminal_attempt()")
    op.execute('DROP TRIGGER step_execution_terminal_immutable ON "STEP_EXECUTION"')
    op.execute("DROP FUNCTION protect_terminal_step()")
    op.execute('DROP TRIGGER process_transition_append_only ON "PROCESS_TRANSITION"')
    op.execute("DROP FUNCTION protect_process_transition()")
    for table in (
        "PROCESS_INSTANCE",
        "EXECUTION_TOKEN",
        "STEP_EXECUTION",
        "STEP_EXECUTION_ATTEMPT",
    ):
        op.execute(f'DROP TRIGGER {table.lower()}_no_delete ON "{table}"')
    op.execute("DROP FUNCTION protect_runtime_delete()")
    op.drop_constraint("fk_FORM_SUBMISSION_step_execution", "FORM_SUBMISSION", type_="foreignkey")
    op.drop_index("ix_STEP_EXECUTION_ATTEMPT_task", table_name="STEP_EXECUTION_ATTEMPT")
    op.drop_index("ix_STEP_EXECUTION_ATTEMPT_status_started", table_name="STEP_EXECUTION_ATTEMPT")
    op.drop_table("STEP_EXECUTION_ATTEMPT")
    op.drop_index("ix_PROCESS_TRANSITION_workflow", table_name="PROCESS_TRANSITION")
    op.drop_index("ix_PROCESS_TRANSITION_to", table_name="PROCESS_TRANSITION")
    op.drop_index("ix_PROCESS_TRANSITION_process_taken", table_name="PROCESS_TRANSITION")
    op.drop_table("PROCESS_TRANSITION")
    op.drop_index("ix_STEP_EXECUTION_token", table_name="STEP_EXECUTION")
    op.drop_index("ix_STEP_EXECUTION_step_status", table_name="STEP_EXECUTION")
    op.drop_index("ix_STEP_EXECUTION_process_status", table_name="STEP_EXECUTION")
    op.drop_index(op.f("ix_STEP_EXECUTION_CREATED_AT"), table_name="STEP_EXECUTION")
    op.drop_table("STEP_EXECUTION")
    op.drop_index(
        "uq_EXECUTION_TOKEN_live_process",
        table_name="EXECUTION_TOKEN",
        postgresql_where=sa.text("\"STATUS\" IN ('ACTIVE','WAITING')"),
    )
    op.drop_index("ix_EXECUTION_TOKEN_step", table_name="EXECUTION_TOKEN")
    op.drop_index("ix_EXECUTION_TOKEN_process_status", table_name="EXECUTION_TOKEN")
    op.drop_index("ix_EXECUTION_TOKEN_parent", table_name="EXECUTION_TOKEN")
    op.drop_index(op.f("ix_EXECUTION_TOKEN_CREATED_AT"), table_name="EXECUTION_TOKEN")
    op.drop_table("EXECUTION_TOKEN")
    op.drop_index("ix_PROCESS_INSTANCE_workflow", table_name="PROCESS_INSTANCE")
    op.drop_index("ix_PROCESS_INSTANCE_status_started", table_name="PROCESS_INSTANCE")
    op.drop_index(op.f("ix_PROCESS_INSTANCE_CREATED_AT"), table_name="PROCESS_INSTANCE")
    op.drop_table("PROCESS_INSTANCE")


# Background automation snapshot


def _upgrade_background_automation_snapshot() -> None:
    op.add_column(
        "STEP_EXECUTION_ATTEMPT",
        sa.Column(
            "AUTOMATION_SNAPSHOT",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )


def _downgrade_background_automation_snapshot() -> None:
    op.drop_column("STEP_EXECUTION_ATTEMPT", "AUTOMATION_SNAPSHOT")


# Form submission attachments


def _upgrade_form_submission_attachments() -> None:
    op.create_table(
        "FORM_SUBMISSION_ATTACHMENT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("FORM_SUBMISSION_ID", sa.Uuid(), nullable=False),
        sa.Column("FIELD_PATH", sa.String(1024), nullable=False),
        sa.Column("USER_UPLOAD_ID", sa.Uuid(), nullable=False),
        sa.Column("ADDED_BY_USER_ID", sa.Uuid(), nullable=False),
        sa.Column("CONTRIBUTING_GROUP_ID", sa.Uuid()),
        sa.Column("POSITION", sa.Integer(), nullable=False),
        sa.Column("CAPTION", sa.String(1024)),
        sa.Column("STATUS", sa.String(16), nullable=False),
        sa.Column("REMOVED_BY_USER_ID", sa.Uuid()),
        sa.Column("REMOVED_AT", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["FORM_SUBMISSION_ID"], ["FORM_SUBMISSION.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["USER_UPLOAD_ID"], ["USER_UPLOAD.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ADDED_BY_USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["CONTRIBUTING_GROUP_ID"], ["WORK_GROUP.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["REMOVED_BY_USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.CheckConstraint('"POSITION" >= 0', name="ck_FORM_SUBMISSION_ATTACHMENT_position"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('ACTIVE','REMOVED')", name="ck_FORM_SUBMISSION_ATTACHMENT_status"
        ),
        sa.CheckConstraint(
            '("STATUS" = \'ACTIVE\' AND "REMOVED_AT" IS NULL AND "REMOVED_BY_USER_ID" IS NULL) OR '
            '("STATUS" = \'REMOVED\' AND "REMOVED_AT" IS NOT NULL AND "REMOVED_BY_USER_ID" IS NOT NULL)',
            name="ck_FORM_SUBMISSION_ATTACHMENT_lifecycle",
        ),
    )
    op.create_index(
        "ix_FORM_SUBMISSION_ATTACHMENT_CREATED_AT", "FORM_SUBMISSION_ATTACHMENT", ["CREATED_AT"]
    )
    op.create_index(
        "uq_FORM_SUBMISSION_ATTACHMENT_active_position",
        "FORM_SUBMISSION_ATTACHMENT",
        ["FORM_SUBMISSION_ID", "FIELD_PATH", "POSITION"],
        unique=True,
        postgresql_where=sa.text("\"STATUS\" = 'ACTIVE'"),
    )
    for name, columns in (
        (
            "ix_FORM_SUBMISSION_ATTACHMENT_collection",
            ["FORM_SUBMISSION_ID", "FIELD_PATH", "STATUS", "POSITION"],
        ),
        ("ix_FORM_SUBMISSION_ATTACHMENT_upload", ["USER_UPLOAD_ID"]),
        ("ix_FORM_SUBMISSION_ATTACHMENT_added_by", ["ADDED_BY_USER_ID"]),
        ("ix_FORM_SUBMISSION_ATTACHMENT_group", ["CONTRIBUTING_GROUP_ID"]),
    ):
        op.create_index(name, "FORM_SUBMISSION_ATTACHMENT", columns)

    history_columns = [
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column("REQUEST_ID", sa.String(64), comment="REQUEST CORRELATION ID."),
        sa.Column("TRACE_ID", sa.String(64), comment="OPENTELEMETRY TRACE ID."),
        sa.Column("REASON", sa.String(1024), comment="OPTIONAL BUSINESS REASON FOR THE CHANGE."),
        sa.Column("SOURCE_IP", sa.String(64), comment="ORIGINATING CLIENT IP WHEN AVAILABLE."),
        sa.Column("USER_AGENT", sa.String(1024), comment="ORIGINATING USER AGENT WHEN AVAILABLE."),
    ]
    for name, kind in (
        ("FORM_SUBMISSION_ID", sa.Uuid()),
        ("FIELD_PATH", sa.String(1024)),
        ("USER_UPLOAD_ID", sa.Uuid()),
        ("ADDED_BY_USER_ID", sa.Uuid()),
        ("CONTRIBUTING_GROUP_ID", sa.Uuid()),
        ("POSITION", sa.Integer()),
        ("CAPTION", sa.String(1024)),
        ("STATUS", sa.String(16)),
        ("REMOVED_BY_USER_ID", sa.Uuid()),
        ("REMOVED_AT", sa.DateTime(timezone=True)),
    ):
        history_columns.extend(
            [
                sa.Column(f"FROM_{name}", kind, comment=f"FROM VALUE OF {name} FOR THIS CHANGE."),
                sa.Column(f"TO_{name}", kind, comment=f"TO VALUE OF {name} FOR THIS CHANGE."),
            ]
        )
    op.create_table(
        "FORM_SUBMISSION_ATTACHMENT_HISTORY",
        *history_columns,
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"],
            ["FORM_SUBMISSION_ATTACHMENT.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
    )
    for suffix, columns in (
        ("ENTITY_ID", ["ENTITY_ID"]),
        ("CHANGED_AT", ["CHANGED_AT"]),
        ("REQUEST_ID", ["REQUEST_ID"]),
        ("TRACE_ID", ["TRACE_ID"]),
        ("entity_changed", ["ENTITY_ID", "CHANGED_AT"]),
    ):
        op.create_index(
            f"ix_FORM_SUBMISSION_ATTACHMENT_HISTORY_{suffix}",
            "FORM_SUBMISSION_ATTACHMENT_HISTORY",
            columns,
        )

    schedule = sa.table(
        "PERIODIC_TASK",
        sa.column("VERSION", sa.Integer()),
        sa.column("CREATED_AT", sa.DateTime(timezone=True)),
        sa.column("NAME", sa.String(255)),
        sa.column("TASK_NAME", sa.String(255)),
        sa.column("QUEUE", sa.String(255)),
        sa.column("SCHEDULE_TYPE", sa.String(32)),
        sa.column("INTERVAL_SECONDS", sa.Float()),
        sa.column("ARGS", sa.JSON()),
        sa.column("KWARGS", sa.JSON()),
        sa.column("HEADERS", sa.JSON()),
        sa.column("ENABLED", sa.Boolean()),
        sa.column("ONE_OFF", sa.Boolean()),
        sa.column("TOTAL_RUN_COUNT", sa.Integer()),
    )
    op.bulk_insert(
        schedule,
        [
            {
                "VERSION": 1,
                "CREATED_AT": datetime.now(UTC),
                "NAME": "abandoned-upload-cleanup-hourly",
                "TASK_NAME": "media.cleanup_abandoned_uploads",
                "QUEUE": "default",
                "SCHEDULE_TYPE": "interval",
                "INTERVAL_SECONDS": 3600.0,
                "ARGS": [],
                "KWARGS": {},
                "HEADERS": {},
                "ENABLED": True,
                "ONE_OFF": False,
                "TOTAL_RUN_COUNT": 0,
            }
        ],
    )


def _downgrade_form_submission_attachments() -> None:
    op.execute(
        sa.text('DELETE FROM "PERIODIC_TASK" WHERE "NAME" = \'abandoned-upload-cleanup-hourly\'')
    )
    for suffix in ("entity_changed", "TRACE_ID", "REQUEST_ID", "CHANGED_AT", "ENTITY_ID"):
        op.drop_index(
            f"ix_FORM_SUBMISSION_ATTACHMENT_HISTORY_{suffix}",
            table_name="FORM_SUBMISSION_ATTACHMENT_HISTORY",
        )
    op.drop_table("FORM_SUBMISSION_ATTACHMENT_HISTORY")
    for name in (
        "ix_FORM_SUBMISSION_ATTACHMENT_group",
        "ix_FORM_SUBMISSION_ATTACHMENT_added_by",
        "ix_FORM_SUBMISSION_ATTACHMENT_upload",
        "ix_FORM_SUBMISSION_ATTACHMENT_collection",
        "uq_FORM_SUBMISSION_ATTACHMENT_active_position",
        "ix_FORM_SUBMISSION_ATTACHMENT_CREATED_AT",
    ):
        op.drop_index(name, table_name="FORM_SUBMISSION_ATTACHMENT")
    op.drop_table("FORM_SUBMISSION_ATTACHMENT")


# Claimable human work


def _upgrade_claimable_human_work() -> None:
    op.drop_constraint("uq_FORM_SUBMISSION_request", "FORM_SUBMISSION", type_="unique")
    op.create_index(
        "uq_FORM_SUBMISSION_request_initial",
        "FORM_SUBMISSION",
        ["BUSINESS_REQUEST_ID"],
        unique=True,
        postgresql_where=sa.text('"STEP_EXECUTION_ID" IS NULL'),
    )
    op.create_index(
        "uq_FORM_SUBMISSION_step_execution",
        "FORM_SUBMISSION",
        ["STEP_EXECUTION_ID"],
        unique=True,
        postgresql_where=sa.text('"STEP_EXECUTION_ID" IS NOT NULL'),
    )
    op.create_table(
        "WORK_ITEM",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("STEP_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("BUSINESS_REQUEST_ID", sa.Uuid(), nullable=False),
        sa.Column("STATUS", sa.String(16), nullable=False),
        sa.Column("PRIORITY", sa.Integer(), nullable=False),
        sa.Column("CLAIMED_BY_USER_ID", sa.Uuid()),
        sa.Column("CLAIMED_AT", sa.DateTime(timezone=True)),
        sa.Column("DUE_AT", sa.DateTime(timezone=True)),
        sa.Column("FORM_VERSION_ID", sa.Uuid()),
        sa.Column("OUTCOME_KEY", sa.String(64)),
        sa.Column("CLOSED_AT", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["STEP_EXECUTION_ID"], ["STEP_EXECUTION.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["BUSINESS_REQUEST_ID"],
            ["BUSINESS_REQUEST.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["CLAIMED_BY_USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["FORM_VERSION_ID"], ["FORM_VERSION.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.CheckConstraint(
            "\"STATUS\" IN ('OPEN','CLAIMED','IN_PROGRESS','COMPLETED','REJECTED','RETURNED','CANCELLED','EXPIRED')",
            name="ck_WORK_ITEM_status",
        ),
        sa.CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_WORK_ITEM_priority"),
        sa.CheckConstraint(
            '(("CLAIMED_BY_USER_ID" IS NULL) = ("CLAIMED_AT" IS NULL))',
            name="ck_WORK_ITEM_claim_pair",
        ),
        sa.CheckConstraint(
            "\"STATUS\" NOT IN ('CLAIMED','IN_PROGRESS') OR \"CLAIMED_BY_USER_ID\" IS NOT NULL",
            name="ck_WORK_ITEM_active_claimant",
        ),
        sa.CheckConstraint(
            "(\"STATUS\" IN ('OPEN','CLAIMED','IN_PROGRESS')) = (\"CLOSED_AT\" IS NULL)",
            name="ck_WORK_ITEM_closed",
        ),
        sa.CheckConstraint('"DELETED_AT" IS NULL', name="ck_WORK_ITEM_not_deleted"),
    )
    op.create_index("ix_WORK_ITEM_CREATED_AT", "WORK_ITEM", ["CREATED_AT"])
    op.create_index(
        "uq_WORK_ITEM_live_execution",
        "WORK_ITEM",
        ["STEP_EXECUTION_ID"],
        unique=True,
        postgresql_where=sa.text("\"STATUS\" IN ('OPEN','CLAIMED','IN_PROGRESS')"),
    )
    op.create_index(
        "ix_WORK_ITEM_cartable",
        "WORK_ITEM",
        [
            "STATUS",
            sa.text('"PRIORITY" DESC'),
            sa.text('"DUE_AT" ASC NULLS LAST'),
            "CREATED_AT",
            "ID",
        ],
    )
    op.create_index("ix_WORK_ITEM_claimant_status", "WORK_ITEM", ["CLAIMED_BY_USER_ID", "STATUS"])
    op.create_index("ix_WORK_ITEM_request", "WORK_ITEM", ["BUSINESS_REQUEST_ID"])
    op.create_index("ix_WORK_ITEM_form", "WORK_ITEM", ["FORM_VERSION_ID"])

    op.create_table(
        "WORK_ITEM_CANDIDATE",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("WORK_ITEM_ID", sa.Uuid(), nullable=False),
        sa.Column("USER_ID", sa.Uuid()),
        sa.Column("WORK_GROUP_ID", sa.Uuid()),
        sa.Column("SOURCE_TARGET_ID", sa.Uuid()),
        sa.Column("CAN_CLAIM", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("CREATED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["WORK_ITEM_ID"], ["WORK_ITEM.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["WORK_GROUP_ID"], ["WORK_GROUP.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["SOURCE_TARGET_ID"],
            ["WORKFLOW_STEP_TARGET.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.CheckConstraint(
            '(num_nonnulls("USER_ID", "WORK_GROUP_ID") = 1)',
            name="ck_WORK_ITEM_CANDIDATE_principal",
        ),
    )
    op.create_index(
        "uq_WORK_ITEM_CANDIDATE_user",
        "WORK_ITEM_CANDIDATE",
        ["WORK_ITEM_ID", "USER_ID"],
        unique=True,
        postgresql_where=sa.text('"USER_ID" IS NOT NULL'),
    )
    op.create_index(
        "uq_WORK_ITEM_CANDIDATE_group",
        "WORK_ITEM_CANDIDATE",
        ["WORK_ITEM_ID", "WORK_GROUP_ID"],
        unique=True,
        postgresql_where=sa.text('"WORK_GROUP_ID" IS NOT NULL'),
    )
    op.create_index(
        "ix_WORK_ITEM_CANDIDATE_user_item", "WORK_ITEM_CANDIDATE", ["USER_ID", "WORK_ITEM_ID"]
    )
    op.create_index(
        "ix_WORK_ITEM_CANDIDATE_group_item",
        "WORK_ITEM_CANDIDATE",
        ["WORK_GROUP_ID", "WORK_ITEM_ID"],
    )
    op.create_index("ix_WORK_ITEM_CANDIDATE_source", "WORK_ITEM_CANDIDATE", ["SOURCE_TARGET_ID"])

    op.create_table(
        "WORK_ITEM_ACTION",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("WORK_ITEM_ID", sa.Uuid(), nullable=False),
        sa.Column("ACTOR_USER_ID", sa.Uuid()),
        sa.Column("ACTION", sa.String(32), nullable=False),
        sa.Column("OUTCOME_KEY", sa.String(64)),
        sa.Column("FORM_SUBMISSION_ID", sa.Uuid()),
        sa.Column("COMMENT", sa.String(4000)),
        sa.Column(
            "DETAILS",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("COMMAND_KEY", sa.String(128), nullable=False),
        sa.Column("OCCURRED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("WORK_ITEM_ID", "COMMAND_KEY", name="uq_WORK_ITEM_ACTION_command"),
        sa.ForeignKeyConstraint(
            ["WORK_ITEM_ID"], ["WORK_ITEM.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ACTOR_USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["FORM_SUBMISSION_ID"], ["FORM_SUBMISSION.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
    )
    op.create_index(
        "ix_WORK_ITEM_ACTION_timeline", "WORK_ITEM_ACTION", ["WORK_ITEM_ID", "OCCURRED_AT", "ID"]
    )
    op.create_index("ix_WORK_ITEM_ACTION_actor", "WORK_ITEM_ACTION", ["ACTOR_USER_ID"])
    op.create_index("ix_WORK_ITEM_ACTION_submission", "WORK_ITEM_ACTION", ["FORM_SUBMISSION_ID"])

    op.create_table(
        "USER_WORK_ITEM_STATE",
        sa.Column("USER_ID", sa.Uuid(), nullable=False),
        sa.Column("WORK_ITEM_ID", sa.Uuid(), nullable=False),
        sa.Column("READ_AT", sa.DateTime(timezone=True)),
        sa.Column("PINNED_AT", sa.DateTime(timezone=True)),
        sa.Column("ARCHIVED_AT", sa.DateTime(timezone=True)),
        sa.Column("WATCHING_AT", sa.DateTime(timezone=True)),
        sa.Column("UPDATED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("USER_ID", "WORK_ITEM_ID"),
        sa.ForeignKeyConstraint(["USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["WORK_ITEM_ID"], ["WORK_ITEM.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
    )
    op.create_index(
        "ix_USER_WORK_ITEM_STATE_item_user", "USER_WORK_ITEM_STATE", ["WORK_ITEM_ID", "USER_ID"]
    )
    op.create_index(
        "ix_USER_WORK_ITEM_STATE_user_pinned", "USER_WORK_ITEM_STATE", ["USER_ID", "PINNED_AT"]
    )
    op.create_index(
        "ix_USER_WORK_ITEM_STATE_user_watching", "USER_WORK_ITEM_STATE", ["USER_ID", "WATCHING_AT"]
    )

    op.execute("""
        CREATE FUNCTION protect_work_item_action() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Work item actions are append-only' USING ERRCODE = '23514';
        END $$
    """)
    op.execute("""CREATE TRIGGER work_item_action_append_only
        BEFORE UPDATE OR DELETE ON "WORK_ITEM_ACTION"
        FOR EACH ROW EXECUTE FUNCTION protect_work_item_action()""")


def _downgrade_claimable_human_work() -> None:
    op.execute('DROP TRIGGER work_item_action_append_only ON "WORK_ITEM_ACTION"')
    op.execute("DROP FUNCTION protect_work_item_action()")
    op.drop_table("USER_WORK_ITEM_STATE")
    op.drop_table("WORK_ITEM_ACTION")
    op.drop_table("WORK_ITEM_CANDIDATE")
    op.drop_table("WORK_ITEM")
    op.execute("""
        DELETE FROM "FORM_SUBMISSION_ATTACHMENT_HISTORY" history
        USING "FORM_SUBMISSION_ATTACHMENT" attachment, "FORM_SUBMISSION" submission
        WHERE history."ENTITY_ID" = attachment."ID"
          AND attachment."FORM_SUBMISSION_ID" = submission."ID"
          AND submission."STEP_EXECUTION_ID" IS NOT NULL
    """)
    op.execute("""
        DELETE FROM "FORM_SUBMISSION_ATTACHMENT" attachment
        USING "FORM_SUBMISSION" submission
        WHERE attachment."FORM_SUBMISSION_ID" = submission."ID"
          AND submission."STEP_EXECUTION_ID" IS NOT NULL
    """)
    op.execute('ALTER TABLE "FORM_SUBMISSION" DISABLE TRIGGER form_submission_immutable')
    op.execute('DELETE FROM "FORM_SUBMISSION" WHERE "STEP_EXECUTION_ID" IS NOT NULL')
    op.execute('ALTER TABLE "FORM_SUBMISSION" ENABLE TRIGGER form_submission_immutable')
    op.drop_index("uq_FORM_SUBMISSION_step_execution", table_name="FORM_SUBMISSION")
    op.drop_index("uq_FORM_SUBMISSION_request_initial", table_name="FORM_SUBMISSION")
    op.create_unique_constraint(
        "uq_FORM_SUBMISSION_request", "FORM_SUBMISSION", ["BUSINESS_REQUEST_ID"]
    )


# Durable event and timer waits

_WAIT_CATALOG = [
    {
        "code": "EVENT_WAIT",
        "name": "Event wait",
        "handler_key": "event_wait",
        "handler_version": "1",
        "execution_mode": "WAIT",
        "config_schema": {
            "additionalProperties": False,
            "properties": {
                "event_type": {
                    "maxLength": 64,
                    "minLength": 1,
                    "pattern": "^[A-Za-z0-9][A-Za-z0-9._:-]*$",
                    "title": "Event Type",
                    "type": "string",
                },
                "expires_in_seconds": {
                    "anyOf": [
                        {"maximum": 31536000, "minimum": 1, "type": "integer"},
                        {"type": "null"},
                    ],
                    "default": None,
                    "title": "Expires In Seconds",
                },
            },
            "required": ["event_type"],
            "title": "EventWaitConfig",
            "type": "object",
        },
        "ports": [
            {
                "port_key": "correlation_key",
                "direction": "INPUT",
                "value_schema": {
                    "maxLength": 512,
                    "minLength": 1,
                    "type": "string",
                    "not": {"type": "null"},
                },
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "payload",
                "direction": "OUTPUT",
                "value_schema": {
                    "$defs": {"JsonValue": {}},
                    "additionalProperties": {"$ref": "#/$defs/JsonValue"},
                    "type": "object",
                    "not": {"type": "null"},
                },
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "outcome",
                "direction": "OUTPUT",
                "value_schema": {"type": "string", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
        ],
    },
    {
        "code": "TIMER",
        "name": "Timer",
        "handler_key": "timer",
        "handler_version": "1",
        "execution_mode": "WAIT",
        "config_schema": {
            "additionalProperties": False,
            "properties": {
                "delay_seconds": {
                    "maximum": 31536000,
                    "minimum": 1,
                    "title": "Delay Seconds",
                    "type": "integer",
                }
            },
            "required": ["delay_seconds"],
            "title": "TimerConfig",
            "type": "object",
        },
        "ports": [
            {
                "port_key": "outcome",
                "direction": "OUTPUT",
                "value_schema": {"type": "string", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            }
        ],
    },
]


def _base_columns_durable_event_and_timer_waits() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION",
            sa.Integer(),
            nullable=False,
            comment="OPTIMISTIC-LOCK VERSION NUMBER.",
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
    ]


def _upgrade_durable_event_and_timer_waits() -> None:
    op.create_table(
        "EVENT_SUBSCRIPTION",
        *_base_columns_durable_event_and_timer_waits(),
        sa.Column("STEP_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("EVENT_TYPE", sa.String(64), nullable=False),
        sa.Column("CORRELATION_HASH", sa.String(64), nullable=False),
        sa.Column("STATUS", sa.String(16), nullable=False),
        sa.Column("EXPIRES_AT", sa.DateTime(timezone=True)),
        sa.Column("CONSUMED_AT", sa.DateTime(timezone=True)),
        sa.Column("DELIVERY_KEY", sa.String(128)),
        sa.Column("DELIVERY_SOURCE", sa.String(32)),
        sa.Column("ATTEMPTS", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["STEP_EXECUTION_ID"], ["STEP_EXECUTION.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.UniqueConstraint(
            "EVENT_TYPE",
            "CORRELATION_HASH",
            "STEP_EXECUTION_ID",
            name="uq_EVENT_SUBSCRIPTION_identity",
        ),
        sa.CheckConstraint(
            "\"STATUS\" IN ('ACTIVE','CONSUMED','EXPIRED','CANCELLED')",
            name="ck_EVENT_SUBSCRIPTION_status",
        ),
        sa.CheckConstraint('"ATTEMPTS" >= 0', name="ck_EVENT_SUBSCRIPTION_attempts"),
        sa.CheckConstraint('"DELETED_AT" IS NULL', name="ck_EVENT_SUBSCRIPTION_not_deleted"),
    )
    op.create_index("ix_EVENT_SUBSCRIPTION_CREATED_AT", "EVENT_SUBSCRIPTION", ["CREATED_AT"])
    op.create_index("ix_EVENT_SUBSCRIPTION_step", "EVENT_SUBSCRIPTION", ["STEP_EXECUTION_ID"])
    op.create_index(
        "ix_EVENT_SUBSCRIPTION_active",
        "EVENT_SUBSCRIPTION",
        ["EVENT_TYPE", "CORRELATION_HASH"],
        postgresql_where=sa.text("\"STATUS\" = 'ACTIVE'"),
    )
    op.create_index(
        "uq_EVENT_SUBSCRIPTION_delivery",
        "EVENT_SUBSCRIPTION",
        ["DELIVERY_KEY"],
        unique=True,
        postgresql_where=sa.text('"DELIVERY_KEY" IS NOT NULL'),
    )

    op.create_table(
        "SCHEDULED_ACTION",
        *_base_columns_durable_event_and_timer_waits(),
        sa.Column("STEP_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("KIND", sa.String(16), nullable=False),
        sa.Column("STATUS", sa.String(16), nullable=False),
        sa.Column("DUE_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ATTEMPTS", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("MAX_ATTEMPTS", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("LEASE_OWNER", sa.Uuid()),
        sa.Column("LEASE_UNTIL", sa.DateTime(timezone=True)),
        sa.Column("FIRED_AT", sa.DateTime(timezone=True)),
        sa.Column("ACTION_KEY", sa.String(160), nullable=False),
        sa.Column("OUTCOME_KEY", sa.String(64), nullable=False),
        sa.Column("LAST_ERROR_CODE", sa.String(128)),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["STEP_EXECUTION_ID"], ["STEP_EXECUTION.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.UniqueConstraint("ACTION_KEY", name="uq_SCHEDULED_ACTION_key"),
        sa.CheckConstraint(
            "\"KIND\" IN ('DELAY','DEADLINE','RETRY','ESCALATION')",
            name="ck_SCHEDULED_ACTION_kind",
        ),
        sa.CheckConstraint(
            "\"STATUS\" IN ('PENDING','LEASED','FIRED','CANCELLED','FAILED')",
            name="ck_SCHEDULED_ACTION_status",
        ),
        sa.CheckConstraint('"ATTEMPTS" >= 0', name="ck_SCHEDULED_ACTION_attempts"),
        sa.CheckConstraint('"MAX_ATTEMPTS" > 0', name="ck_SCHEDULED_ACTION_max_attempts"),
        sa.CheckConstraint(
            '("STATUS" = \'LEASED\') = ("LEASE_OWNER" IS NOT NULL AND "LEASE_UNTIL" IS NOT NULL)',
            name="ck_SCHEDULED_ACTION_lease",
        ),
        sa.CheckConstraint('"DELETED_AT" IS NULL', name="ck_SCHEDULED_ACTION_not_deleted"),
    )
    op.create_index("ix_SCHEDULED_ACTION_CREATED_AT", "SCHEDULED_ACTION", ["CREATED_AT"])
    op.create_index("ix_SCHEDULED_ACTION_step", "SCHEDULED_ACTION", ["STEP_EXECUTION_ID"])
    op.create_index(
        "ix_SCHEDULED_ACTION_due",
        "SCHEDULED_ACTION",
        ["DUE_AT", "ID"],
        postgresql_where=sa.text("\"STATUS\" = 'PENDING'"),
    )
    op.create_index(
        "ix_SCHEDULED_ACTION_lease",
        "SCHEDULED_ACTION",
        ["LEASE_UNTIL", "ID"],
        postgresql_where=sa.text("\"STATUS\" = 'LEASED'"),
    )

    payload = json.dumps(_WAIT_CATALOG)
    op.execute(
        sa.text("""
        WITH seeds AS (
            SELECT value AS data FROM jsonb_array_elements(CAST(:payload AS jsonb))
        ), roots AS (
            INSERT INTO "STEP_TYPE" ("CODE", "NAME", "IS_ENABLED", "VERSION", "CREATED_AT")
            SELECT data->>'code', data->>'name', true, 1, now() FROM seeds
            RETURNING "ID", "CODE", "NAME"
        ), history AS (
            INSERT INTO "STEP_TYPE_HISTORY"
                ("ENTITY_ID", "MODIFIER_TYPE", "MODIFIER_ID", "CHANGED_AT", "OPERATION",
                 "TO_CODE", "TO_NAME", "TO_IS_ENABLED")
            SELECT "ID", 'system', 'migration:a13d5e7f9012', now(), 'insert',
                   "CODE", "NAME", true FROM roots
        ), versions AS (
            INSERT INTO "STEP_TYPE_VERSION"
                ("STEP_TYPE_ID", "NUMBER", "STATUS", "HANDLER_KEY", "HANDLER_VERSION",
                 "EXECUTION_MODE", "CONFIG_SCHEMA", "PUBLISHED_AT", "VERSION", "CREATED_AT")
            SELECT roots."ID", 1, 'DRAFT', data->>'handler_key', data->>'handler_version',
                   data->>'execution_mode', data->'config_schema', NULL, 1, now()
            FROM roots JOIN seeds ON roots."CODE" = data->>'code'
            RETURNING "ID", "HANDLER_KEY"
        )
        INSERT INTO "STEP_TYPE_PORT"
            ("STEP_TYPE_VERSION_ID", "DIRECTION", "PORT_KEY", "VALUE_SCHEMA",
             "REQUIRED", "NULLABLE", "CARDINALITY", "CREATED_AT")
        SELECT versions."ID", port->>'direction', port->>'port_key', port->'value_schema',
               (port->>'required')::boolean, (port->>'nullable')::boolean,
               port->>'cardinality', now()
        FROM versions JOIN seeds ON versions."HANDLER_KEY" = data->>'handler_key'
        CROSS JOIN LATERAL jsonb_array_elements(data->'ports') AS port
        """).bindparams(sa.bindparam("payload", value=payload, type_=sa.Text()))
    )
    op.execute(
        sa.text("""
        UPDATE "STEP_TYPE_VERSION" SET "STATUS" = 'PUBLISHED', "PUBLISHED_AT" = now(),
            "UPDATED_AT" = now()
        WHERE "HANDLER_KEY" IN ('event_wait', 'timer') AND "STATUS" = 'DRAFT'
        """)
    )


def _downgrade_durable_event_and_timer_waits() -> None:
    op.execute('ALTER TABLE "STEP_TYPE_PORT" DISABLE TRIGGER step_type_port_immutable')
    op.execute('ALTER TABLE "STEP_TYPE_VERSION" DISABLE TRIGGER step_type_version_immutable')
    op.execute(
        sa.text("""
        DELETE FROM "STEP_TYPE_PORT" WHERE "STEP_TYPE_VERSION_ID" IN (
            SELECT "ID" FROM "STEP_TYPE_VERSION" WHERE "STEP_TYPE_ID" IN (
                SELECT "ID" FROM "STEP_TYPE" WHERE "CODE" IN ('EVENT_WAIT', 'TIMER')
            )
        )
        """)
    )
    op.execute(
        sa.text("""
        DELETE FROM "STEP_TYPE_VERSION" WHERE "STEP_TYPE_ID" IN (
            SELECT "ID" FROM "STEP_TYPE" WHERE "CODE" IN ('EVENT_WAIT', 'TIMER')
        )
        """)
    )
    op.execute(
        sa.text("""
        DELETE FROM "STEP_TYPE_HISTORY" WHERE "ENTITY_ID" IN (
            SELECT "ID" FROM "STEP_TYPE" WHERE "CODE" IN ('EVENT_WAIT', 'TIMER')
        )
        """)
    )
    op.execute(sa.text("DELETE FROM \"STEP_TYPE\" WHERE \"CODE\" IN ('EVENT_WAIT', 'TIMER')"))
    op.execute('ALTER TABLE "STEP_TYPE_VERSION" ENABLE TRIGGER step_type_version_immutable')
    op.execute('ALTER TABLE "STEP_TYPE_PORT" ENABLE TRIGGER step_type_port_immutable')
    op.drop_table("SCHEDULED_ACTION")
    op.drop_table("EVENT_SUBSCRIPTION")


# Append only process events


def _upgrade_append_only_process_events() -> None:
    op.create_table(
        "PROCESS_EVENT",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("PROCESS_INSTANCE_ID", sa.Uuid(), nullable=False),
        sa.Column("BUSINESS_REQUEST_ID", sa.Uuid(), nullable=False),
        sa.Column("SEQUENCE", sa.Integer(), nullable=False),
        sa.Column("EVENT_TYPE", sa.String(64), nullable=False),
        sa.Column("STEP_EXECUTION_ID", sa.Uuid()),
        sa.Column("WORK_ITEM_ID", sa.Uuid()),
        sa.Column("ACTOR_USER_ID", sa.Uuid()),
        sa.Column(
            "PUBLIC_PAYLOAD",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("TRACE_ID", sa.String(64)),
        sa.Column("REQUEST_ID", sa.String(64)),
        sa.Column("COMMAND_KEY", sa.String(128)),
        sa.Column("COMMAND_PAYLOAD_HASH", sa.String(64)),
        sa.Column("OCCURRED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["PROCESS_INSTANCE_ID"],
            ["PROCESS_INSTANCE.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["BUSINESS_REQUEST_ID"],
            ["BUSINESS_REQUEST.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["STEP_EXECUTION_ID"],
            ["STEP_EXECUTION.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["WORK_ITEM_ID"], ["WORK_ITEM.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ACTOR_USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.UniqueConstraint("PROCESS_INSTANCE_ID", "SEQUENCE", name="uq_PROCESS_EVENT_sequence"),
        sa.CheckConstraint('"SEQUENCE" > 0', name="ck_PROCESS_EVENT_sequence"),
        sa.CheckConstraint(
            '("COMMAND_KEY" IS NULL) = ("COMMAND_PAYLOAD_HASH" IS NULL)',
            name="ck_PROCESS_EVENT_command_pair",
        ),
    )
    op.create_index(
        "uq_PROCESS_EVENT_step_command",
        "PROCESS_EVENT",
        ["STEP_EXECUTION_ID", "COMMAND_KEY"],
        unique=True,
        postgresql_where=sa.text('"COMMAND_KEY" IS NOT NULL'),
    )
    op.create_index(
        "ix_PROCESS_EVENT_request_time",
        "PROCESS_EVENT",
        ["BUSINESS_REQUEST_ID", "OCCURRED_AT", "ID"],
    )
    op.create_index("ix_PROCESS_EVENT_step", "PROCESS_EVENT", ["STEP_EXECUTION_ID"])
    op.create_index("ix_PROCESS_EVENT_work_item", "PROCESS_EVENT", ["WORK_ITEM_ID"])
    op.create_index("ix_PROCESS_EVENT_actor", "PROCESS_EVENT", ["ACTOR_USER_ID"])
    op.execute(
        """
        CREATE FUNCTION prevent_process_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'PROCESS_EVENT is append-only' USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER process_event_append_only
        BEFORE UPDATE OR DELETE ON "PROCESS_EVENT"
        FOR EACH ROW EXECUTE FUNCTION prevent_process_event_mutation()
        """
    )


def _downgrade_append_only_process_events() -> None:
    op.drop_table("PROCESS_EVENT")
    op.execute("DROP FUNCTION prevent_process_event_mutation()")


# Advanced execution


def _upgrade_advanced_execution() -> None:
    op.drop_constraint("ck_PROCESS_INSTANCE_status", "PROCESS_INSTANCE", type_="check")
    op.drop_constraint("ck_PROCESS_INSTANCE_terminal", "PROCESS_INSTANCE", type_="check")
    op.alter_column(
        "PROCESS_INSTANCE",
        "STATUS",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_PROCESS_INSTANCE_status",
        "PROCESS_INSTANCE",
        "\"STATUS\" IN ('RUNNING','WAITING','PAUSED','COMPLETED','FAILED','CANCELLED','COMPENSATING','COMPENSATION_FAILED','COMPENSATED')",
    )
    op.create_check_constraint(
        "ck_PROCESS_INSTANCE_terminal",
        "PROCESS_INSTANCE",
        "(\"STATUS\" IN ('COMPLETED','FAILED','CANCELLED','COMPENSATION_FAILED','COMPENSATED')) = (\"ENDED_AT\" IS NOT NULL)",
    )
    op.add_column(
        "WORKFLOW_STEP",
        sa.Column(
            "FLOW",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.drop_index("uq_EXECUTION_TOKEN_live_process", table_name="EXECUTION_TOKEN")
    op.drop_constraint("ck_EXECUTION_TOKEN_phase1_single_path", "EXECUTION_TOKEN", type_="check")
    op.create_index(
        "uq_EXECUTION_TOKEN_root_live_process",
        "EXECUTION_TOKEN",
        ["PROCESS_INSTANCE_ID"],
        unique=True,
        postgresql_where=sa.text(
            "\"STATUS\" IN ('ACTIVE','WAITING') AND \"PARENT_TOKEN_ID\" IS NULL"
        ),
    )
    op.create_index(
        "uq_EXECUTION_TOKEN_branch_key",
        "EXECUTION_TOKEN",
        ["PARENT_TOKEN_ID", "BRANCH_KEY"],
        unique=True,
        postgresql_where=sa.text('"PARENT_TOKEN_ID" IS NOT NULL'),
    )
    op.create_table(
        "COMPENSATION_RECORD",
        sa.Column("ID", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("PROCESS_INSTANCE_ID", sa.Uuid(), nullable=False),
        sa.Column("SOURCE_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("COMPENSATION_STEP_ID", sa.Uuid(), nullable=False),
        sa.Column("ORDINAL", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(16), nullable=False),
        sa.Column("DISPATCH_KEY", sa.String(160)),
        sa.Column("LAST_ERROR_CODE", sa.String(128)),
        sa.Column("COMPLETED_AT", sa.DateTime(timezone=True)),
        sa.Column("CREATED_AT", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["PROCESS_INSTANCE_ID"],
            ["PROCESS_INSTANCE.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["SOURCE_EXECUTION_ID"], ["STEP_EXECUTION.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["COMPENSATION_STEP_ID"], ["WORKFLOW_STEP.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.CheckConstraint('"ORDINAL" > 0', name="ck_COMPENSATION_RECORD_ordinal"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('PENDING','RUNNING','EXECUTING','COMPLETED','FAILED')",
            name="ck_COMPENSATION_RECORD_status",
        ),
        sa.UniqueConstraint("SOURCE_EXECUTION_ID", name="uq_COMPENSATION_RECORD_source"),
        sa.UniqueConstraint(
            "PROCESS_INSTANCE_ID", "DISPATCH_KEY", name="uq_COMPENSATION_RECORD_dispatch"
        ),
    )
    op.create_index(
        "ix_COMPENSATION_RECORD_process_order",
        "COMPENSATION_RECORD",
        ["PROCESS_INSTANCE_ID", "ORDINAL"],
    )


def _downgrade_advanced_execution() -> None:
    op.drop_index("ix_COMPENSATION_RECORD_process_order", table_name="COMPENSATION_RECORD")
    op.drop_table("COMPENSATION_RECORD")
    op.drop_index("uq_EXECUTION_TOKEN_branch_key", table_name="EXECUTION_TOKEN")
    op.drop_index("uq_EXECUTION_TOKEN_root_live_process", table_name="EXECUTION_TOKEN")
    op.create_check_constraint(
        "ck_EXECUTION_TOKEN_phase1_single_path",
        "EXECUTION_TOKEN",
        '"BRANCH_KEY" IS NULL AND "PARENT_TOKEN_ID" IS NULL',
    )
    op.create_index(
        "uq_EXECUTION_TOKEN_live_process",
        "EXECUTION_TOKEN",
        ["PROCESS_INSTANCE_ID"],
        unique=True,
        postgresql_where=sa.text("\"STATUS\" IN ('ACTIVE','WAITING')"),
    )
    op.drop_column("WORKFLOW_STEP", "FLOW")
    op.drop_constraint("ck_PROCESS_INSTANCE_terminal", "PROCESS_INSTANCE", type_="check")
    op.drop_constraint("ck_PROCESS_INSTANCE_status", "PROCESS_INSTANCE", type_="check")
    op.alter_column(
        "PROCESS_INSTANCE",
        "STATUS",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_PROCESS_INSTANCE_status",
        "PROCESS_INSTANCE",
        "\"STATUS\" IN ('RUNNING','WAITING','PAUSED','COMPLETED','FAILED','CANCELLED')",
    )
    op.create_check_constraint(
        "ck_PROCESS_INSTANCE_terminal",
        "PROCESS_INSTANCE",
        "((\"STATUS\" IN ('COMPLETED','FAILED','CANCELLED')) = (\"ENDED_AT\" IS NOT NULL))",
    )


# Durable notifications


def _base_columns_durable_notifications() -> list[sa.Column[Any]]:
    return [
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION",
            sa.Integer(),
            nullable=False,
            comment="OPTIMISTIC-LOCK VERSION NUMBER.",
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
    ]


def _upgrade_durable_notifications() -> None:
    op.get_bind().exec_driver_sql(
        """
        WITH source AS (
            SELECT v."STEP_TYPE_ID"
            FROM "STEP_TYPE_VERSION" v
            JOIN "STEP_TYPE" t ON t."ID" = v."STEP_TYPE_ID"
            WHERE t."CODE" = 'NOTIFICATION' AND v."NUMBER" = 1
        ), inserted AS (
            INSERT INTO "STEP_TYPE_VERSION" (
                "ID", "VERSION", "CREATED_AT", "STEP_TYPE_ID", "NUMBER", "STATUS",
                "HANDLER_KEY", "HANDLER_VERSION", "EXECUTION_MODE", "CONFIG_SCHEMA", "PUBLISHED_AT"
            )
            SELECT uuidv7(), 1, now(), "STEP_TYPE_ID", 2, 'DRAFT',
                   'notification', '2', 'BACKGROUND',
                   '{
                     "$defs":{"Reference":{"maxLength":512,"minLength":1,"type":"string"}},
                     "additionalProperties":false,
                     "properties":{
                       "channel":{"const":"EMAIL","default":"EMAIL","title":"Channel","type":"string"},
                       "connection_ref":{"$ref":"#/$defs/Reference"},
                       "locale":{"default":"en","enum":["en","fa"],"title":"Locale","type":"string"},
                       "template_key":{"$ref":"#/$defs/Reference"},
                       "template_version":{"default":"1","maxLength":32,"minLength":1,"title":"Template Version","type":"string"}
                     },
                     "required":["connection_ref","template_key"],
                     "title":"NotificationConfigV2","type":"object"
                   }'::jsonb,
                   NULL
            FROM source
            RETURNING "ID"
        )
        INSERT INTO "STEP_TYPE_PORT" (
            "ID", "STEP_TYPE_VERSION_ID", "DIRECTION", "PORT_KEY", "VALUE_SCHEMA",
            "REQUIRED", "NULLABLE", "CARDINALITY", "CREATED_AT"
        )
        SELECT uuidv7(), inserted."ID", p."DIRECTION", p."PORT_KEY", p."VALUE_SCHEMA",
               p."REQUIRED", p."NULLABLE", p."CARDINALITY", now()
        FROM inserted
        JOIN "STEP_TYPE_VERSION" old ON old."HANDLER_KEY" = 'notification'
                                    AND old."HANDLER_VERSION" = '1'
        JOIN "STEP_TYPE_PORT" p ON p."STEP_TYPE_VERSION_ID" = old."ID"
        """
    )
    op.execute(
        """
        UPDATE "STEP_TYPE_VERSION"
        SET "STATUS" = 'PUBLISHED', "PUBLISHED_AT" = now()
        WHERE "HANDLER_KEY" = 'notification' AND "HANDLER_VERSION" = '2'
        """
    )
    op.create_table(
        "NOTIFICATION",
        *_base_columns_durable_notifications(),
        sa.Column("RECIPIENT_USER_ID", sa.Uuid(), nullable=False),
        sa.Column("BUSINESS_REQUEST_ID", sa.Uuid(), nullable=False),
        sa.Column("PROCESS_INSTANCE_ID", sa.Uuid(), nullable=False),
        sa.Column("STEP_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("TEMPLATE_KEY", sa.String(128), nullable=False),
        sa.Column("TEMPLATE_VERSION", sa.String(32), nullable=False),
        sa.Column("LOCALE", sa.String(16), nullable=False),
        sa.Column("SUBJECT", sa.String(512), nullable=False),
        sa.Column("CONTENT", sa.Text()),
        sa.Column("CONTENT_REF", sa.String(512)),
        sa.Column("PRIORITY", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(16), nullable=False),
        sa.Column("READ_AT", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["RECIPIENT_USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["BUSINESS_REQUEST_ID"],
            ["BUSINESS_REQUEST.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["PROCESS_INSTANCE_ID"],
            ["PROCESS_INSTANCE.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["STEP_EXECUTION_ID"],
            ["STEP_EXECUTION.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.UniqueConstraint(
            "STEP_EXECUTION_ID", "RECIPIENT_USER_ID", name="uq_NOTIFICATION_execution_recipient"
        ),
        sa.CheckConstraint('"PRIORITY" BETWEEN 0 AND 9', name="ck_NOTIFICATION_priority"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('ACTIVE','CANCELLED','EXPIRED')", name="ck_NOTIFICATION_status"
        ),
        sa.CheckConstraint(
            '("CONTENT" IS NOT NULL)::int + ("CONTENT_REF" IS NOT NULL)::int = 1',
            name="ck_NOTIFICATION_content",
        ),
    )
    op.create_index("ix_NOTIFICATION_CREATED_AT", "NOTIFICATION", ["CREATED_AT"])
    op.create_index(
        "ix_NOTIFICATION_recipient_created",
        "NOTIFICATION",
        ["RECIPIENT_USER_ID", "CREATED_AT", "ID"],
    )
    op.create_index("ix_NOTIFICATION_process", "NOTIFICATION", ["PROCESS_INSTANCE_ID"])
    op.create_table(
        "NOTIFICATION_DELIVERY",
        *_base_columns_durable_notifications(),
        sa.Column("NOTIFICATION_ID", sa.Uuid(), nullable=False),
        sa.Column("CHANNEL", sa.String(16), nullable=False),
        sa.Column("DESTINATION_FINGERPRINT", sa.String(64), nullable=False),
        sa.Column("INTEGRATION_CONNECTION_ID", sa.Uuid(), nullable=False),
        sa.Column("PROVIDER_MESSAGE_REF", sa.String(255)),
        sa.Column("STATUS", sa.String(16), nullable=False),
        sa.Column("ATTEMPT_COUNT", sa.Integer(), nullable=False),
        sa.Column("NEXT_ATTEMPT_AT", sa.DateTime(timezone=True)),
        sa.Column("LAST_ERROR_CODE", sa.String(128)),
        sa.Column("DELIVERED_AT", sa.DateTime(timezone=True)),
        sa.Column("TERMINAL_AT", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("ID"),
        sa.ForeignKeyConstraint(
            ["NOTIFICATION_ID"],
            ["NOTIFICATION.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["INTEGRATION_CONNECTION_ID"],
            ["INTEGRATION_CONNECTION.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.UniqueConstraint("NOTIFICATION_ID", "CHANNEL", name="uq_NOTIFICATION_DELIVERY_channel"),
        sa.CheckConstraint("\"CHANNEL\" IN ('EMAIL')", name="ck_NOTIFICATION_DELIVERY_channel"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('PENDING','RUNNING','RETRY','DELIVERED','BOUNCED','FAILED','CANCELLED')",
            name="ck_NOTIFICATION_DELIVERY_status",
        ),
        sa.CheckConstraint('"ATTEMPT_COUNT" >= 0', name="ck_NOTIFICATION_DELIVERY_attempts"),
    )
    op.create_index("ix_NOTIFICATION_DELIVERY_CREATED_AT", "NOTIFICATION_DELIVERY", ["CREATED_AT"])
    op.create_index(
        "ix_NOTIFICATION_DELIVERY_due",
        "NOTIFICATION_DELIVERY",
        ["STATUS", "NEXT_ATTEMPT_AT", "ID"],
    )
    op.create_index(
        "ix_NOTIFICATION_DELIVERY_connection",
        "NOTIFICATION_DELIVERY",
        ["INTEGRATION_CONNECTION_ID"],
    )


def _downgrade_durable_notifications() -> None:
    op.drop_table("NOTIFICATION_DELIVERY")
    op.drop_table("NOTIFICATION")
    op.execute('DROP TRIGGER step_type_port_immutable ON "STEP_TYPE_PORT"')
    op.execute('DROP TRIGGER step_type_version_immutable ON "STEP_TYPE_VERSION"')
    op.execute(
        """
        DELETE FROM "STEP_TYPE_PORT"
        WHERE "STEP_TYPE_VERSION_ID" IN (
            SELECT "ID" FROM "STEP_TYPE_VERSION"
            WHERE "HANDLER_KEY" = 'notification' AND "HANDLER_VERSION" = '2'
        )
        """
    )
    op.execute(
        'DELETE FROM "STEP_TYPE_VERSION" WHERE "HANDLER_KEY" = \'notification\' AND "HANDLER_VERSION" = \'2\''
    )
    op.execute(
        """CREATE TRIGGER step_type_version_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON "STEP_TYPE_VERSION"
        FOR EACH ROW EXECUTE FUNCTION protect_step_type_version()"""
    )
    op.execute(
        """CREATE TRIGGER step_type_port_immutable
        BEFORE INSERT OR UPDATE OR DELETE ON "STEP_TYPE_PORT"
        FOR EACH ROW EXECUTE FUNCTION protect_step_type_port()"""
    )


# Registered client releases


def _upgrade_registered_client_releases() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "CLIENT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("KIND", sa.String(length=16), nullable=False),
        sa.Column("PLATFORM", sa.String(length=64), nullable=False),
        sa.Column("SECRET_HASH", sa.String(length=64), nullable=True),
        sa.Column("IS_ACTIVE", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "\"KIND\" IN ('ANDROID','IOS','DESKTOP','WEB','B2B','SDK')", name="ck_CLIENT_kind"
        ),
        sa.CheckConstraint('length("CODE") > 0 AND length("NAME") > 0', name="ck_CLIENT_names"),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(op.f("ix_CLIENT_CREATED_AT"), "CLIENT", ["CREATED_AT"], unique=False)
    op.create_index(
        "uq_CLIENT_code_active",
        "CLIENT",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "CLIENT_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_KIND",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF KIND FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_KIND",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF KIND FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PLATFORM",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF PLATFORM FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PLATFORM",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF PLATFORM FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SECRET_HASH",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF SECRET_HASH FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SECRET_HASH",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF SECRET_HASH FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["CLIENT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_CLIENT_HISTORY_CHANGED_AT"), "CLIENT_HISTORY", ["CHANGED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_CLIENT_HISTORY_ENTITY_ID"), "CLIENT_HISTORY", ["ENTITY_ID"], unique=False
    )
    op.create_index(
        op.f("ix_CLIENT_HISTORY_REQUEST_ID"), "CLIENT_HISTORY", ["REQUEST_ID"], unique=False
    )
    op.create_index(
        op.f("ix_CLIENT_HISTORY_TRACE_ID"), "CLIENT_HISTORY", ["TRACE_ID"], unique=False
    )
    op.create_index(
        "ix_CLIENT_HISTORY_entity_changed",
        "CLIENT_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "CLIENT_RELEASE",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CLIENT_ID", sa.Uuid(), nullable=False),
        sa.Column("RELEASE_VERSION", sa.String(length=64), nullable=False),
        sa.Column("API_VERSION", sa.String(length=32), nullable=False),
        sa.Column(
            "RENDERER_CAPABILITIES",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("IS_ENABLED", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            'length("RELEASE_VERSION") > 0', name="ck_CLIENT_RELEASE_release_version"
        ),
        sa.ForeignKeyConstraint(
            ["CLIENT_ID"], ["CLIENT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_CLIENT_RELEASE_CREATED_AT"), "CLIENT_RELEASE", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_CLIENT_RELEASE_client_enabled",
        "CLIENT_RELEASE",
        ["CLIENT_ID", "IS_ENABLED"],
        unique=False,
    )
    op.create_index(
        "uq_CLIENT_RELEASE_client_version",
        "CLIENT_RELEASE",
        ["CLIENT_ID", "RELEASE_VERSION"],
        unique=True,
    )
    op.create_table(
        "CLIENT_RELEASE_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CLIENT_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF CLIENT_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CLIENT_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF CLIENT_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_RELEASE_VERSION",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF RELEASE_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_RELEASE_VERSION",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF RELEASE_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_API_VERSION",
            sa.String(length=32),
            nullable=True,
            comment="FROM VALUE OF API_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_API_VERSION",
            sa.String(length=32),
            nullable=True,
            comment="TO VALUE OF API_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_RENDERER_CAPABILITIES",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF RENDERER_CAPABILITIES FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_RENDERER_CAPABILITIES",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF RENDERER_CAPABILITIES FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_ENABLED",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_ENABLED FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_ENABLED",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_ENABLED FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["CLIENT_RELEASE.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_CLIENT_RELEASE_HISTORY_CHANGED_AT"),
        "CLIENT_RELEASE_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_CLIENT_RELEASE_HISTORY_ENTITY_ID"),
        "CLIENT_RELEASE_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_CLIENT_RELEASE_HISTORY_REQUEST_ID"),
        "CLIENT_RELEASE_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_CLIENT_RELEASE_HISTORY_TRACE_ID"),
        "CLIENT_RELEASE_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_CLIENT_RELEASE_HISTORY_entity_changed",
        "CLIENT_RELEASE_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.add_column("AUTH_SESSION", sa.Column("CLIENT_ID", sa.Uuid(), nullable=True))
    op.add_column("AUTH_SESSION", sa.Column("CLIENT_RELEASE_ID", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_AUTH_SESSION_CLIENT_ID"), "AUTH_SESSION", ["CLIENT_ID"], unique=False)
    op.create_index(
        op.f("ix_AUTH_SESSION_CLIENT_RELEASE_ID"),
        "AUTH_SESSION",
        ["CLIENT_RELEASE_ID"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_AUTH_SESSION_CLIENT_ID",
        "AUTH_SESSION",
        "CLIENT",
        ["CLIENT_ID"],
        ["ID"],
        onupdate="RESTRICT",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_AUTH_SESSION_CLIENT_RELEASE_ID",
        "AUTH_SESSION",
        "CLIENT_RELEASE",
        ["CLIENT_RELEASE_ID"],
        ["ID"],
        onupdate="RESTRICT",
        ondelete="RESTRICT",
    )


def _downgrade_registered_client_releases() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("fk_AUTH_SESSION_CLIENT_RELEASE_ID", "AUTH_SESSION", type_="foreignkey")
    op.drop_constraint("fk_AUTH_SESSION_CLIENT_ID", "AUTH_SESSION", type_="foreignkey")
    op.drop_index(op.f("ix_AUTH_SESSION_CLIENT_RELEASE_ID"), table_name="AUTH_SESSION")
    op.drop_index(op.f("ix_AUTH_SESSION_CLIENT_ID"), table_name="AUTH_SESSION")
    op.drop_column("AUTH_SESSION", "CLIENT_RELEASE_ID")
    op.drop_column("AUTH_SESSION", "CLIENT_ID")
    op.drop_index("ix_CLIENT_RELEASE_HISTORY_entity_changed", table_name="CLIENT_RELEASE_HISTORY")
    op.drop_index(op.f("ix_CLIENT_RELEASE_HISTORY_TRACE_ID"), table_name="CLIENT_RELEASE_HISTORY")
    op.drop_index(op.f("ix_CLIENT_RELEASE_HISTORY_REQUEST_ID"), table_name="CLIENT_RELEASE_HISTORY")
    op.drop_index(op.f("ix_CLIENT_RELEASE_HISTORY_ENTITY_ID"), table_name="CLIENT_RELEASE_HISTORY")
    op.drop_index(op.f("ix_CLIENT_RELEASE_HISTORY_CHANGED_AT"), table_name="CLIENT_RELEASE_HISTORY")
    op.drop_table("CLIENT_RELEASE_HISTORY")
    op.drop_index("uq_CLIENT_RELEASE_client_version", table_name="CLIENT_RELEASE")
    op.drop_index("ix_CLIENT_RELEASE_client_enabled", table_name="CLIENT_RELEASE")
    op.drop_index(op.f("ix_CLIENT_RELEASE_CREATED_AT"), table_name="CLIENT_RELEASE")
    op.drop_table("CLIENT_RELEASE")
    op.drop_index("ix_CLIENT_HISTORY_entity_changed", table_name="CLIENT_HISTORY")
    op.drop_index(op.f("ix_CLIENT_HISTORY_TRACE_ID"), table_name="CLIENT_HISTORY")
    op.drop_index(op.f("ix_CLIENT_HISTORY_REQUEST_ID"), table_name="CLIENT_HISTORY")
    op.drop_index(op.f("ix_CLIENT_HISTORY_ENTITY_ID"), table_name="CLIENT_HISTORY")
    op.drop_index(op.f("ix_CLIENT_HISTORY_CHANGED_AT"), table_name="CLIENT_HISTORY")
    op.drop_table("CLIENT_HISTORY")
    op.drop_index(
        "uq_CLIENT_code_active",
        table_name="CLIENT",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index(op.f("ix_CLIENT_CREATED_AT"), table_name="CLIENT")
    op.drop_table("CLIENT")


# Request client restrictions


def _upgrade_request_client_restrictions() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "REQUEST_TYPE_CLIENT_TARGET",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("REQUEST_TYPE_ID", sa.Uuid(), nullable=False),
        sa.Column("CLIENT_ID", sa.Uuid(), nullable=False),
        sa.Column("MINIMUM_RELEASE", sa.String(length=64), nullable=True),
        sa.Column("MAXIMUM_RELEASE_EXCLUSIVE", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["CLIENT_ID"], ["CLIENT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["REQUEST_TYPE_ID"], ["REQUEST_TYPE.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_CREATED_AT"),
        "REQUEST_TYPE_CLIENT_TARGET",
        ["CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "ix_REQUEST_TYPE_CLIENT_TARGET_client",
        "REQUEST_TYPE_CLIENT_TARGET",
        ["CLIENT_ID"],
        unique=False,
    )
    op.create_index(
        "uq_REQUEST_TYPE_CLIENT_TARGET_active",
        "REQUEST_TYPE_CLIENT_TARGET",
        ["REQUEST_TYPE_ID", "CLIENT_ID"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "REQUEST_TYPE_CLIENT_TARGET_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_REQUEST_TYPE_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF REQUEST_TYPE_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_REQUEST_TYPE_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF REQUEST_TYPE_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CLIENT_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF CLIENT_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CLIENT_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF CLIENT_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_MINIMUM_RELEASE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF MINIMUM_RELEASE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_MINIMUM_RELEASE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF MINIMUM_RELEASE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_MAXIMUM_RELEASE_EXCLUSIVE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF MAXIMUM_RELEASE_EXCLUSIVE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_MAXIMUM_RELEASE_EXCLUSIVE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF MAXIMUM_RELEASE_EXCLUSIVE FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"],
            ["REQUEST_TYPE_CLIENT_TARGET.ID"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_CHANGED_AT"),
        "REQUEST_TYPE_CLIENT_TARGET_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_ENTITY_ID"),
        "REQUEST_TYPE_CLIENT_TARGET_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_REQUEST_ID"),
        "REQUEST_TYPE_CLIENT_TARGET_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_TRACE_ID"),
        "REQUEST_TYPE_CLIENT_TARGET_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_entity_changed",
        "REQUEST_TYPE_CLIENT_TARGET_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.add_column(
        "BUSINESS_REQUEST",
        sa.Column("ORIGIN_CLIENT_CONTEXT", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def _downgrade_request_client_restrictions() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("BUSINESS_REQUEST", "ORIGIN_CLIENT_CONTEXT")
    op.drop_index(
        "ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_entity_changed",
        table_name="REQUEST_TYPE_CLIENT_TARGET_HISTORY",
    )
    op.drop_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_TRACE_ID"),
        table_name="REQUEST_TYPE_CLIENT_TARGET_HISTORY",
    )
    op.drop_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_REQUEST_ID"),
        table_name="REQUEST_TYPE_CLIENT_TARGET_HISTORY",
    )
    op.drop_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_ENTITY_ID"),
        table_name="REQUEST_TYPE_CLIENT_TARGET_HISTORY",
    )
    op.drop_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_HISTORY_CHANGED_AT"),
        table_name="REQUEST_TYPE_CLIENT_TARGET_HISTORY",
    )
    op.drop_table("REQUEST_TYPE_CLIENT_TARGET_HISTORY")
    op.drop_index(
        "uq_REQUEST_TYPE_CLIENT_TARGET_active",
        table_name="REQUEST_TYPE_CLIENT_TARGET",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index("ix_REQUEST_TYPE_CLIENT_TARGET_client", table_name="REQUEST_TYPE_CLIENT_TARGET")
    op.drop_index(
        op.f("ix_REQUEST_TYPE_CLIENT_TARGET_CREATED_AT"), table_name="REQUEST_TYPE_CLIENT_TARGET"
    )
    op.drop_table("REQUEST_TYPE_CLIENT_TARGET")


# Versioned form design variants


def _upgrade_versioned_form_design_variants() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "FORM_VERSION",
        sa.Column(
            "PAGE_SETTINGS",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "FORM_VERSION",
        sa.Column(
            "VARIANTS",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "FORM_VERSION_HISTORY",
        sa.Column(
            "FROM_PAGE_SETTINGS",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF PAGE_SETTINGS FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "FORM_VERSION_HISTORY",
        sa.Column(
            "TO_PAGE_SETTINGS",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF PAGE_SETTINGS FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "FORM_VERSION_HISTORY",
        sa.Column(
            "FROM_VARIANTS",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF VARIANTS FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "FORM_VERSION_HISTORY",
        sa.Column(
            "TO_VARIANTS",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF VARIANTS FOR THIS CHANGE.",
        ),
    )


def _downgrade_versioned_form_design_variants() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("FORM_VERSION_HISTORY", "TO_VARIANTS")
    op.drop_column("FORM_VERSION_HISTORY", "FROM_VARIANTS")
    op.drop_column("FORM_VERSION_HISTORY", "TO_PAGE_SETTINGS")
    op.drop_column("FORM_VERSION_HISTORY", "FROM_PAGE_SETTINGS")
    op.drop_column("FORM_VERSION", "VARIANTS")
    op.drop_column("FORM_VERSION", "PAGE_SETTINGS")


# Pin request presentation design


def _upgrade_pin_request_presentation_design() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "FORM_SUBMISSION",
        sa.Column("DESIGN_SNAPSHOT", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION protect_form_submission() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD."STATUS" <> 'DRAFT' THEN
                RAISE EXCEPTION 'Submitted form data is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD."STATUS" <> 'DRAFT' AND (
                NEW."BUSINESS_REQUEST_ID" IS DISTINCT FROM OLD."BUSINESS_REQUEST_ID" OR
                NEW."FORM_VERSION_ID" IS DISTINCT FROM OLD."FORM_VERSION_ID" OR
                NEW."SUBMITTED_BY_USER_ID" IS DISTINCT FROM OLD."SUBMITTED_BY_USER_ID" OR
                NEW."STATUS" IS DISTINCT FROM OLD."STATUS" OR
                NEW."DATA" IS DISTINCT FROM OLD."DATA" OR
                NEW."SUBMITTED_AT" IS DISTINCT FROM OLD."SUBMITTED_AT" OR
                NEW."DESIGN_SNAPSHOT" IS DISTINCT FROM OLD."DESIGN_SNAPSHOT"
            ) THEN
                RAISE EXCEPTION 'Submitted form data and design pin are immutable' USING ERRCODE = '23514';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$;
    """)


def _downgrade_pin_request_presentation_design() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("""
        CREATE OR REPLACE FUNCTION protect_form_submission() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD."STATUS" <> 'DRAFT' THEN
                RAISE EXCEPTION 'Submitted form data is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD."STATUS" <> 'DRAFT' AND (
                NEW."BUSINESS_REQUEST_ID" IS DISTINCT FROM OLD."BUSINESS_REQUEST_ID" OR
                NEW."FORM_VERSION_ID" IS DISTINCT FROM OLD."FORM_VERSION_ID" OR
                NEW."SUBMITTED_BY_USER_ID" IS DISTINCT FROM OLD."SUBMITTED_BY_USER_ID" OR
                NEW."STATUS" IS DISTINCT FROM OLD."STATUS" OR
                NEW."DATA" IS DISTINCT FROM OLD."DATA" OR
                NEW."SUBMITTED_AT" IS DISTINCT FROM OLD."SUBMITTED_AT"
            ) THEN
                RAISE EXCEPTION 'Submitted form data and version pin are immutable' USING ERRCODE = '23514';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$;
    """)
    op.drop_column("FORM_SUBMISSION", "DESIGN_SNAPSHOT")


# Explicit request cross client


def _upgrade_explicit_request_cross_client_resume() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "REQUEST_TYPE",
        sa.Column(
            "ALLOW_CROSS_CLIENT_RESUME",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "REQUEST_TYPE_HISTORY",
        sa.Column(
            "FROM_ALLOW_CROSS_CLIENT_RESUME",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF ALLOW_CROSS_CLIENT_RESUME FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "REQUEST_TYPE_HISTORY",
        sa.Column(
            "TO_ALLOW_CROSS_CLIENT_RESUME",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF ALLOW_CROSS_CLIENT_RESUME FOR THIS CHANGE.",
        ),
    )


def _downgrade_explicit_request_cross_client_resume() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("REQUEST_TYPE_HISTORY", "TO_ALLOW_CROSS_CLIENT_RESUME")
    op.drop_column("REQUEST_TYPE_HISTORY", "FROM_ALLOW_CROSS_CLIENT_RESUME")
    op.drop_column("REQUEST_TYPE", "ALLOW_CROSS_CLIENT_RESUME")


# Audit form presentation interactions


def _upgrade_audit_form_presentation_interactions() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "FORM_SUBMISSION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_BUSINESS_REQUEST_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF BUSINESS_REQUEST_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_BUSINESS_REQUEST_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF BUSINESS_REQUEST_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_FORM_VERSION_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF FORM_VERSION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_FORM_VERSION_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF FORM_VERSION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_STEP_EXECUTION_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF STEP_EXECUTION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STEP_EXECUTION_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF STEP_EXECUTION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SUBMITTED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF SUBMITTED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SUBMITTED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF SUBMITTED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DATA",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF DATA FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DATA",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF DATA FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DESIGN_SNAPSHOT",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF DESIGN_SNAPSHOT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DESIGN_SNAPSHOT",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF DESIGN_SNAPSHOT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SUBMITTED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF SUBMITTED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SUBMITTED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF SUBMITTED_AT FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["FORM_SUBMISSION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_SUBMISSION_HISTORY_CHANGED_AT"),
        "FORM_SUBMISSION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_SUBMISSION_HISTORY_ENTITY_ID"),
        "FORM_SUBMISSION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_SUBMISSION_HISTORY_REQUEST_ID"),
        "FORM_SUBMISSION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_SUBMISSION_HISTORY_TRACE_ID"),
        "FORM_SUBMISSION_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_SUBMISSION_HISTORY_entity_changed",
        "FORM_SUBMISSION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )


def _downgrade_audit_form_presentation_interactions() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_FORM_SUBMISSION_HISTORY_entity_changed", table_name="FORM_SUBMISSION_HISTORY")
    op.drop_index(op.f("ix_FORM_SUBMISSION_HISTORY_TRACE_ID"), table_name="FORM_SUBMISSION_HISTORY")
    op.drop_index(
        op.f("ix_FORM_SUBMISSION_HISTORY_REQUEST_ID"), table_name="FORM_SUBMISSION_HISTORY"
    )
    op.drop_index(
        op.f("ix_FORM_SUBMISSION_HISTORY_ENTITY_ID"), table_name="FORM_SUBMISSION_HISTORY"
    )
    op.drop_index(
        op.f("ix_FORM_SUBMISSION_HISTORY_CHANGED_AT"), table_name="FORM_SUBMISSION_HISTORY"
    )
    op.drop_table("FORM_SUBMISSION_HISTORY")


# Durable ai task budget reservations


def _upgrade_durable_ai_task_budget_reservations() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "AI_TASK_BUDGET",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("STEP_EXECUTION_ID", sa.Uuid(), nullable=False),
        sa.Column("EFFECTIVE_LIMITS", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "USED",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "RESERVED",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("CURRENCY", sa.String(length=3), nullable=False),
        sa.Column("PRICE_VERSION", sa.String(length=128), nullable=False),
        sa.CheckConstraint("\"CURRENCY\" = 'USD'", name="ck_AI_TASK_BUDGET_currency"),
        sa.ForeignKeyConstraint(
            ["STEP_EXECUTION_ID"], ["STEP_EXECUTION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_AI_TASK_BUDGET_CREATED_AT"), "AI_TASK_BUDGET", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "uq_AI_TASK_BUDGET_execution", "AI_TASK_BUDGET", ["STEP_EXECUTION_ID"], unique=True
    )
    op.create_table(
        "AI_RESERVATION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("TASK_BUDGET_ID", sa.Uuid(), nullable=False),
        sa.Column("RESERVATION_KEY", sa.String(length=128), nullable=False),
        sa.Column("STATUS", sa.String(length=24), nullable=False),
        sa.Column("UPPER_BOUND", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ACTUAL_USAGE", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "\"STATUS\" IN ('RESERVED', 'SETTLED', 'UNKNOWN', 'NOT_DISPATCHED')",
            name="ck_AI_RESERVATION_status",
        ),
        sa.ForeignKeyConstraint(
            ["TASK_BUDGET_ID"], ["AI_TASK_BUDGET.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_AI_RESERVATION_CREATED_AT"), "AI_RESERVATION", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "uq_AI_RESERVATION_task_key",
        "AI_RESERVATION",
        ["TASK_BUDGET_ID", "RESERVATION_KEY"],
        unique=True,
    )
    op.create_table(
        "AI_TASK_BUDGET_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_STEP_EXECUTION_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF STEP_EXECUTION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STEP_EXECUTION_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF STEP_EXECUTION_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_EFFECTIVE_LIMITS",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF EFFECTIVE_LIMITS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_EFFECTIVE_LIMITS",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF EFFECTIVE_LIMITS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_USED",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF USED FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_USED",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF USED FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_RESERVED",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF RESERVED FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_RESERVED",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF RESERVED FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CURRENCY",
            sa.String(length=3),
            nullable=True,
            comment="FROM VALUE OF CURRENCY FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CURRENCY",
            sa.String(length=3),
            nullable=True,
            comment="TO VALUE OF CURRENCY FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PRICE_VERSION",
            sa.String(length=128),
            nullable=True,
            comment="FROM VALUE OF PRICE_VERSION FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PRICE_VERSION",
            sa.String(length=128),
            nullable=True,
            comment="TO VALUE OF PRICE_VERSION FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["AI_TASK_BUDGET.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_AI_TASK_BUDGET_HISTORY_CHANGED_AT"),
        "AI_TASK_BUDGET_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_AI_TASK_BUDGET_HISTORY_ENTITY_ID"),
        "AI_TASK_BUDGET_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_AI_TASK_BUDGET_HISTORY_REQUEST_ID"),
        "AI_TASK_BUDGET_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_AI_TASK_BUDGET_HISTORY_TRACE_ID"),
        "AI_TASK_BUDGET_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_AI_TASK_BUDGET_HISTORY_entity_changed",
        "AI_TASK_BUDGET_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "AI_RESERVATION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_TASK_BUDGET_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF TASK_BUDGET_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_TASK_BUDGET_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF TASK_BUDGET_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_RESERVATION_KEY",
            sa.String(length=128),
            nullable=True,
            comment="FROM VALUE OF RESERVATION_KEY FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_RESERVATION_KEY",
            sa.String(length=128),
            nullable=True,
            comment="TO VALUE OF RESERVATION_KEY FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=24),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=24),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_UPPER_BOUND",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF UPPER_BOUND FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_UPPER_BOUND",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF UPPER_BOUND FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_ACTUAL_USAGE",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF ACTUAL_USAGE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ACTUAL_USAGE",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF ACTUAL_USAGE FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["AI_RESERVATION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_AI_RESERVATION_HISTORY_CHANGED_AT"),
        "AI_RESERVATION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_AI_RESERVATION_HISTORY_ENTITY_ID"),
        "AI_RESERVATION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_AI_RESERVATION_HISTORY_REQUEST_ID"),
        "AI_RESERVATION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_AI_RESERVATION_HISTORY_TRACE_ID"),
        "AI_RESERVATION_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_AI_RESERVATION_HISTORY_entity_changed",
        "AI_RESERVATION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )


def _downgrade_durable_ai_task_budget_reservations() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_AI_RESERVATION_HISTORY_entity_changed", table_name="AI_RESERVATION_HISTORY")
    op.drop_index(op.f("ix_AI_RESERVATION_HISTORY_TRACE_ID"), table_name="AI_RESERVATION_HISTORY")
    op.drop_index(op.f("ix_AI_RESERVATION_HISTORY_REQUEST_ID"), table_name="AI_RESERVATION_HISTORY")
    op.drop_index(op.f("ix_AI_RESERVATION_HISTORY_ENTITY_ID"), table_name="AI_RESERVATION_HISTORY")
    op.drop_index(op.f("ix_AI_RESERVATION_HISTORY_CHANGED_AT"), table_name="AI_RESERVATION_HISTORY")
    op.drop_table("AI_RESERVATION_HISTORY")
    op.drop_index("ix_AI_TASK_BUDGET_HISTORY_entity_changed", table_name="AI_TASK_BUDGET_HISTORY")
    op.drop_index(op.f("ix_AI_TASK_BUDGET_HISTORY_TRACE_ID"), table_name="AI_TASK_BUDGET_HISTORY")
    op.drop_index(op.f("ix_AI_TASK_BUDGET_HISTORY_REQUEST_ID"), table_name="AI_TASK_BUDGET_HISTORY")
    op.drop_index(op.f("ix_AI_TASK_BUDGET_HISTORY_ENTITY_ID"), table_name="AI_TASK_BUDGET_HISTORY")
    op.drop_index(op.f("ix_AI_TASK_BUDGET_HISTORY_CHANGED_AT"), table_name="AI_TASK_BUDGET_HISTORY")
    op.drop_table("AI_TASK_BUDGET_HISTORY")
    op.drop_index("uq_AI_RESERVATION_task_key", table_name="AI_RESERVATION")
    op.drop_index(op.f("ix_AI_RESERVATION_CREATED_AT"), table_name="AI_RESERVATION")
    op.drop_table("AI_RESERVATION")
    op.drop_index("uq_AI_TASK_BUDGET_execution", table_name="AI_TASK_BUDGET")
    op.drop_index(op.f("ix_AI_TASK_BUDGET_CREATED_AT"), table_name="AI_TASK_BUDGET")
    op.drop_table("AI_TASK_BUDGET")


# Versioned ai agents


def _upgrade_versioned_ai_agents() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "AI_AGENT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NUMBER", sa.Integer(), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("OWNER_USER_ID", sa.Uuid(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("SPEC", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("CHECKSUM", sa.String(length=64), nullable=True),
        sa.Column("PUBLISHED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('"NUMBER" > 0', name="ck_AI_AGENT_number"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')", name="ck_AI_AGENT_status"
        ),
        sa.ForeignKeyConstraint(
            ["OWNER_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(op.f("ix_AI_AGENT_CREATED_AT"), "AI_AGENT", ["CREATED_AT"], unique=False)
    op.create_index("ix_AI_AGENT_owner", "AI_AGENT", ["OWNER_USER_ID"], unique=False)
    op.create_index("uq_AI_AGENT_code_number", "AI_AGENT", ["CODE", "NUMBER"], unique=True)
    op.create_table(
        "AI_AGENT_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NUMBER",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF NUMBER FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NUMBER", sa.Integer(), nullable=True, comment="TO VALUE OF NUMBER FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_SPEC",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF SPEC FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_SPEC",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF SPEC FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["AI_AGENT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_AI_AGENT_HISTORY_CHANGED_AT"), "AI_AGENT_HISTORY", ["CHANGED_AT"], unique=False
    )
    op.create_index(
        op.f("ix_AI_AGENT_HISTORY_ENTITY_ID"), "AI_AGENT_HISTORY", ["ENTITY_ID"], unique=False
    )
    op.create_index(
        op.f("ix_AI_AGENT_HISTORY_REQUEST_ID"), "AI_AGENT_HISTORY", ["REQUEST_ID"], unique=False
    )
    op.create_index(
        op.f("ix_AI_AGENT_HISTORY_TRACE_ID"), "AI_AGENT_HISTORY", ["TRACE_ID"], unique=False
    )
    op.create_index(
        "ix_AI_AGENT_HISTORY_entity_changed",
        "AI_AGENT_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.execute(
        """CREATE FUNCTION ai_agent_published_immutable() RETURNS trigger AS $$
        BEGIN
            IF OLD."STATUS" IN ('PUBLISHED', 'RETIRED') AND (
                NEW."CODE", NEW."NUMBER", NEW."NAME", NEW."OWNER_USER_ID",
                NEW."SPEC", NEW."CHECKSUM", NEW."PUBLISHED_AT"
            ) IS DISTINCT FROM (
                OLD."CODE", OLD."NUMBER", OLD."NAME", OLD."OWNER_USER_ID",
                OLD."SPEC", OLD."CHECKSUM", OLD."PUBLISHED_AT"
            ) THEN
                RAISE EXCEPTION 'Published AI agent definition is immutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        'CREATE TRIGGER ai_agent_published_immutable BEFORE UPDATE ON "AI_AGENT" '
        "FOR EACH ROW EXECUTE FUNCTION ai_agent_published_immutable()"
    )


def _downgrade_versioned_ai_agents() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute('DROP TRIGGER ai_agent_published_immutable ON "AI_AGENT"')
    op.execute("DROP FUNCTION ai_agent_published_immutable()")
    op.drop_index("ix_AI_AGENT_HISTORY_entity_changed", table_name="AI_AGENT_HISTORY")
    op.drop_index(op.f("ix_AI_AGENT_HISTORY_TRACE_ID"), table_name="AI_AGENT_HISTORY")
    op.drop_index(op.f("ix_AI_AGENT_HISTORY_REQUEST_ID"), table_name="AI_AGENT_HISTORY")
    op.drop_index(op.f("ix_AI_AGENT_HISTORY_ENTITY_ID"), table_name="AI_AGENT_HISTORY")
    op.drop_index(op.f("ix_AI_AGENT_HISTORY_CHANGED_AT"), table_name="AI_AGENT_HISTORY")
    op.drop_table("AI_AGENT_HISTORY")
    op.drop_index("uq_AI_AGENT_code_number", table_name="AI_AGENT")
    op.drop_index("ix_AI_AGENT_owner", table_name="AI_AGENT")
    op.drop_index(op.f("ix_AI_AGENT_CREATED_AT"), table_name="AI_AGENT")
    op.drop_table("AI_AGENT")


# Record actual ai reservation model


def _upgrade_record_actual_ai_reservation_model() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("AI_RESERVATION", sa.Column("MODEL_USED", sa.String(length=255), nullable=True))
    op.add_column(
        "AI_RESERVATION_HISTORY",
        sa.Column(
            "FROM_MODEL_USED",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF MODEL_USED FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "AI_RESERVATION_HISTORY",
        sa.Column(
            "TO_MODEL_USED",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF MODEL_USED FOR THIS CHANGE.",
        ),
    )


def _downgrade_record_actual_ai_reservation_model() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("AI_RESERVATION_HISTORY", "TO_MODEL_USED")
    op.drop_column("AI_RESERVATION_HISTORY", "FROM_MODEL_USED")
    op.drop_column("AI_RESERVATION", "MODEL_USED")


# Ai tool approval checkpoint


def _upgrade_ai_tool_approval_checkpoint() -> None:
    op.create_table(
        "AI_TOOL_APPROVAL",
        sa.Column("STEP_EXECUTION_ATTEMPT_ID", sa.Uuid(), nullable=False),
        sa.Column("WORK_ITEM_ID", sa.Uuid(), nullable=False),
        sa.Column("TOOL_KEY", sa.String(length=64), nullable=False),
        sa.Column("TOOL_VERSION", sa.String(length=128), nullable=False),
        sa.Column("TOOL_CALL_ID", sa.String(length=128), nullable=False),
        sa.Column("PAYLOAD_CIPHERTEXT", sa.LargeBinary(), nullable=True),
        sa.Column("PAYLOAD_HASH", sa.String(length=64), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("EXPIRES_AT", sa.DateTime(timezone=True), nullable=False),
        sa.Column("DECIDED_BY_USER_ID", sa.Uuid(), nullable=True),
        sa.Column("DECIDED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("CONSUMED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.CheckConstraint(
            "(\"STATUS\" IN ('PENDING','APPROVED')) = (\"PAYLOAD_CIPHERTEXT\" IS NOT NULL)",
            name="ck_AI_TOOL_APPROVAL_payload_lifecycle",
        ),
        sa.CheckConstraint(
            "\"STATUS\" IN ('PENDING', 'APPROVED', 'DENIED', 'EXPIRED', 'CANCELLED', 'CONSUMED')",
            name="ck_AI_TOOL_APPROVAL_status",
        ),
        sa.ForeignKeyConstraint(
            ["DECIDED_BY_USER_ID"], ["USER.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["STEP_EXECUTION_ATTEMPT_ID"],
            ["STEP_EXECUTION_ATTEMPT.ID"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["WORK_ITEM_ID"], ["WORK_ITEM.ID"], ondelete="RESTRICT", onupdate="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index("ix_AI_TOOL_APPROVAL_due", "AI_TOOL_APPROVAL", ["STATUS", "EXPIRES_AT"])
    op.create_index(
        "uq_AI_TOOL_APPROVAL_attempt_call",
        "AI_TOOL_APPROVAL",
        ["STEP_EXECUTION_ATTEMPT_ID", "TOOL_CALL_ID"],
        unique=True,
    )
    op.create_index(
        "uq_AI_TOOL_APPROVAL_work_item", "AI_TOOL_APPROVAL", ["WORK_ITEM_ID"], unique=True
    )
    op.create_index("ix_AI_TOOL_APPROVAL_CREATED_AT", "AI_TOOL_APPROVAL", ["CREATED_AT"])


def _downgrade_ai_tool_approval_checkpoint() -> None:
    op.drop_index("ix_AI_TOOL_APPROVAL_CREATED_AT", table_name="AI_TOOL_APPROVAL")
    op.drop_index("uq_AI_TOOL_APPROVAL_work_item", table_name="AI_TOOL_APPROVAL")
    op.drop_index("uq_AI_TOOL_APPROVAL_attempt_call", table_name="AI_TOOL_APPROVAL")
    op.drop_index("ix_AI_TOOL_APPROVAL_due", table_name="AI_TOOL_APPROVAL")
    op.drop_table("AI_TOOL_APPROVAL")


# Versioned form localization


def _upgrade_versioned_form_localization() -> None:
    op.add_column(
        "FORM_VERSION",
        sa.Column("LOCALIZATION", postgresql.JSONB(none_as_null=True), nullable=True),
    )
    for prefix in ("FROM", "TO"):
        op.add_column(
            "FORM_VERSION_HISTORY",
            sa.Column(
                prefix + "_LOCALIZATION",
                postgresql.JSONB(none_as_null=True),
                nullable=True,
                comment=f"{prefix} VALUE OF LOCALIZATION FOR THIS CHANGE.",
            ),
        )


def _downgrade_versioned_form_localization() -> None:
    op.drop_column("FORM_VERSION_HISTORY", "TO_LOCALIZATION")
    op.drop_column("FORM_VERSION_HISTORY", "FROM_LOCALIZATION")
    op.drop_column("FORM_VERSION", "LOCALIZATION")


# Authored form library versions


def _upgrade_authored_form_library_versions() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "FORM_COMPONENT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("OWNER_USER_ID", sa.Uuid(), nullable=False),
        sa.Column("IS_ACTIVE", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["OWNER_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_CREATED_AT"), "FORM_COMPONENT", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_FORM_COMPONENT_owner_created",
        "FORM_COMPONENT",
        ["OWNER_USER_ID", "CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "uq_FORM_COMPONENT_CODE_active",
        "FORM_COMPONENT",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "FORM_DATA_TYPE",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("CODE", sa.String(length=64), nullable=False),
        sa.Column("NAME", sa.String(length=255), nullable=False),
        sa.Column("OWNER_USER_ID", sa.Uuid(), nullable=False),
        sa.Column("IS_ACTIVE", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["OWNER_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_CREATED_AT"), "FORM_DATA_TYPE", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_FORM_DATA_TYPE_owner_created",
        "FORM_DATA_TYPE",
        ["OWNER_USER_ID", "CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "uq_FORM_DATA_TYPE_CODE_active",
        "FORM_DATA_TYPE",
        ["CODE"],
        unique=True,
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.create_table(
        "FORM_COMPONENT_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["FORM_COMPONENT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_HISTORY_CHANGED_AT"),
        "FORM_COMPONENT_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_HISTORY_ENTITY_ID"),
        "FORM_COMPONENT_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_HISTORY_REQUEST_ID"),
        "FORM_COMPONENT_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_HISTORY_TRACE_ID"),
        "FORM_COMPONENT_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_COMPONENT_HISTORY_entity_changed",
        "FORM_COMPONENT_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "FORM_COMPONENT_VERSION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("ROOT_ID", sa.Uuid(), nullable=False),
        sa.Column("NUMBER", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("DOCUMENT", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "RESOLVED", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "DEPENDENCIES",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("CHECKSUM", sa.String(length=64), nullable=True),
        sa.Column("PUBLISHED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("PUBLISHED_BY_USER_ID", sa.Uuid(), nullable=True),
        sa.CheckConstraint('"NUMBER" > 0', name="ck_FORM_COMPONENT_VERSION_number"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_FORM_COMPONENT_VERSION_status",
        ),
        sa.ForeignKeyConstraint(
            ["PUBLISHED_BY_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ROOT_ID"], ["FORM_COMPONENT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("ROOT_ID", "NUMBER", name="uq_FORM_COMPONENT_VERSION_number"),
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_VERSION_CREATED_AT"),
        "FORM_COMPONENT_VERSION",
        ["CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_COMPONENT_VERSION_root_status",
        "FORM_COMPONENT_VERSION",
        ["ROOT_ID", "STATUS", "NUMBER"],
        unique=False,
    )
    op.create_table(
        "FORM_DATA_TYPE_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_CODE",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CODE",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CODE FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_NAME",
            sa.String(length=255),
            nullable=True,
            comment="FROM VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NAME",
            sa.String(length=255),
            nullable=True,
            comment="TO VALUE OF NAME FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_OWNER_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF OWNER_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_IS_ACTIVE",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF IS_ACTIVE FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["FORM_DATA_TYPE.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_HISTORY_CHANGED_AT"),
        "FORM_DATA_TYPE_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_HISTORY_ENTITY_ID"),
        "FORM_DATA_TYPE_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_HISTORY_REQUEST_ID"),
        "FORM_DATA_TYPE_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_HISTORY_TRACE_ID"),
        "FORM_DATA_TYPE_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_DATA_TYPE_HISTORY_entity_changed",
        "FORM_DATA_TYPE_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "FORM_DATA_TYPE_VERSION",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("ROOT_ID", sa.Uuid(), nullable=False),
        sa.Column("NUMBER", sa.Integer(), nullable=False),
        sa.Column("STATUS", sa.String(length=16), nullable=False),
        sa.Column("DOCUMENT", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "RESOLVED", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "DEPENDENCIES",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("CHECKSUM", sa.String(length=64), nullable=True),
        sa.Column("PUBLISHED_AT", sa.DateTime(timezone=True), nullable=True),
        sa.Column("PUBLISHED_BY_USER_ID", sa.Uuid(), nullable=True),
        sa.CheckConstraint('"NUMBER" > 0', name="ck_FORM_DATA_TYPE_VERSION_number"),
        sa.CheckConstraint(
            "\"STATUS\" IN ('DRAFT', 'PUBLISHED', 'RETIRED')",
            name="ck_FORM_DATA_TYPE_VERSION_status",
        ),
        sa.ForeignKeyConstraint(
            ["PUBLISHED_BY_USER_ID"], ["USER.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ROOT_ID"], ["FORM_DATA_TYPE.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
        sa.UniqueConstraint("ROOT_ID", "NUMBER", name="uq_FORM_DATA_TYPE_VERSION_number"),
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_CREATED_AT"),
        "FORM_DATA_TYPE_VERSION",
        ["CREATED_AT"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_DATA_TYPE_VERSION_root_status",
        "FORM_DATA_TYPE_VERSION",
        ["ROOT_ID", "STATUS", "NUMBER"],
        unique=False,
    )
    op.create_table(
        "FORM_LIBRARY_GRANT",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="TIME-SORTABLE UUIDV7 PRIMARY KEY.",
        ),
        sa.Column(
            "VERSION", sa.Integer(), nullable=False, comment="OPTIMISTIC-LOCK VERSION NUMBER."
        ),
        sa.Column(
            "CREATED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE ROW WAS CREATED.",
        ),
        sa.Column(
            "UPDATED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC TIMESTAMP OF THE MOST RECENT UPDATE.",
        ),
        sa.Column(
            "DELETED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC SOFT-DELETION TIMESTAMP; NULL MEANS THE ROW IS ACTIVE.",
        ),
        sa.Column("COMPONENT_ID", sa.Uuid(), nullable=True),
        sa.Column("DATA_TYPE_ID", sa.Uuid(), nullable=True),
        sa.Column("USER_ID", sa.Uuid(), nullable=True),
        sa.Column("WORK_GROUP_ID", sa.Uuid(), nullable=True),
        sa.Column("CAN_USE", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            '(CASE WHEN "COMPONENT_ID" IS NULL THEN 0 ELSE 1 END) + (CASE WHEN "DATA_TYPE_ID" IS NULL THEN 0 ELSE 1 END) = 1',
            name="ck_FORM_LIBRARY_GRANT_resource",
        ),
        sa.CheckConstraint(
            '(CASE WHEN "USER_ID" IS NULL THEN 0 ELSE 1 END) + (CASE WHEN "WORK_GROUP_ID" IS NULL THEN 0 ELSE 1 END) = 1',
            name="ck_FORM_LIBRARY_GRANT_target",
        ),
        sa.ForeignKeyConstraint(["COMPONENT_ID"], ["FORM_COMPONENT.ID"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["DATA_TYPE_ID"], ["FORM_DATA_TYPE.ID"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["USER_ID"], ["USER.ID"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["WORK_GROUP_ID"], ["WORK_GROUP.ID"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_LIBRARY_GRANT_CREATED_AT"), "FORM_LIBRARY_GRANT", ["CREATED_AT"], unique=False
    )
    op.create_index(
        "ix_FORM_LIBRARY_GRANT_component", "FORM_LIBRARY_GRANT", ["COMPONENT_ID"], unique=False
    )
    op.create_index(
        "ix_FORM_LIBRARY_GRANT_data_type", "FORM_LIBRARY_GRANT", ["DATA_TYPE_ID"], unique=False
    )
    op.create_index(
        "ix_FORM_LIBRARY_GRANT_group", "FORM_LIBRARY_GRANT", ["WORK_GROUP_ID"], unique=False
    )
    op.create_index("ix_FORM_LIBRARY_GRANT_user", "FORM_LIBRARY_GRANT", ["USER_ID"], unique=False)
    op.create_table(
        "FORM_COMPONENT_VERSION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_ROOT_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF ROOT_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ROOT_ID", sa.Uuid(), nullable=True, comment="TO VALUE OF ROOT_ID FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_NUMBER",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF NUMBER FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NUMBER", sa.Integer(), nullable=True, comment="TO VALUE OF NUMBER FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DOCUMENT",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF DOCUMENT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DOCUMENT",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF DOCUMENT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_RESOLVED",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF RESOLVED FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_RESOLVED",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF RESOLVED FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DEPENDENCIES",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF DEPENDENCIES FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DEPENDENCIES",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF DEPENDENCIES FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["FORM_COMPONENT_VERSION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_VERSION_HISTORY_CHANGED_AT"),
        "FORM_COMPONENT_VERSION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_VERSION_HISTORY_ENTITY_ID"),
        "FORM_COMPONENT_VERSION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_VERSION_HISTORY_REQUEST_ID"),
        "FORM_COMPONENT_VERSION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_COMPONENT_VERSION_HISTORY_TRACE_ID"),
        "FORM_COMPONENT_VERSION_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_COMPONENT_VERSION_HISTORY_entity_changed",
        "FORM_COMPONENT_VERSION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "FORM_DATA_TYPE_VERSION_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_ROOT_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF ROOT_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_ROOT_ID", sa.Uuid(), nullable=True, comment="TO VALUE OF ROOT_ID FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_NUMBER",
            sa.Integer(),
            nullable=True,
            comment="FROM VALUE OF NUMBER FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_NUMBER", sa.Integer(), nullable=True, comment="TO VALUE OF NUMBER FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="FROM VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_STATUS",
            sa.String(length=16),
            nullable=True,
            comment="TO VALUE OF STATUS FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DOCUMENT",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF DOCUMENT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DOCUMENT",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF DOCUMENT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_RESOLVED",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF RESOLVED FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_RESOLVED",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF RESOLVED FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DEPENDENCIES",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF DEPENDENCIES FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DEPENDENCIES",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF DEPENDENCIES FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CHECKSUM",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF CHECKSUM FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_AT",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_AT FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_PUBLISHED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF PUBLISHED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_PUBLISHED_BY_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF PUBLISHED_BY_USER_ID FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["FORM_DATA_TYPE_VERSION.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_HISTORY_CHANGED_AT"),
        "FORM_DATA_TYPE_VERSION_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_HISTORY_ENTITY_ID"),
        "FORM_DATA_TYPE_VERSION_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_HISTORY_REQUEST_ID"),
        "FORM_DATA_TYPE_VERSION_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_HISTORY_TRACE_ID"),
        "FORM_DATA_TYPE_VERSION_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_DATA_TYPE_VERSION_HISTORY_entity_changed",
        "FORM_DATA_TYPE_VERSION_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    op.create_table(
        "FORM_LIBRARY_GRANT_HISTORY",
        sa.Column(
            "ID",
            sa.Uuid(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
            comment="UUIDV7 IDENTIFIER FOR THIS HISTORY ROW.",
        ),
        sa.Column(
            "ENTITY_ID",
            sa.Uuid(),
            nullable=False,
            comment="IDENTIFIER OF THE SOURCE ROW THAT CHANGED.",
        ),
        sa.Column(
            "MODIFIER_TYPE",
            sa.String(length=255),
            nullable=False,
            comment="APPLICATION TYPE OF THE ACTOR THAT MADE THE CHANGE.",
        ),
        sa.Column(
            "MODIFIER_ID",
            sa.String(length=255),
            nullable=False,
            comment="IDENTIFIER OF THE ACTOR; STORED AS TEXT TO SUPPORT DIFFERENT ACTOR TYPES.",
        ),
        sa.Column(
            "CHANGED_AT",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC TIMESTAMP AT WHICH THE CHANGE OCCURRED.",
        ),
        sa.Column(
            "OPERATION",
            sa.String(length=32),
            nullable=False,
            comment="INSERT, UPDATE, DELETE, OR RESTORE.",
        ),
        sa.Column(
            "REQUEST_ID", sa.String(length=64), nullable=True, comment="REQUEST CORRELATION ID."
        ),
        sa.Column(
            "TRACE_ID", sa.String(length=64), nullable=True, comment="OPENTELEMETRY TRACE ID."
        ),
        sa.Column(
            "REASON",
            sa.String(length=1024),
            nullable=True,
            comment="OPTIONAL BUSINESS REASON FOR THE CHANGE.",
        ),
        sa.Column(
            "SOURCE_IP",
            sa.String(length=64),
            nullable=True,
            comment="ORIGINATING CLIENT IP WHEN AVAILABLE.",
        ),
        sa.Column(
            "USER_AGENT",
            sa.String(length=1024),
            nullable=True,
            comment="ORIGINATING USER AGENT WHEN AVAILABLE.",
        ),
        sa.Column(
            "FROM_COMPONENT_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF COMPONENT_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_COMPONENT_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF COMPONENT_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_DATA_TYPE_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF DATA_TYPE_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_DATA_TYPE_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF DATA_TYPE_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_USER_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF USER_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_USER_ID", sa.Uuid(), nullable=True, comment="TO VALUE OF USER_ID FOR THIS CHANGE."
        ),
        sa.Column(
            "FROM_WORK_GROUP_ID",
            sa.Uuid(),
            nullable=True,
            comment="FROM VALUE OF WORK_GROUP_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_WORK_GROUP_ID",
            sa.Uuid(),
            nullable=True,
            comment="TO VALUE OF WORK_GROUP_ID FOR THIS CHANGE.",
        ),
        sa.Column(
            "FROM_CAN_USE",
            sa.Boolean(),
            nullable=True,
            comment="FROM VALUE OF CAN_USE FOR THIS CHANGE.",
        ),
        sa.Column(
            "TO_CAN_USE",
            sa.Boolean(),
            nullable=True,
            comment="TO VALUE OF CAN_USE FOR THIS CHANGE.",
        ),
        sa.ForeignKeyConstraint(
            ["ENTITY_ID"], ["FORM_LIBRARY_GRANT.ID"], onupdate="RESTRICT", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("ID"),
    )
    op.create_index(
        op.f("ix_FORM_LIBRARY_GRANT_HISTORY_CHANGED_AT"),
        "FORM_LIBRARY_GRANT_HISTORY",
        ["CHANGED_AT"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_LIBRARY_GRANT_HISTORY_ENTITY_ID"),
        "FORM_LIBRARY_GRANT_HISTORY",
        ["ENTITY_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_LIBRARY_GRANT_HISTORY_REQUEST_ID"),
        "FORM_LIBRARY_GRANT_HISTORY",
        ["REQUEST_ID"],
        unique=False,
    )
    op.create_index(
        op.f("ix_FORM_LIBRARY_GRANT_HISTORY_TRACE_ID"),
        "FORM_LIBRARY_GRANT_HISTORY",
        ["TRACE_ID"],
        unique=False,
    )
    op.create_index(
        "ix_FORM_LIBRARY_GRANT_HISTORY_entity_changed",
        "FORM_LIBRARY_GRANT_HISTORY",
        ["ENTITY_ID", "CHANGED_AT"],
        unique=False,
    )
    # Existing published rows retain SQL NULL and their original documents/checksums.
    for name in ("REUSE_INSTANCES", "REUSE_SOURCE", "REUSE_MANIFEST"):
        op.add_column(
            "FORM_VERSION", sa.Column(name, postgresql.JSONB(none_as_null=True), nullable=True)
        )
        for prefix in ("FROM", "TO"):
            op.add_column(
                "FORM_VERSION_HISTORY",
                sa.Column(
                    f"{prefix}_{name}",
                    postgresql.JSONB(none_as_null=True),
                    nullable=True,
                    comment=f"{prefix} VALUE OF {name} FOR THIS CHANGE.",
                ),
            )
    for table in ("FORM_COMPONENT_VERSION", "FORM_DATA_TYPE_VERSION"):
        op.create_check_constraint(
            f"ck_{table}_publication",
            table,
            """("STATUS" = 'DRAFT' AND "CHECKSUM" IS NULL AND "RESOLVED" IS NULL AND "PUBLISHED_AT" IS NULL AND "PUBLISHED_BY_USER_ID" IS NULL) OR ("STATUS" IN ('PUBLISHED', 'RETIRED') AND "CHECKSUM" IS NOT NULL AND length("CHECKSUM") = 64 AND "RESOLVED" IS NOT NULL AND "PUBLISHED_AT" IS NOT NULL AND "PUBLISHED_BY_USER_ID" IS NOT NULL)""",
        )
    for name, resource, target in (
        ("component_user", "COMPONENT_ID", "USER_ID"),
        ("component_group", "COMPONENT_ID", "WORK_GROUP_ID"),
        ("type_user", "DATA_TYPE_ID", "USER_ID"),
        ("type_group", "DATA_TYPE_ID", "WORK_GROUP_ID"),
    ):
        op.create_index(
            f"uq_FORM_LIBRARY_GRANT_{name}_active",
            "FORM_LIBRARY_GRANT",
            [resource, target],
            unique=True,
            postgresql_where=sa.text(
                f'"{resource}" IS NOT NULL AND "{target}" IS NOT NULL AND "DELETED_AT" IS NULL'
            ),
        )
    op.execute("""CREATE FUNCTION protect_form_library_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW."STATUS" <> 'DRAFT' THEN
                    RAISE EXCEPTION 'New library versions must be drafts' USING ERRCODE = '23514';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD."STATUS" <> 'DRAFT' THEN
                IF TG_OP = 'UPDATE' AND OLD."STATUS" = 'PUBLISHED'
                    AND NEW."STATUS" = 'RETIRED'
                    AND (to_jsonb(NEW) - ARRAY['STATUS', 'VERSION', 'UPDATED_AT']) =
                        (to_jsonb(OLD) - ARRAY['STATUS', 'VERSION', 'UPDATED_AT']) THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Published library version is immutable' USING ERRCODE = '23514';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            IF NEW."STATUS" = 'RETIRED' THEN
                RAISE EXCEPTION 'Draft cannot be retired' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$""")
    for table in ("FORM_COMPONENT_VERSION", "FORM_DATA_TYPE_VERSION"):
        op.execute(
            f'CREATE TRIGGER protect_{table.lower()} BEFORE INSERT OR UPDATE OR DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION protect_form_library_version()'
        )


def _downgrade_authored_form_library_versions() -> None:
    """Downgrade schema."""
    for table in ("FORM_DATA_TYPE_VERSION", "FORM_COMPONENT_VERSION"):
        op.execute(f'DROP TRIGGER protect_{table.lower()} ON "{table}"')
    op.execute("DROP FUNCTION protect_form_library_version()")
    for name in ("REUSE_MANIFEST", "REUSE_SOURCE", "REUSE_INSTANCES"):
        for prefix in ("TO", "FROM"):
            op.drop_column("FORM_VERSION_HISTORY", f"{prefix}_{name}")
        op.drop_column("FORM_VERSION", name)
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        "ix_FORM_LIBRARY_GRANT_HISTORY_entity_changed", table_name="FORM_LIBRARY_GRANT_HISTORY"
    )
    op.drop_index(
        op.f("ix_FORM_LIBRARY_GRANT_HISTORY_TRACE_ID"), table_name="FORM_LIBRARY_GRANT_HISTORY"
    )
    op.drop_index(
        op.f("ix_FORM_LIBRARY_GRANT_HISTORY_REQUEST_ID"), table_name="FORM_LIBRARY_GRANT_HISTORY"
    )
    op.drop_index(
        op.f("ix_FORM_LIBRARY_GRANT_HISTORY_ENTITY_ID"), table_name="FORM_LIBRARY_GRANT_HISTORY"
    )
    op.drop_index(
        op.f("ix_FORM_LIBRARY_GRANT_HISTORY_CHANGED_AT"), table_name="FORM_LIBRARY_GRANT_HISTORY"
    )
    op.drop_table("FORM_LIBRARY_GRANT_HISTORY")
    op.drop_index(
        "ix_FORM_DATA_TYPE_VERSION_HISTORY_entity_changed",
        table_name="FORM_DATA_TYPE_VERSION_HISTORY",
    )
    op.drop_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_HISTORY_TRACE_ID"),
        table_name="FORM_DATA_TYPE_VERSION_HISTORY",
    )
    op.drop_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_HISTORY_REQUEST_ID"),
        table_name="FORM_DATA_TYPE_VERSION_HISTORY",
    )
    op.drop_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_HISTORY_ENTITY_ID"),
        table_name="FORM_DATA_TYPE_VERSION_HISTORY",
    )
    op.drop_index(
        op.f("ix_FORM_DATA_TYPE_VERSION_HISTORY_CHANGED_AT"),
        table_name="FORM_DATA_TYPE_VERSION_HISTORY",
    )
    op.drop_table("FORM_DATA_TYPE_VERSION_HISTORY")
    op.drop_index(
        "ix_FORM_COMPONENT_VERSION_HISTORY_entity_changed",
        table_name="FORM_COMPONENT_VERSION_HISTORY",
    )
    op.drop_index(
        op.f("ix_FORM_COMPONENT_VERSION_HISTORY_TRACE_ID"),
        table_name="FORM_COMPONENT_VERSION_HISTORY",
    )
    op.drop_index(
        op.f("ix_FORM_COMPONENT_VERSION_HISTORY_REQUEST_ID"),
        table_name="FORM_COMPONENT_VERSION_HISTORY",
    )
    op.drop_index(
        op.f("ix_FORM_COMPONENT_VERSION_HISTORY_ENTITY_ID"),
        table_name="FORM_COMPONENT_VERSION_HISTORY",
    )
    op.drop_index(
        op.f("ix_FORM_COMPONENT_VERSION_HISTORY_CHANGED_AT"),
        table_name="FORM_COMPONENT_VERSION_HISTORY",
    )
    op.drop_table("FORM_COMPONENT_VERSION_HISTORY")
    op.drop_index("ix_FORM_LIBRARY_GRANT_user", table_name="FORM_LIBRARY_GRANT")
    op.drop_index("ix_FORM_LIBRARY_GRANT_group", table_name="FORM_LIBRARY_GRANT")
    op.drop_index("ix_FORM_LIBRARY_GRANT_data_type", table_name="FORM_LIBRARY_GRANT")
    op.drop_index("ix_FORM_LIBRARY_GRANT_component", table_name="FORM_LIBRARY_GRANT")
    op.drop_index(op.f("ix_FORM_LIBRARY_GRANT_CREATED_AT"), table_name="FORM_LIBRARY_GRANT")
    op.drop_table("FORM_LIBRARY_GRANT")
    op.drop_index("ix_FORM_DATA_TYPE_VERSION_root_status", table_name="FORM_DATA_TYPE_VERSION")
    op.drop_index(op.f("ix_FORM_DATA_TYPE_VERSION_CREATED_AT"), table_name="FORM_DATA_TYPE_VERSION")
    op.drop_table("FORM_DATA_TYPE_VERSION")
    op.drop_index("ix_FORM_DATA_TYPE_HISTORY_entity_changed", table_name="FORM_DATA_TYPE_HISTORY")
    op.drop_index(op.f("ix_FORM_DATA_TYPE_HISTORY_TRACE_ID"), table_name="FORM_DATA_TYPE_HISTORY")
    op.drop_index(op.f("ix_FORM_DATA_TYPE_HISTORY_REQUEST_ID"), table_name="FORM_DATA_TYPE_HISTORY")
    op.drop_index(op.f("ix_FORM_DATA_TYPE_HISTORY_ENTITY_ID"), table_name="FORM_DATA_TYPE_HISTORY")
    op.drop_index(op.f("ix_FORM_DATA_TYPE_HISTORY_CHANGED_AT"), table_name="FORM_DATA_TYPE_HISTORY")
    op.drop_table("FORM_DATA_TYPE_HISTORY")
    op.drop_index("ix_FORM_COMPONENT_VERSION_root_status", table_name="FORM_COMPONENT_VERSION")
    op.drop_index(op.f("ix_FORM_COMPONENT_VERSION_CREATED_AT"), table_name="FORM_COMPONENT_VERSION")
    op.drop_table("FORM_COMPONENT_VERSION")
    op.drop_index("ix_FORM_COMPONENT_HISTORY_entity_changed", table_name="FORM_COMPONENT_HISTORY")
    op.drop_index(op.f("ix_FORM_COMPONENT_HISTORY_TRACE_ID"), table_name="FORM_COMPONENT_HISTORY")
    op.drop_index(op.f("ix_FORM_COMPONENT_HISTORY_REQUEST_ID"), table_name="FORM_COMPONENT_HISTORY")
    op.drop_index(op.f("ix_FORM_COMPONENT_HISTORY_ENTITY_ID"), table_name="FORM_COMPONENT_HISTORY")
    op.drop_index(op.f("ix_FORM_COMPONENT_HISTORY_CHANGED_AT"), table_name="FORM_COMPONENT_HISTORY")
    op.drop_table("FORM_COMPONENT_HISTORY")
    op.drop_index(
        "uq_FORM_DATA_TYPE_CODE_active",
        table_name="FORM_DATA_TYPE",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index("ix_FORM_DATA_TYPE_owner_created", table_name="FORM_DATA_TYPE")
    op.drop_index(op.f("ix_FORM_DATA_TYPE_CREATED_AT"), table_name="FORM_DATA_TYPE")
    op.drop_table("FORM_DATA_TYPE")
    op.drop_index(
        "uq_FORM_COMPONENT_CODE_active",
        table_name="FORM_COMPONENT",
        postgresql_where=sa.text('"DELETED_AT" IS NULL'),
    )
    op.drop_index("ix_FORM_COMPONENT_owner_created", table_name="FORM_COMPONENT")
    op.drop_index(op.f("ix_FORM_COMPONENT_CREATED_AT"), table_name="FORM_COMPONENT")
    op.drop_table("FORM_COMPONENT")


# Form behavior and collection state


def _upgrade_form_behavior_and_collection_state() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "FORM_SUBMISSION",
        sa.Column(
            "ITEM_IDENTITY",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "FORM_SUBMISSION",
        sa.Column(
            "OVERRIDE_PROVENANCE",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "FORM_SUBMISSION_HISTORY",
        sa.Column(
            "FROM_ITEM_IDENTITY",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF ITEM_IDENTITY FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "FORM_SUBMISSION_HISTORY",
        sa.Column(
            "TO_ITEM_IDENTITY",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF ITEM_IDENTITY FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "FORM_SUBMISSION_HISTORY",
        sa.Column(
            "FROM_OVERRIDE_PROVENANCE",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="FROM VALUE OF OVERRIDE_PROVENANCE FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "FORM_SUBMISSION_HISTORY",
        sa.Column(
            "TO_OVERRIDE_PROVENANCE",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="TO VALUE OF OVERRIDE_PROVENANCE FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "FORM_VERSION", sa.Column("BEHAVIOR_DIALECT", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "FORM_VERSION_HISTORY",
        sa.Column(
            "FROM_BEHAVIOR_DIALECT",
            sa.String(length=64),
            nullable=True,
            comment="FROM VALUE OF BEHAVIOR_DIALECT FOR THIS CHANGE.",
        ),
    )
    op.add_column(
        "FORM_VERSION_HISTORY",
        sa.Column(
            "TO_BEHAVIOR_DIALECT",
            sa.String(length=64),
            nullable=True,
            comment="TO VALUE OF BEHAVIOR_DIALECT FOR THIS CHANGE.",
        ),
    )


def _downgrade_form_behavior_and_collection_state() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("FORM_VERSION_HISTORY", "TO_BEHAVIOR_DIALECT")
    op.drop_column("FORM_VERSION_HISTORY", "FROM_BEHAVIOR_DIALECT")
    op.drop_column("FORM_VERSION", "BEHAVIOR_DIALECT")
    op.drop_column("FORM_SUBMISSION_HISTORY", "TO_OVERRIDE_PROVENANCE")
    op.drop_column("FORM_SUBMISSION_HISTORY", "FROM_OVERRIDE_PROVENANCE")
    op.drop_column("FORM_SUBMISSION_HISTORY", "TO_ITEM_IDENTITY")
    op.drop_column("FORM_SUBMISSION_HISTORY", "FROM_ITEM_IDENTITY")
    op.drop_column("FORM_SUBMISSION", "OVERRIDE_PROVENANCE")
    op.drop_column("FORM_SUBMISSION", "ITEM_IDENTITY")


# Human task contract and corrections


def _upgrade_human_task_contract_and_corrections() -> None:
    jsonb = postgresql.JSONB(none_as_null=True)
    op.add_column("WORKFLOW_STEP", sa.Column("TASK_CONTRACT", jsonb, nullable=True))
    op.add_column(
        "FORM_SUBMISSION",
        sa.Column(
            "CORRECTION_SOURCE_SUBMISSION_ID",
            sa.Uuid(),
            sa.ForeignKey("FORM_SUBMISSION.ID", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column("FORM_SUBMISSION", sa.Column("CORRECTION_FEEDBACK", jsonb, nullable=True))
    for name, column_type in (
        ("CORRECTION_SOURCE_SUBMISSION_ID", sa.Uuid()),
        ("CORRECTION_FEEDBACK", postgresql.JSONB(none_as_null=True)),
    ):
        for prefix in ("FROM", "TO"):
            op.add_column(
                "FORM_SUBMISSION_HISTORY",
                sa.Column(
                    f"{prefix}_{name}",
                    column_type,
                    nullable=True,
                    comment=f"{prefix} VALUE OF {name} FOR THIS CHANGE.",
                ),
            )
    op.create_index(
        "uq_FORM_SUBMISSION_correction_source",
        "FORM_SUBMISSION",
        ["CORRECTION_SOURCE_SUBMISSION_ID"],
        unique=True,
        postgresql_where=sa.text('"CORRECTION_SOURCE_SUBMISSION_ID" IS NOT NULL'),
    )


def _downgrade_human_task_contract_and_corrections() -> None:
    op.drop_index("uq_FORM_SUBMISSION_correction_source", table_name="FORM_SUBMISSION")
    for name in ("CORRECTION_FEEDBACK", "CORRECTION_SOURCE_SUBMISSION_ID"):
        for prefix in ("TO", "FROM"):
            op.drop_column("FORM_SUBMISSION_HISTORY", f"{prefix}_{name}")
        op.drop_column("FORM_SUBMISSION", name)
    op.drop_column("WORKFLOW_STEP", "TASK_CONTRACT")


# Subprocess authoring contract


def _upgrade_subprocess_authoring_contract() -> None:
    jsonb = postgresql.JSONB(none_as_null=True)
    op.add_column("WORKFLOW_VERSION", sa.Column("SUBPROCESS_INTERFACE", jsonb, nullable=True))
    op.add_column("WORKFLOW_STEP", sa.Column("SUBPROCESS_CALL", jsonb, nullable=True))
    for prefix in ("FROM", "TO"):
        op.add_column(
            "WORKFLOW_VERSION_HISTORY",
            sa.Column(
                f"{prefix}_SUBPROCESS_INTERFACE",
                postgresql.JSONB(none_as_null=True),
                nullable=True,
                comment=f"{prefix} VALUE OF SUBPROCESS_INTERFACE FOR THIS CHANGE.",
            ),
        )
    connection = op.get_bind()
    root_id = connection.execute(
        sa.text("""
        INSERT INTO "STEP_TYPE" ("CODE", "NAME", "IS_ENABLED", "VERSION", "CREATED_AT")
        VALUES ('SUBPROCESS', 'Subprocess call', true, 1, now())
        RETURNING "ID"
    """)
    ).scalar_one()
    connection.execute(
        sa.text("""
        INSERT INTO "STEP_TYPE_HISTORY"
            ("ENTITY_ID", "MODIFIER_TYPE", "MODIFIER_ID", "CHANGED_AT", "OPERATION",
             "TO_CODE", "TO_NAME", "TO_IS_ENABLED")
        VALUES (:root_id, 'system', 'migration:4e6f8a913c02', now(), 'insert',
                'SUBPROCESS', 'Subprocess call', true)
    """),
        {"root_id": root_id},
    )
    version_id = connection.execute(
        sa.text("""
        INSERT INTO "STEP_TYPE_VERSION"
            ("STEP_TYPE_ID", "NUMBER", "STATUS", "HANDLER_KEY", "HANDLER_VERSION",
             "EXECUTION_MODE", "CONFIG_SCHEMA", "VERSION", "CREATED_AT")
        VALUES (:root_id, 1, 'DRAFT', 'subprocess', '1', 'WAIT',
                CAST(:config_schema AS jsonb),
                1, now())
        RETURNING "ID"
    """),
        {
            "root_id": root_id,
            "config_schema": '{"additionalProperties":false,"properties":{},"title":"EmptyConfig","type":"object"}',
        },
    ).scalar_one()
    connection.execute(
        sa.text("""
        UPDATE "STEP_TYPE_VERSION" SET "STATUS" = 'PUBLISHED', "PUBLISHED_AT" = now()
        WHERE "ID" = :version_id
    """),
        {"version_id": version_id},
    )


def _downgrade_subprocess_authoring_contract() -> None:
    connection = op.get_bind()
    op.execute('ALTER TABLE "STEP_TYPE_VERSION" DISABLE TRIGGER step_type_version_immutable')
    connection.execute(
        sa.text("""
        DELETE FROM "STEP_TYPE_VERSION" WHERE "HANDLER_KEY" = 'subprocess'
        AND "HANDLER_VERSION" = '1'
    """)
    )
    op.execute('ALTER TABLE "STEP_TYPE_VERSION" ENABLE TRIGGER step_type_version_immutable')
    connection.execute(
        sa.text("""
        DELETE FROM "STEP_TYPE_HISTORY" WHERE "MODIFIER_ID" = 'migration:4e6f8a913c02'
    """)
    )
    connection.execute(
        sa.text("""
        DELETE FROM "STEP_TYPE" WHERE "CODE" = 'SUBPROCESS'
    """)
    )
    for prefix in ("TO", "FROM"):
        op.drop_column("WORKFLOW_VERSION_HISTORY", f"{prefix}_SUBPROCESS_INTERFACE")
    op.drop_column("WORKFLOW_STEP", "SUBPROCESS_CALL")
    op.drop_column("WORKFLOW_VERSION", "SUBPROCESS_INTERFACE")


# Subprocess runtime


def _upgrade_subprocess_runtime() -> None:
    op.add_column(
        "PROCESS_INSTANCE", sa.Column("PARENT_STEP_EXECUTION_ID", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "PROCESS_INSTANCE",
        sa.Column("INPUT_CONTEXT", postgresql.JSONB(none_as_null=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_PROCESS_INSTANCE_parent_execution",
        "PROCESS_INSTANCE",
        "STEP_EXECUTION",
        ["PARENT_STEP_EXECUTION_ID"],
        ["ID"],
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    )
    op.drop_constraint("uq_PROCESS_INSTANCE_request", "PROCESS_INSTANCE", type_="unique")
    op.create_index(
        "uq_PROCESS_INSTANCE_root_request",
        "PROCESS_INSTANCE",
        ["BUSINESS_REQUEST_ID"],
        unique=True,
        postgresql_where=sa.text('"PARENT_STEP_EXECUTION_ID" IS NULL'),
    )
    op.create_index(
        "uq_PROCESS_INSTANCE_parent_execution",
        "PROCESS_INSTANCE",
        ["PARENT_STEP_EXECUTION_ID"],
        unique=True,
        postgresql_where=sa.text('"PARENT_STEP_EXECUTION_ID" IS NOT NULL'),
    )
    op.drop_constraint("ck_STEP_EXECUTION_wait_kind", "STEP_EXECUTION", type_="check")
    op.create_check_constraint(
        "ck_STEP_EXECUTION_wait_kind",
        "STEP_EXECUTION",
        """"WAIT_KIND" IS NULL OR "WAIT_KIND" IN ('HUMAN','EVENT','TIMER','BACKGROUND','SUBPROCESS')""",
    )


def _downgrade_subprocess_runtime() -> None:
    connection = op.get_bind()
    children = connection.execute(
        sa.text(
            'SELECT 1 FROM "PROCESS_INSTANCE" WHERE "PARENT_STEP_EXECUTION_ID" IS NOT NULL LIMIT 1'
        )
    ).first()
    if children is not None:
        raise RuntimeError("Remove subprocess runtime records before downgrading this revision")
    op.drop_constraint("ck_STEP_EXECUTION_wait_kind", "STEP_EXECUTION", type_="check")
    op.create_check_constraint(
        "ck_STEP_EXECUTION_wait_kind",
        "STEP_EXECUTION",
        """"WAIT_KIND" IS NULL OR "WAIT_KIND" IN ('HUMAN','EVENT','TIMER','BACKGROUND')""",
    )
    op.drop_index("uq_PROCESS_INSTANCE_parent_execution", table_name="PROCESS_INSTANCE")
    op.drop_index("uq_PROCESS_INSTANCE_root_request", table_name="PROCESS_INSTANCE")
    op.create_unique_constraint(
        "uq_PROCESS_INSTANCE_request", "PROCESS_INSTANCE", ["BUSINESS_REQUEST_ID"]
    )
    op.drop_constraint(
        "fk_PROCESS_INSTANCE_parent_execution", "PROCESS_INSTANCE", type_="foreignkey"
    )
    op.drop_column("PROCESS_INSTANCE", "INPUT_CONTEXT")
    op.drop_column("PROCESS_INSTANCE", "PARENT_STEP_EXECUTION_ID")


# Library template provenance


def _upgrade_library_template_provenance() -> None:
    for table in ("FORM_VERSION", "WORKFLOW_VERSION"):
        op.add_column(
            table,
            sa.Column("TEMPLATE_SOURCE", postgresql.JSONB(none_as_null=True), nullable=True),
        )
        for prefix in ("FROM", "TO"):
            op.add_column(
                f"{table}_HISTORY",
                sa.Column(
                    f"{prefix}_TEMPLATE_SOURCE",
                    postgresql.JSONB(none_as_null=True),
                    nullable=True,
                    comment=f"{prefix} VALUE OF TEMPLATE_SOURCE FOR THIS CHANGE.",
                ),
            )


def _downgrade_library_template_provenance() -> None:
    for table in ("WORKFLOW_VERSION", "FORM_VERSION"):
        for prefix in ("TO", "FROM"):
            op.drop_column(f"{table}_HISTORY", f"{prefix}_TEMPLATE_SOURCE")
        op.drop_column(table, "TEMPLATE_SOURCE")
