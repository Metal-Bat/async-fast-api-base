"""Required built-in handlers, permissions and maintenance schedules.

No demo data, role grants or external integration activation is installed.
Optional admin credentials must be explicitly configured as a complete pair.
"""

import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "0002_required_data"
down_revision = "0001_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Install required data after the complete schema and guards exist."""
    _seed_catalog()
    _upgrade_typed_transform_handler_v2()
    _seed_wait_catalog()
    _seed_notification_v2()
    _seed_subprocess()
    _seed_catalog(_deployed_catalog())
    _seed_permissions()
    _create_report_cleanup_schedule()
    _seed_upload_cleanup_schedule()
    _create_initial_admin()


def downgrade() -> None:
    """Preserve seeds during full teardown; refuse data-only catalog rollback."""
    from alembic import context

    if context.get_revision_argument() is not None:
        raise RuntimeError(
            "Required data cannot be downgraded independently; use a backup to roll back"
        )


def _create_initial_admin() -> None:
    username = os.getenv("INITIAL_ADMIN_USERNAME")
    password = os.getenv("INITIAL_ADMIN_PASSWORD")
    if not bool(username) and not bool(password):
        return
    if not bool(username) or not bool(password):
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


def _seed_catalog(catalog: list[dict[str, Any]] | None = None) -> None:
    """Install and publish only the supplied frozen handler contracts."""
    payload = json.dumps(_INITIAL_CATALOG if catalog is None else catalog)
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
        UPDATE "STEP_TYPE_VERSION" AS version
        SET "STATUS" = 'PUBLISHED', "PUBLISHED_AT" = now()
        FROM "STEP_TYPE" AS root,
             jsonb_array_elements(CAST(:payload AS jsonb)) AS seed(data)
        WHERE version."STEP_TYPE_ID" = root."ID"
          AND root."CODE" = data->>'code'
          AND version."HANDLER_KEY" = data->>'handler_key'
          AND version."HANDLER_VERSION" = data->>'handler_version'
          AND version."NUMBER" = 1 AND version."STATUS" = 'DRAFT'
        """).bindparams(payload=payload)
    )


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


def _seed_upload_cleanup_schedule() -> None:
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


def _seed_wait_catalog() -> None:
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


def _seed_notification_v2() -> None:
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


def _seed_subprocess() -> None:
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


_PERMISSIONS = {
    "admin.users.manage": "Manage ordinary users; superuser changes require superuser authority.",
    "admin.permissions.manage": "Manage permission definitions and role assignments.",
    "admin.work_groups.manage": "Manage work groups and administrative resource selectors.",
    "admin.history.read": "Read authorized administrative history.",
    "admin.tasks.manage": "Manage task definitions, schedules and execution operations.",
    "forms.manage": "Author forms, reusable form definitions and client catalog entries.",
    "workflows.manage": "Author workflows, step catalogs, agents and designer metadata.",
    "requests.manage": "Manage request types and their application configuration.",
    "requests.start": "Use requests and work items subject to current resource eligibility.",
    "integrations.manage": "Manage governed integration connections and grants.",
    "integration.connection.use": "Use an explicitly granted integration connection.",
    "processes.recover": "Enter recovery routes; recovery service also requires a superuser.",
    "support.incidents.manage": "Read and acknowledge sanitized support incidents; correlation grants no access.",
}


def _seed_permissions() -> None:
    """Install absent capability definitions without roles or user assignments."""
    for name, description in _PERMISSIONS.items():
        op.execute(
            sa.text(
                'INSERT INTO "PERMISSION" ("NAME", "DESCRIPTION", "VERSION", "CREATED_AT") '
                'VALUES (:name, :description, 1, now()) ON CONFLICT ("NAME") DO NOTHING'
            ).bindparams(name=name, description=description)
        )


# Frozen contracts from the deployed extension package at baseline creation.
_DEPLOYED_CATALOG: list[dict[str, Any]] = [
    {
        "code": "AI_DECISION",
        "name": "AI decision",
        "handler_key": "ai_decision",
        "handler_version": "1",
        "execution_mode": "BACKGROUND",
        "config_schema": {
            "$defs": {"Reference": {"maxLength": 512, "minLength": 1, "type": "string"}},
            "properties": {"agent_ref": {"$ref": "#/$defs/Reference"}},
            "required": ["agent_ref"],
            "title": "AIDecisionConfig",
            "type": "object",
            "x-step-definition": {
                "category": "DECISION",
                "name_key": "step.ai_decision.name",
                "help_key": "step.ai_decision.help",
                "outcomes": ["next", "review"],
                "examples": [{"agent_ref": "<published-agent-ref>"}],
                "required_capabilities": ["ai.agent.use"],
            },
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
                "port_key": "choice",
                "direction": "OUTPUT",
                "value_schema": {"type": "string", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "confidence",
                "direction": "OUTPUT",
                "value_schema": {"type": "number", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
            {
                "port_key": "needs_review",
                "direction": "OUTPUT",
                "value_schema": {"type": "boolean", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            },
        ],
    },
    {
        "code": "CONNECTION_STATUS",
        "name": "Connection status",
        "handler_key": "connection_status",
        "handler_version": "1",
        "execution_mode": "BACKGROUND",
        "config_schema": {
            "$defs": {"Reference": {"maxLength": 512, "minLength": 1, "type": "string"}},
            "additionalProperties": False,
            "properties": {"connection_ref": {"$ref": "#/$defs/Reference"}},
            "required": ["connection_ref"],
            "title": "ConnectionStatusConfig",
            "type": "object",
            "x-step-definition": {
                "category": "INTEGRATION",
                "name_key": "step.connection_status.name",
                "help_key": "step.connection_status.help",
                "outcomes": [],
                "examples": [{"connection_ref": "<approved-connection-ref>"}],
                "required_capabilities": ["integration.connection.use"],
            },
        },
        "ports": [
            {
                "port_key": "status_code",
                "direction": "OUTPUT",
                "value_schema": {"type": "integer", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            }
        ],
    },
    {
        "code": "PERMISSION_CHECK",
        "name": "Permission check",
        "handler_key": "permission_check",
        "handler_version": "1",
        "execution_mode": "SYNC",
        "config_schema": {
            "additionalProperties": False,
            "properties": {
                "permission_key": {
                    "maxLength": 128,
                    "minLength": 1,
                    "title": "Permission Key",
                    "type": "string",
                }
            },
            "required": ["permission_key"],
            "title": "PermissionConfig",
            "type": "object",
            "x-step-definition": {
                "category": "DECISION",
                "name_key": "step.permission_check.name",
                "help_key": "step.permission_check.help",
                "outcomes": [],
                "examples": [{"permission_key": "workflows.manage"}],
                "required_capabilities": [],
            },
        },
        "ports": [
            {
                "port_key": "allowed",
                "direction": "OUTPUT",
                "value_schema": {"type": "boolean", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            }
        ],
    },
    {
        "code": "REQUEST_PRIORITY",
        "name": "Request priority",
        "handler_key": "request_priority",
        "handler_version": "1",
        "execution_mode": "SYNC",
        "config_schema": {
            "additionalProperties": False,
            "properties": {},
            "title": "EmptyConfig",
            "type": "object",
            "x-step-definition": {
                "category": "DATA",
                "name_key": "step.request_priority.name",
                "help_key": "step.request_priority.help",
                "outcomes": [],
                "examples": [{}],
                "required_capabilities": [],
            },
        },
        "ports": [
            {
                "port_key": "priority",
                "direction": "OUTPUT",
                "value_schema": {"type": "integer", "not": {"type": "null"}},
                "required": True,
                "nullable": False,
                "cardinality": "SCALAR",
            }
        ],
    },
]


def _deployed_catalog() -> list[dict[str, Any]]:
    """Derive public fingerprints from frozen deployed contracts without runtime imports."""
    catalog: list[dict[str, Any]] = []
    for row in _DEPLOYED_CATALOG:
        schema = dict(row["config_schema"])
        definition = schema.pop("x-step-definition")
        contract = dict(row, config_schema=schema)
        contract.update(definition, is_starter=False, is_ender=False)
        fingerprint = hashlib.sha256(
            json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        enriched = dict(row["config_schema"], **{"x-step-definition-fingerprint": fingerprint})
        catalog.append(dict(row, config_schema=enriched))
    return catalog
